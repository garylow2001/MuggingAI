import os

# Prevent tokenizers deadlock when running under uvicorn/pm forking
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import faiss
import numpy as np
from typing import List, Dict, Any, Optional
from app.core.config import settings
import json
import logging
from sentence_transformers import SentenceTransformer

# Get logger for this module
logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Initialize sentence transformer model
        self.model = SentenceTransformer(model_name)
        logger.info(
            "Loaded sentence-transformers model: %s (dim=%d)",
            model_name,
            self.model.get_sentence_embedding_dimension(),
        )

        self.index_path = os.path.join(settings.vector_store_path, "faiss_index.bin")
        self.metadata_path = os.path.join(settings.vector_store_path, "metadata.json")

        # Initialize FAISS index
        self.dimension = (
            self.model.get_sentence_embedding_dimension()
        )  # Get dimension from the model
        self.index = None
        self.metadata: List[Dict[str, Any]] = []

        self._load_or_create_index()

    def _load_or_create_index(self):
        """Load existing index or create a new one."""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            # Load existing index
            self.index = faiss.read_index(self.index_path)
            # Verify index dimension matches model dimension
            idx_dim = int(getattr(self.index, "d", -1))
            if idx_dim != self.dimension:
                # If dimensions don't match, remove existing index/metadata and recreate to follow current model
                logger.info(
                    "FAISS index dimension (%s) does not match model dimension (%s). Removing old index and recreating to match model.",
                    idx_dim,
                    self.dimension,
                )
                if os.path.exists(self.index_path):
                    os.remove(self.index_path)
                if os.path.exists(self.metadata_path):
                    os.remove(self.metadata_path)
                logger.info("Removed old FAISS index and metadata files")
                # Recreate empty index and metadata
                self.index = faiss.IndexFlatIP(self.dimension)
                self.metadata = []
                return
            with open(self.metadata_path, "r") as f:
                self.metadata = json.load(f)
        else:
            # Create new index
            self.index = faiss.IndexFlatIP(
                self.dimension
            )  # Inner product for cosine similarity
            self.metadata = []

    def _ensure_index(self):
        """Ensure the FAISS index exists and matches the configured dimension."""
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dimension)
            return
        idx_dim = int(getattr(self.index, "d", -1))
        if idx_dim != self.dimension:
            logger.warning(
                "FAISS index dim mismatch at runtime (index=%s, model=%s). Recreating index.",
                idx_dim,
                self.dimension,
            )
            self.index = faiss.IndexFlatIP(self.dimension)

    def _save_index(self):
        """Save the FAISS index and metadata."""
        os.makedirs(settings.vector_store_path, exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, "w") as f:
            json.dump(self.metadata, f)

    async def get_embedding(self, text: str) -> List[float]:
        """Async wrapper for create_embedding."""
        return self.create_embedding(text)

    def create_embedding(self, text: str) -> List[float]:
        """Create embedding using sentence-transformers model."""
        if not text:
            raise ValueError("Text for embedding must be non-empty")

        # Batch encode to get consistent numpy output
        emb_batch = self.model.encode(
            [text], convert_to_numpy=True, show_progress_bar=False
        )
        emb = np.asarray(emb_batch[0], dtype=np.float32)

        # Ensure correct dimensionality
        if emb.shape[0] != self.dimension:
            # If different, resize or pad/truncate safely
            if emb.shape[0] > self.dimension:
                emb = emb[: self.dimension]
            else:
                padded = np.zeros(self.dimension, dtype=np.float32)
                padded[: emb.shape[0]] = emb
                emb = padded

        # Normalize for cosine similarity when using IndexFlatIP
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        return emb.tolist()

    def _ensure_embedding(self, embedding: List[float]) -> np.ndarray:
        """Validate, pad/truncate, normalize and return numpy array of shape (dimension,)"""
        arr = np.asarray(embedding, dtype=np.float32).reshape(-1)

        if arr.shape[0] != self.dimension:
            if arr.shape[0] > self.dimension:
                arr = arr[: self.dimension]
            else:
                padded = np.zeros(self.dimension, dtype=np.float32)
                padded[: arr.shape[0]] = arr
                arr = padded

        # normalize for IndexFlatIP (cosine similarity)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm

        return arr

    def store_embedding(
        self,
        embedding: List[float],
        chunk_id: int,
        content: Optional[str] = None,
        course_id: Optional[int] = None,
        file_id: Optional[int] = None,
        chapter_title: Optional[str] = None,
        chunk_index: Optional[int] = None,
        page_number: Optional[int] = None,
    ) -> str:
        """
        Store a single embedding and return its internal chunk id string.

        This method now accepts metadata fields so callers can persist course/file/chapter
        information into the single shared metadata store (metadata.json). That allows
        filtering by `course_id` at query time while keeping one FAISS index.
        """
        # Ensure FAISS index exists
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dimension)

        # Validate and prepare embedding
        arr = self._ensure_embedding(embedding)
        embedding_array = np.asarray([arr], dtype=np.float32)

        # Add to FAISS index
        self.index.add(embedding_array)

        # Create metadata entry with provided metadata (caller may pass None for some fields)
        chunk_id_str = f"chunk_{len(self.metadata)}"
        metadata_entry = {
            "id": chunk_id_str,
            "content": content or "",
            "course_id": course_id,
            "file_id": file_id,
            "chapter_title": chapter_title,
            "chunk_index": chunk_index,
            "page_number": page_number,
            "faiss_index": len(self.metadata),
            "chunk_id": chunk_id,  # Reference to the database chunk
        }
        self.metadata.append(metadata_entry)

        # Persist index + metadata
        self._save_index()

        return chunk_id_str

    async def add_chunks(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Add chunks to the vector store and return their IDs."""
        if not chunks:
            return []

        # Get embeddings for all chunks
        texts = [chunk["content"] for chunk in chunks]
        embeddings = []

        for i, text in enumerate(texts):
            embedding = await self.get_embedding(text)
            # Basic validation: embedding should be list/array of correct length
            if not embedding or len(embedding) != self.dimension:
                raise ValueError(
                    f"Invalid embedding for chunk {i}: length={len(embedding) if embedding else 0}"
                )
            embeddings.append(embedding)

        # Convert to numpy array (ensure each embedding is correct size)
        prepared = []
        for emb in embeddings:
            prepared.append(self._ensure_embedding(emb))
        if prepared:
            embeddings_array = np.vstack(prepared).astype(np.float32)
            # Ensure FAISS index exists
            if self.index is None:
                self.index = faiss.IndexFlatIP(self.dimension)
            self.index.add(embeddings_array)

        # Add metadata
        chunk_ids = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"chunk_{len(self.metadata) + i}"
            chunk_ids.append(chunk_id)

            # Normalize course_id to int when possible to make filtering reliable
            c_id = chunk.get("course_id")
            try:
                if c_id is not None:
                    c_id = int(c_id)
            except Exception:
                # leave as-is if cannot convert
                pass

            metadata_entry = {
                "id": chunk_id,
                "content": chunk["content"],
                "course_id": c_id,
                "file_id": chunk.get("file_id"),
                "chapter_title": chunk.get("chapter_title"),
                "chunk_index": chunk.get("chunk_index"),
                "page_number": chunk.get("page_number"),
                "faiss_index": len(self.metadata) + i,
            }
            self.metadata.append(metadata_entry)

        # Save index
        self._save_index()

        return chunk_ids

    async def search(
        self, query: str, course_ids: Optional[List[int]] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks based on query."""
        # Get query embedding
        query_embedding = await self.get_embedding(query)
        query_vector = np.array([query_embedding], dtype=np.float32)

        # Search in FAISS
        scores, indices = self.index.search(
            query_vector, min(limit * 2, len(self.metadata))
        )

        # Filter and format results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.metadata):
                metadata = self.metadata[idx]

                # Filter by course_ids if specified
                if course_ids is not None and len(course_ids) > 0:
                    meta_course = metadata.get("course_id")
                    try:
                        if meta_course is None:
                            continue
                        # Accept int/str mismatches
                        if not any(str(meta_course) == str(cid) for cid in course_ids):
                            continue
                    except Exception:
                        continue

                results.append(
                    {
                        "id": metadata["id"],
                        "content": metadata["content"],
                        "score": float(score),
                        "course_id": metadata.get("course_id"),
                        "chapter_title": metadata.get("chapter_title"),
                        "chunk_index": metadata.get("chunk_index"),
                    }
                )

                if len(results) >= limit:
                    break

        return results

    async def get_chunks_by_course_chapter(
        self,
        course_ids: Optional[List[int]] = None,
        chapter_title: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get chunks for specific courses and optionally chapter."""
        results = []

        for metadata in self.metadata:
            # Filter by course_ids
            if course_ids is not None and len(course_ids) > 0:
                meta_course = metadata.get("course_id")
                try:
                    if meta_course is None:
                        continue
                    if not any(str(meta_course) == str(cid) for cid in course_ids):
                        continue
                except Exception:
                    continue
            # If no course_ids, include all

            if chapter_title is None or metadata.get("chapter_title") == chapter_title:
                results.append(
                    {
                        "id": metadata["id"],
                        "content": metadata["content"],
                        "course_id": metadata.get("course_id"),
                        "chapter_title": metadata.get("chapter_title"),
                        "chunk_index": metadata.get("chunk_index"),
                        "page_number": metadata.get("page_number"),
                    }
                )

                if len(results) >= limit:
                    break

        # Sort by chunk_index for consistent ordering
        results.sort(key=lambda x: x.get("chunk_index", 0))
        return results

    async def delete_chunks_by_course(self, course_ids: List[int]):
        """Delete all chunks for specific courses."""
        # This is a simplified implementation
        # In production, you might want to use FAISS's remove_ids method
        # For now, we'll mark them as deleted in metadata

        if not course_ids:
            return

        for metadata in self.metadata:
            meta_course = metadata.get("course_id")
            if meta_course is not None:
                if any(str(meta_course) == str(cid) for cid in course_ids):
                    metadata["deleted"] = True

        self._save_index()

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        return {
            "total_chunks": len(self.metadata),
            "index_size": self.index.ntotal if self.index else 0,
            "dimension": self.dimension,
        }
