import faiss
import numpy as np
import pickle
import os
from typing import List, Dict, Any, Optional
import openai
from app.core.config import settings
import json
import logging

# Get logger for this module
logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.index_path = os.path.join(settings.vector_store_path, "faiss_index.bin")
        self.metadata_path = os.path.join(settings.vector_store_path, "metadata.json")
        
        # Initialize FAISS index
        self.dimension = 1536  # OpenAI text-embedding-3-small dimension
        self.index = None
        self.metadata = []
        
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing index or create a new one."""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            # Load existing index
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'r') as f:
                self.metadata = json.load(f)
        else:
            # Create new index
            self.index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
            self.metadata = []
    
    def _save_index(self):
        """Save the FAISS index and metadata."""
        os.makedirs(settings.vector_store_path, exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'w') as f:
            json.dump(self.metadata, f)
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a text using OpenAI."""
        response = await self.client.embeddings.create(
            model=settings.embedding_model,
            input=text
        )
        return response.data[0].embedding
    
    def create_embedding(self, text: str) -> List[float]:
        """Synchronous wrapper for get_embedding."""
        try:
            response = self.client.embeddings.create(
                model=settings.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            # Return a dummy embedding if OpenAI fails
            return [0.0] * self.dimension
    
    def store_embedding(self, embedding: List[float], chunk_id: int) -> str:
        """Store a single embedding and return its ID."""
        # Convert to numpy array
        embedding_array = np.array([embedding], dtype=np.float32)
        
        # Add to FAISS index
        self.index.add(embedding_array)
        
        # Create metadata entry
        chunk_id_str = f"chunk_{len(self.metadata)}"
        metadata_entry = {
            "id": chunk_id_str,
            "content": "",  # Will be filled by the caller
            "course_id": None,  # Will be filled by the caller
            "file_id": None,  # Will be filled by the caller
            "chapter_title": None,  # Will be filled by the caller
            "chunk_index": None,  # Will be filled by the caller
            "page_number": None,  # Will be filled by the caller
            "faiss_index": len(self.metadata),
            "chunk_id": chunk_id  # Reference to the database chunk
        }
        self.metadata.append(metadata_entry)
        
        # Save index
        self._save_index()
        
        return chunk_id_str
    
    async def add_chunks(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Add chunks to the vector store and return their IDs."""
        if not chunks:
            return []
        
        # Get embeddings for all chunks
        texts = [chunk['content'] for chunk in chunks]
        embeddings = []
        
        for text in texts:
            embedding = await self.get_embedding(text)
            embeddings.append(embedding)
        
        # Convert to numpy array
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        # Add to FAISS index
        self.index.add(embeddings_array)
        
        # Add metadata
        chunk_ids = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"chunk_{len(self.metadata) + i}"
            chunk_ids.append(chunk_id)
            
            metadata_entry = {
                "id": chunk_id,
                "content": chunk['content'],
                "course_id": chunk.get('course_id'),
                "file_id": chunk.get('file_id'),
                "chapter_title": chunk.get('chapter_title'),
                "chunk_index": chunk.get('chunk_index'),
                "page_number": chunk.get('page_number'),
                "faiss_index": len(self.metadata) + i
            }
            self.metadata.append(metadata_entry)
        
        # Save index
        self._save_index()
        
        return chunk_ids
    
    async def search(self, query: str, course_id: Optional[int] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar chunks based on query."""
        # Get query embedding
        query_embedding = await self.get_embedding(query)
        query_vector = np.array([query_embedding], dtype=np.float32)
        
        # Search in FAISS
        scores, indices = self.index.search(query_vector, min(limit * 2, len(self.metadata)))
        
        # Filter and format results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.metadata):
                metadata = self.metadata[idx]
                
                # Filter by course_id if specified
                if course_id is not None and metadata.get('course_id') != course_id:
                    continue
                
                results.append({
                    "id": metadata["id"],
                    "content": metadata["content"],
                    "score": float(score),
                    "course_id": metadata.get("course_id"),
                    "chapter_title": metadata.get("chapter_title"),
                    "chunk_index": metadata.get("chunk_index")
                })
                
                if len(results) >= limit:
                    break
        
        return results
    
    async def get_chunks_by_course_chapter(self, course_id: int, chapter_title: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get chunks for a specific course and optionally chapter."""
        results = []
        
        for metadata in self.metadata:
            if metadata.get('course_id') == course_id:
                if chapter_title is None or metadata.get('chapter_title') == chapter_title:
                    results.append({
                        "id": metadata["id"],
                        "content": metadata["content"],
                        "course_id": metadata.get("course_id"),
                        "chapter_title": metadata.get("chapter_title"),
                        "chunk_index": metadata.get("chunk_index"),
                        "page_number": metadata.get("page_number")
                    })
                    
                    if len(results) >= limit:
                        break
        
        # Sort by chunk_index for consistent ordering
        results.sort(key=lambda x: x.get('chunk_index', 0))
        return results
    
    async def delete_chunks_by_course(self, course_id: int):
        """Delete all chunks for a specific course."""
        # This is a simplified implementation
        # In production, you might want to use FAISS's remove_ids method
        # For now, we'll mark them as deleted in metadata
        
        for metadata in self.metadata:
            if metadata.get('course_id') == course_id:
                metadata['deleted'] = True
        
        self._save_index()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        return {
            "total_chunks": len(self.metadata),
            "index_size": self.index.ntotal if self.index else 0,
            "dimension": self.dimension
        } 