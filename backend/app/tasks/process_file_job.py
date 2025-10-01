import os
import uuid
import shutil
import asyncio
from datetime import datetime
from app.models.database import get_db, File as FileModel, Chunk, Summary, Course
from app.core.config import settings
from app.celery_worker import celery_app
import logging
import redis
import json

logger = logging.getLogger(__name__)
redis_client = redis.Redis.from_url(settings.redis_url)


@celery_app.task(bind=True, ignore_result=False)
def process_file_job(self, course_id, file_bytes, original_filename, content_type):
    # Import ML/GPU-related modules inside the task for macOS fork safety
    from app.services.chunker import Chunker
    from app.services.vector_store import VectorStore
    from app.services.summarizer_singleton import init_summarizer, get_summarizer

    status_key = f"upload_status:{self.request.id}"
    status_msgs = []

    def update_status(msg):
        logger.info(f"Status update: {msg}")
        status_msgs.append(msg)
        redis_client.set(status_key, json.dumps(status_msgs))

    update_status("Saving file to disk and database")
    file_extension = os.path.splitext(original_filename)[1] or ""
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = os.path.join(settings.uploads_dir, unique_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(file_bytes)

    file_size = os.path.getsize(file_path)
    logger.info(f"File saved successfully. Size: {file_size} bytes")

    db = next(get_db())
    db_file = FileModel(
        filename=unique_filename,
        original_filename=original_filename,
        file_path=file_path,
        file_type=file_extension[1:],
        file_size=file_size,
        course_id=course_id,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    update_status("Chunking file content")
    chunker = Chunker()
    chunks_data = chunker.process_file(file_path, course_id, db_file.id)
    logger.info(f"File processing complete. Created {len(chunks_data)} chunks")
    if not chunks_data:
        update_status("Failed to process file content")
        return {"error": "Failed to process file content"}

    chunks: list[Chunk] = []
    for chunk_data in chunks_data:
        chunk = Chunk(
            content=chunk_data["content"],
            chunk_index=chunk_data["chunk_index"],
            page_number=chunk_data.get("page_number"),
            course_id=course_id,
            file_id=db_file.id,
        )
        db.add(chunk)
        chunks.append(chunk)
    db.commit()
    logger.info(f"Successfully saved {len(chunks)} chunks to database")

    update_status("Embedding chunks and storing in vector database")
    vector_store = VectorStore()
    for chunk in chunks:
        embedding = vector_store.create_embedding(chunk.content)
        if not embedding or len(embedding) != vector_store.dimension:
            raise ValueError(
                f"Invalid embedding length for chunk {chunk.id}: {len(embedding) if embedding else 0}"
            )
        chunk.embedding_id = vector_store.store_embedding(
            embedding,
            chunk.id,
            content=chunk.content,
            course_id=chunk.course_id,
            file_id=chunk.file_id,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
        )
    db.commit()
    chunk_stats = chunker.get_chunk_statistics(chunks_data)

    update_status("Summarizing content")
    summaries = []
    try:
        # Ensure summarizer is initialized in this worker process
        init_summarizer()
        summarizer = get_summarizer()
        if summarizer is not None:
            summaries = summarizer.summarize_chunks(chunks_data)
            logger.info(f"Generated summaries for {len(summaries)} chunks")
        else:
            logger.warning("Summarizer not initialized; skipping chunk summarization")
            summaries = []
    except Exception as e:
        logger.exception("Chunk summarization failed: %s", e)
        summaries = []

    try:
        for s in summaries:
            chunk_obj = (
                db.query(Chunk)
                .filter(
                    Chunk.course_id == course_id,
                    Chunk.file_id == s.get("file_id"),
                    Chunk.chunk_index == s.get("chunk_index"),
                )
                .first()
            )
            summary_record = Summary(
                content=s.get("summary") or "",
                chunk_id=chunk_obj.id if chunk_obj else None,
                chunk_index=s.get("chunk_index"),
                file_id=s.get("file_id"),
                course_id=course_id,
            )
            db.add(summary_record)
        db.commit()
    except Exception:
        logger.exception("Failed to persist summaries to database")
        db.rollback()

    update_status("File processing complete")
    logger.info(
        f"File processing complete. File ID: {db_file.id}, Chunks: {len(chunks)}"
    )

    return {
        "message": "File uploaded and processed successfully",
        "file_id": db_file.id,
        "filename": original_filename,
        "file_size": file_size,
        "chunks_created": len(chunks),
        "notes_generated": 0,
        "statistics": chunk_stats,
        "summaries": summaries,
    }
