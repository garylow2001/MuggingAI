import json
import os
import re
import shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.models.database import get_db, Course, File as FileModel, Chunk, Topic, Note
from app.services.chunker import Chunker
from app.services.note_generator import NoteGenerator
from app.services.vector_store import VectorStore
from app.core.config import settings
import uuid
from datetime import datetime
import logging

# Get logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])

# Ensure uploads directory exists
os.makedirs(settings.uploads_dir, exist_ok=True)

@router.post("/upload/{course_id}")
async def upload_file(
    course_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a file to a course and process it for AI analysis.
    Updates the vector store as well as the database (for note generation)."""
    
    logger.info(f"Starting file upload for course {course_id}")
    logger.info(f"File: {file.filename}, Size: {file.size}, Type: {file.content_type}")
    
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        logger.error(f"Course {course_id} not found")
        raise HTTPException(status_code=404, detail="Course not found")

    # Prepare file paths and names
    file_extension = os.path.splitext(file.filename)[1] or ""
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = os.path.join(settings.uploads_dir, unique_filename)

    # Save file to disk
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Log file size
    file_size = os.path.getsize(file_path)
    logger.info(f"File saved successfully. Size: {file_size} bytes")

    # Create file record in database
    db_file = FileModel(
        filename=unique_filename,
        original_filename=file.filename,
        file_path=file_path,
        file_type=file_extension[1:],  # Remove the dot
        file_size=file_size,
        course_id=course_id
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    # Process file content with chunking
    logger.info("Starting file content processing...")
    chunker = Chunker()
    chunks_data = chunker.process_file(file_path, course_id, db_file.id)
    logger.info(f"File processing complete. Created {len(chunks_data)} chunks")
    if not chunks_data:
        raise HTTPException(status_code=500, detail="Failed to process file content")

    # Save chunks to database
    logger.info("Saving chunks to database...")
    chunks = []
    for chunk_data in chunks_data:
        chunk = Chunk(
            content=chunk_data['content'],
            chunk_index=chunk_data['chunk_index'],
            chapter_title=chunk_data.get('chapter_title'),
            page_number=chunk_data.get('page_number'),
            course_id=course_id,
            file_id=db_file.id
        )
        db.add(chunk)
        chunks.append(chunk)
    db.commit()
    logger.info(f"Successfully saved {len(chunks)} chunks to database")

    # Generate embeddings for chunks
    vector_store = VectorStore()
    for chunk in chunks:
        # use async wrapper to avoid blocking in async route
        embedding = await vector_store.get_embedding(chunk.content)
        if not embedding or len(embedding) != vector_store.dimension:
            raise ValueError(f"Invalid embedding length for chunk {chunk.id}: {len(embedding) if embedding else 0}")
        # Store embedding with rich metadata so vector store metadata.json is populated
        chunk.embedding_id = vector_store.store_embedding(
            embedding,
            chunk.id,
            content=chunk.content,
            course_id=chunk.course_id,
            file_id=chunk.file_id,
            chapter_title=chunk.chapter_title,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
        )
    db.commit()

    # Generate AI-powered notes
    note_generator = NoteGenerator()
    structured_notes = note_generator.process_course_content(chunks_data)
    logger.info(f"Generated {len(structured_notes)} structured notes")
    logger.info(f"Structured notes content:\n{json.dumps(structured_notes, ensure_ascii=False, indent=2)}")

    # Save topics and notes to database
    for note_data in structured_notes:
        # Create or find topic
        topic = db.query(Topic).filter(
            Topic.title == note_data['topic_title'],
            Topic.course_id == course_id
        ).first()
        
        if not topic:
            topic = Topic(
                title=note_data['topic_title'],
                chapter_title=note_data['chapter_title'],
                course_id=course_id
            )
            db.add(topic)
            db.commit()
            db.refresh(topic)
        
        # Normalize note content to string for DB storage (avoid list/dict binding errors)
        # Check for both 'notes_content' and 'notes' keys to handle different response formats
        raw_content = note_data.get('notes_content', note_data.get('notes', ''))
        
        # If it's a list, format as bullet points
        if isinstance(raw_content, list):
            # Make sure each item starts with a bullet
            note_content = '\n'.join([
                f"- {str(item).strip('- ')}" for item in raw_content
            ])
        elif isinstance(raw_content, dict):
            # Convert dict to formatted JSON
            note_content = json.dumps(raw_content, ensure_ascii=False, indent=2)
        elif raw_content is None:
            # Empty string for None values
            note_content = ''
        else:
            # Convert to string and ensure proper bullet point formatting
            content_str = str(raw_content)
            
            # If content already has bullet points, keep them as is
            if re.search(r'^\s*[-•*]\s', content_str, re.MULTILINE):
                note_content = content_str
            else:
                # Convert text with newlines to bullet points if not already formatted
                lines = content_str.strip().split('\n')
                note_content = '\n'.join([f"- {line.strip('- ')}" for line in lines if line.strip()])
                
        # Log what we're saving
        logger.info(f"Saving note content for topic '{note_data['topic_title']}', content starts with: {note_content[:50]}...")

        # Create note
        note = Note(
            content=note_content,
            topic_id=topic.id,
            course_id=course_id
        )
        db.add(note)
    db.commit()

    # Get chunk statistics
    chunk_stats = chunker.get_chunk_statistics(chunks_data)
    
    logger.info(f"Upload complete. File ID: {db_file.id}, Chunks: {len(chunks)}, Notes: {len(structured_notes)}")
    
    return {
        "message": "File uploaded and processed successfully",
        "file_id": db_file.id,
        "filename": file.filename,
        "file_size": file_size,
        "chunks_created": len(chunks),
        "notes_generated": len(structured_notes) if 'structured_notes' in locals() else 0,
        "statistics": chunk_stats
    }

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
            "chunks_count": len(file.chunks)
        }
        for file in files
    ]

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