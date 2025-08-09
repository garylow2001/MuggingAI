from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, HTTPException
from sqlalchemy.orm import Session
from app.models.database import get_db, Course, Topic, Note
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/notes", tags=["notes"])

# Pydantic models
class TopicResponse(BaseModel):
    id: int
    title: str
    chapter_title: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class NoteResponse(BaseModel):
    id: int
    content: str
    topic_id: int
    course_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class NoteUpdate(BaseModel):
    content: str

class NoteCreate(BaseModel):
    content: str
    topic_id: int

@router.get("/course/{course_id}")
async def get_course_notes(course_id: int, db: Session = Depends(get_db)):
    """Get all notes for a course, organized by topics and chapters."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get topics with their notes
    topics = db.query(Topic).filter(Topic.course_id == course_id).all()
    
    result = []
    for topic in topics:
        topic_notes = db.query(Note).filter(Note.topic_id == topic.id).all()
        
        result.append({
            "topic": TopicResponse.from_orm(topic),
            "notes": [NoteResponse.from_orm(note) for note in topic_notes]
        })
    
    return result

@router.get("/topic/{topic_id}")
async def get_topic_notes(topic_id: int, db: Session = Depends(get_db)):
    """Get all notes for a specific topic."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    notes = db.query(Note).filter(Note.topic_id == topic_id).all()
    return [NoteResponse.from_orm(note) for note in notes]

@router.put("/{note_id}")
async def update_note(note_id: int, note_update: NoteUpdate, db: Session = Depends(get_db)):
    """Update a note's content."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    note.content = note_update.content
    note.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(note)
    
    return NoteResponse.from_orm(note)

@router.post("/")
async def create_note(note_create: NoteCreate, db: Session = Depends(get_db)):
    """Create a new note."""
    # Verify topic exists
    topic = db.query(Topic).filter(Topic.id == note_create.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    note = Note(
        content=note_create.content,
        topic_id=note_create.topic_id,
        course_id=topic.course_id
    )
    
    db.add(note)
    db.commit()
    db.refresh(note)
    
    return NoteResponse.from_orm(note)

@router.delete("/{note_id}")
async def delete_note(note_id: int, db: Session = Depends(get_db)):
    """Delete a note."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    db.delete(note)
    db.commit()
    
    return {"message": "Note deleted successfully"}

@router.get("/chapters/{course_id}")
async def get_course_chapters(course_id: int, db: Session = Depends(get_db)):
    """Get all chapters for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get unique chapter titles
    chapters = db.query(Topic.chapter_title).filter(
        Topic.course_id == course_id,
        Topic.chapter_title.isnot(None)
    ).distinct().all()
    
    return [{"title": chapter[0]} for chapter in chapters if chapter[0]]
