from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.database import get_db, Chunk as ChunkModel, Course
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Pydantic models
class ChunkResponse(BaseModel):
    id: int
    content: str
    chunk_index: int
    chapter_title: Optional[str]
    page_number: Optional[int]
    course_id: int
    file_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChapterInfo(BaseModel):
    title: str
    chunk_count: int
    first_chunk_id: int

@router.get("/course/{course_id}", response_model=List[ChunkResponse])
async def get_chunks_by_course(
    course_id: int, 
    chapter_title: Optional[str] = None,
    skip: int = 0, 
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get chunks for a specific course, optionally filtered by chapter."""
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    query = db.query(ChunkModel).filter(ChunkModel.course_id == course_id)
    
    if chapter_title:
        query = query.filter(ChunkModel.chapter_title == chapter_title)
    
    chunks = query.order_by(ChunkModel.chunk_index).offset(skip).limit(limit).all()
    return chunks

@router.get("/course/{course_id}/chapters", response_model=List[ChapterInfo])
async def get_chapters_by_course(course_id: int, db: Session = Depends(get_db)):
    """Get all chapters for a specific course."""
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Get unique chapters with their chunk counts
    from sqlalchemy import func
    chapters = db.query(
        ChunkModel.chapter_title,
        func.count(ChunkModel.id).label('chunk_count'),
        func.min(ChunkModel.id).label('first_chunk_id')
    ).filter(
        ChunkModel.course_id == course_id,
        ChunkModel.chapter_title.isnot(None)
    ).group_by(ChunkModel.chapter_title).all()
    
    return [
        ChapterInfo(
            title=chapter.chapter_title,
            chunk_count=chapter.chunk_count,
            first_chunk_id=chapter.first_chunk_id
        )
        for chapter in chapters
    ]

@router.get("/{chunk_id}", response_model=ChunkResponse)
async def get_chunk(chunk_id: int, db: Session = Depends(get_db)):
    """Get a specific chunk by ID."""
    chunk = db.query(ChunkModel).filter(ChunkModel.id == chunk_id).first()
    if not chunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chunk not found"
        )
    return chunk

@router.get("/course/{course_id}/search")
async def search_chunks(
    course_id: int,
    query: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Search chunks within a course using semantic search."""
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Use vector store for semantic search
    from app.services.vector_store import VectorStore
    vector_store = VectorStore()
    
    try:
        results = await vector_store.search(query, course_id=course_id, limit=limit)
        return {
            "query": query,
            "results": results,
            "total_found": len(results)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

@router.get("/course/{course_id}/stats")
async def get_course_stats(course_id: int, db: Session = Depends(get_db)):
    """Get statistics for a course's chunks."""
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    from sqlalchemy import func
    
    # Get basic stats
    total_chunks = db.query(func.count(ChunkModel.id)).filter(
        ChunkModel.course_id == course_id
    ).scalar()
    
    unique_chapters = db.query(func.count(func.distinct(ChunkModel.chapter_title))).filter(
        ChunkModel.course_id == course_id,
        ChunkModel.chapter_title.isnot(None)
    ).scalar()
    
    # Get total word count (approximate)
    chunks = db.query(ChunkModel.content).filter(ChunkModel.course_id == course_id).all()
    total_words = sum(len(chunk.content.split()) for chunk in chunks)
    
    return {
        "course_id": course_id,
        "total_chunks": total_chunks,
        "unique_chapters": unique_chapters,
        "total_words": total_words,
        "average_chunk_size": round(total_words / total_chunks, 2) if total_chunks > 0 else 0
    } 