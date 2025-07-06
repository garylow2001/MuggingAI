from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.database import get_db, File as FileModel, Course
from app.services.chunker import Chunker
from app.services.vector_store import VectorStore
from pydantic import BaseModel
from datetime import datetime
import os
import uuid
from app.core.config import settings

router = APIRouter()

# Pydantic models
class FileResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    course_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class FileUploadResponse(BaseModel):
    file: FileResponse
    chunks_created: int
    processing_time: float

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    course_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a file and process it into chunks."""
    import time
    start_time = time.time()
    
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Validate file type
    allowed_extensions = ['.pdf', '.docx', '.txt']
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Validate file size
    if file.size > settings.max_file_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {settings.max_file_size // (1024*1024)}MB"
        )
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(settings.upload_dir, unique_filename)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Create file record in database
    db_file = FileModel(
        filename=unique_filename,
        original_filename=file.filename,
        file_path=file_path,
        file_type=file_extension[1:],  # Remove the dot
        file_size=file.size,
        course_id=course_id
    )
    
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    # Process file into chunks
    try:
        chunker = Chunker()
        chunks = chunker.process_file(file_path, course_id, db_file.id)
        
        # Add chunks to vector store
        vector_store = VectorStore()
        chunk_ids = await vector_store.add_chunks(chunks)
        
        # Save chunks to database (simplified - in production you might want to batch this)
        from app.models.database import Chunk as ChunkModel
        for chunk_data in chunks:
            db_chunk = ChunkModel(
                content=chunk_data['content'],
                chunk_index=chunk_data['chunk_index'],
                chapter_title=chunk_data.get('chapter_title'),
                page_number=chunk_data.get('page_number'),
                embedding_id=chunk_ids[chunks.index(chunk_data)] if chunk_ids else None,
                course_id=course_id,
                file_id=db_file.id
            )
            db.add(db_chunk)
        
        db.commit()
        
        processing_time = time.time() - start_time
        
        return FileUploadResponse(
            file=db_file,
            chunks_created=len(chunks),
            processing_time=round(processing_time, 2)
        )
        
    except Exception as e:
        # Clean up file if processing fails
        if os.path.exists(file_path):
            os.remove(file_path)
        db.delete(db_file)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}"
        )

@router.get("/course/{course_id}", response_model=List[FileResponse])
async def get_files_by_course(course_id: int, db: Session = Depends(get_db)):
    """Get all files for a specific course."""
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    files = db.query(FileModel).filter(FileModel.course_id == course_id).all()
    return files

@router.get("/{file_id}", response_model=FileResponse)
async def get_file(file_id: int, db: Session = Depends(get_db)):
    """Get a specific file by ID."""
    file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    return file

@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(file_id: int, db: Session = Depends(get_db)):
    """Delete a file and all associated chunks."""
    file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Delete physical file
    if os.path.exists(file.file_path):
        os.remove(file.file_path)
    
    # Delete from vector store (simplified - in production you'd want to remove specific embeddings)
    vector_store = VectorStore()
    await vector_store.delete_chunks_by_course(file.course_id)
    
    # Delete from database (cascade will handle chunks)
    db.delete(file)
    db.commit()
    
    return None 