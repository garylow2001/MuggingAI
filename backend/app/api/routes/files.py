import os
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

router = APIRouter(prefix="/files", tags=["files"])

# Ensure uploads directory exists
os.makedirs(settings.uploads_dir, exist_ok=True)

@router.post("/upload/{course_id}")
async def upload_file(
    course_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a file to a course and process it for AI analysis."""
    
    print(f"Starting file upload for course {course_id}")
    print(f"File: {file.filename}, Size: {file.size}, Type: {file.content_type}")
    
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        print(f"Course {course_id} not found")
        raise HTTPException(status_code=404, detail="Course not found")
    
    print(f"Course found: {course.name}")
    
    # Validate file type
    allowed_extensions = {'.pdf', '.docx', '.txt'}
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Validate file size
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size / (1024*1024):.1f}MB"
        )
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.uploads_dir, unique_filename)
    
    print(f"Saving file to: {file_path}")
    
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        print(f"File saved successfully. Size: {file_size} bytes")
        
        # Create file record in database
        try:
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
        except Exception as e:
            print(f"Error creating file record: {e}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        # Process file content
        try:
            print("Starting file content processing...")
            chunker = Chunker()
            chunks_data = chunker.process_file(file_path, course_id, db_file.id)
            
            print(f"File processing complete. Created {len(chunks_data)} chunks")
            
            if not chunks_data:
                raise HTTPException(status_code=500, detail="Failed to process file content")
        except Exception as e:
            print(f"Error processing file content: {e}")
            raise HTTPException(status_code=500, detail=f"File processing error: {str(e)}")
        
        # Save chunks to database
        try:
            print("Saving chunks to database...")
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
            print(f"Successfully saved {len(chunks)} chunks to database")
        except Exception as e:
            print(f"Error saving chunks: {e}")
            raise HTTPException(status_code=500, detail=f"Database error saving chunks: {str(e)}")
        
        # Generate embeddings for chunks
        try:
            vector_store = VectorStore()
            for chunk in chunks:
                try:
                    embedding = vector_store.create_embedding(chunk.content)
                    chunk.embedding_id = vector_store.store_embedding(embedding, chunk.id)
                except Exception as e:
                    print(f"Warning: Failed to generate embedding for chunk {chunk.id}: {e}")
                    # Continue with other chunks even if one fails
            
            db.commit()
        except Exception as e:
            print(f"Warning: Failed to initialize vector store: {e}")
            # Continue without embeddings if vector store fails
        
        # Generate AI-powered notes
        structured_notes = []
        try:
            note_generator = NoteGenerator()
            structured_notes = note_generator.process_course_content(chunks_data)
            
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
                
                # Create note
                note = Note(
                    content=note_data['notes_content'],
                    topic_id=topic.id,
                    course_id=course_id
                )
                db.add(note)
            
            db.commit()
        except Exception as e:
            print(f"Warning: Failed to generate notes: {e}")
            # Continue even if note generation fails
        
        # Get chunk statistics
        chunk_stats = chunker.get_chunk_statistics(chunks_data)
        
        print(f"Upload complete. File ID: {db_file.id}, Chunks: {len(chunks)}, Notes: {len(structured_notes)}")
        
        return {
            "message": "File uploaded and processed successfully",
            "file_id": db_file.id,
            "filename": file.filename,
            "file_size": file_size,
            "chunks_created": len(chunks),
            "notes_generated": len(structured_notes) if 'structured_notes' in locals() else 0,
            "statistics": chunk_stats
        }
        
    except Exception as e:
        # Clean up file if processing failed
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Rollback database changes
        db.rollback()
        
        # Log the error for debugging
        print(f"Error processing file {file.filename}: {str(e)}")
        
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

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