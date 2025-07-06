from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.database import get_db, Course
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Pydantic models for request/response
class CourseCreate(BaseModel):
    name: str
    description: Optional[str] = None

class CourseResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class CourseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    """Create a new course."""
    # Check if course with same name already exists
    existing_course = db.query(Course).filter(Course.name == course.name).first()
    if existing_course:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course with this name already exists"
        )
    
    db_course = Course(
        name=course.name,
        description=course.description
    )
    
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    
    return db_course

@router.get("/", response_model=List[CourseResponse])
async def get_courses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all courses with pagination."""
    courses = db.query(Course).offset(skip).limit(limit).all()
    return courses

@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: int, db: Session = Depends(get_db)):
    """Get a specific course by ID."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    return course

@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(course_id: int, course_update: CourseUpdate, db: Session = Depends(get_db)):
    """Update a course."""
    db_course = db.query(Course).filter(Course.id == course_id).first()
    if not db_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if new name conflicts with existing course
    if course_update.name and course_update.name != db_course.name:
        existing_course = db.query(Course).filter(
            Course.name == course_update.name,
            Course.id != course_id
        ).first()
        if existing_course:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Course with this name already exists"
            )
    
    # Update fields
    if course_update.name is not None:
        db_course.name = course_update.name
    if course_update.description is not None:
        db_course.description = course_update.description
    
    db_course.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_course)
    
    return db_course

@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(course_id: int, db: Session = Depends(get_db)):
    """Delete a course and all associated data."""
    db_course = db.query(Course).filter(Course.id == course_id).first()
    if not db_course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Delete the course (cascade will handle related data)
    db.delete(db_course)
    db.commit()
    
    return None 