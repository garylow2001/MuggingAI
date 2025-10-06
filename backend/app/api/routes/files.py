import asyncio
import json
import os
import re
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.celery_worker import celery_app
from celery.result import AsyncResult
import redis
import json
from sqlalchemy.orm import Session
from app.models.database import get_db, Course, File as FileModel, Chunk, Topic, Note
from app.models.database import Summary, FileUploadJob
from app.services.chunker import Chunker
from app.services.note_generator import NoteGenerator
from app.services.vector_store import VectorStore
from app.services.summarizer_singleton import get_summarizer
from app.core.config import settings
import uuid
from datetime import datetime
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

# Ensure uploads directory exists
os.makedirs(settings.uploads_dir, exist_ok=True)

# Get logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])


@router.get("/upload/status/{job_id}")
async def get_upload_status(job_id: str):
    redis_client = redis.Redis.from_url(settings.redis_url)
    status_key = f"upload_status:{job_id}"
    status_msgs = redis_client.get(status_key)
    status_list = json.loads(status_msgs) if status_msgs else []
    celery_result: AsyncResult = celery_app.AsyncResult(job_id)
    logger.info(f"Celery status for job {job_id}: {celery_result.status}")
    logger.info(f"Celery raw result for job {job_id}: {celery_result.result}")
    # Wait for result to be ready if status is SUCCESS but result is None
    result_data = None
    if celery_result.status == "SUCCESS":
        result_data = celery_result.result
        if result_data is None:
            logger.warning(f"Result for job {job_id} is None.")
    return {
        "job_id": job_id,
        "status": celery_result.status,
        "progress_messages": status_list,
        "result": result_data,
    }


@router.post("/upload/{course_id}")
async def upload_file(
    course_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Start a job for file upload and processing. Returns job_id immediately."""
    logger.info(f"Starting async file upload for course {course_id}")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        logger.error(f"Course {course_id} not found")
        raise HTTPException(status_code=404, detail="Course not found")

    # Read file bytes
    file_bytes = await file.read()

    logger.info(f"Starting Celery job for file {file.filename}")
    # Enqueue Celery background job
    task = celery_app.send_task(
        "app.tasks.process_file_job.process_file_job",
        args=[course_id, file_bytes, file.filename, file.content_type],
    )
    return {"message": "File upload job started", "job_id": task.id}


@router.get("/{course_id}")
async def get_course_files(course_id: int, db: Session = Depends(get_db)):
    """Get all files for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    files = db.query(FileModel).filter(FileModel.course_id == course_id).all()

    return [
        {
            "id": file.id,
            "filename": file.original_filename,
            "file_type": file.file_type,
            "file_size": file.file_size,
            "created_at": file.created_at,
            "chunks_count": len(file.chunks),
        }
        for file in files
    ]


@router.post("/generate-notes/{course_id}")
async def generate_notes(
    course_id: int, file_id: int | None = None, db: Session = Depends(get_db)
):
    """Generate notes for a course or a specific file. This runs the NoteGenerator over existing chunks
    and saves Topics and Notes into the database. If `file_id` is provided it will only process chunks
    for that file, otherwise it will process all chunks for the course.
    """
    logger.info(f"Starting note generation for course {course_id} file_id={file_id}")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        logger.error(f"Course {course_id} not found for note generation")
        raise HTTPException(status_code=404, detail="Course not found")

    # Get chunks from DB to prepare for note generation
    query = db.query(Chunk).filter(Chunk.course_id == course_id)
    if file_id is not None:
        query = query.filter(Chunk.file_id == file_id)

    db_chunks = query.order_by(Chunk.chunk_index).all()
    if not db_chunks:
        logger.warning("No chunks found to generate notes from")
        raise HTTPException(
            status_code=400, detail="No chunks available for note generation"
        )

    chunks_data = []
    for c in db_chunks:
        chunks_data.append(
            {
                "content": c.content,
                "chunk_index": c.chunk_index,
                "course_id": c.course_id,
                "file_id": c.file_id,
            }
        )

    # Run note generation (may call LLMs and take time)
    note_generator = NoteGenerator()
    try:
        structured_notes = note_generator.process_course_content(chunks_data)
    except Exception as e:
        logger.exception("Note generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Note generation failed: {str(e)}")

    logger.info(f"Generated {len(structured_notes)} structured notes; saving to DB")

    # Save topics and notes to database
    for note_data in structured_notes:
        topic = (
            db.query(Topic)
            .filter(
                Topic.title == note_data["topic_title"], Topic.course_id == course_id
            )
            .first()
        )

        if not topic:
            topic = Topic(
                title=note_data["topic_title"],
                chapter_title=note_data.get("chapter_title"),
                course_id=course_id,
            )
            db.add(topic)
            db.commit()
            db.refresh(topic)

        raw_content = note_data.get("notes_content")

        if isinstance(raw_content, list):
            note_content = "\n".join(
                [f"- {str(item).strip('- ')}" for item in raw_content]
            )
        elif isinstance(raw_content, dict):
            note_content = json.dumps(raw_content, ensure_ascii=False, indent=2)
        elif raw_content is None:
            note_content = ""
        else:
            content_str = str(raw_content)
            if re.search(r"^\s*[-•*]\s", content_str, re.MULTILINE):
                note_content = content_str
            else:
                lines = content_str.strip().split("\n")
                note_content = "\n".join(
                    [f"- {line.strip('- ')}" for line in lines if line.strip()]
                )

        logger.info(
            f"Saving note for topic '%s' (starts: %s)",
            note_data["topic_title"],
            note_content[:50],
        )

        note = Note(content=note_content, topic_id=topic.id, course_id=course_id)
        db.add(note)

    db.commit()

    return {
        "message": "Notes generated and saved",
        "notes_generated": len(structured_notes),
    }


@router.delete("/{file_id}")
async def delete_file(file_id: int, db: Session = Depends(get_db)):
    """Delete a file and all associated data."""
    file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Remove file from disk
        if os.path.exists(file.file_path):
            os.remove(file.file_path)

        # Delete from database (cascade will handle chunks, topics, notes)
        db.delete(file)
        db.commit()

        return {"message": "File deleted successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")
