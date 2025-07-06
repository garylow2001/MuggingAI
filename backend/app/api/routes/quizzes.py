from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from app.models.database import get_db, Quiz as QuizModel, Course
from app.services.model_context_provider import ModelContextProvider
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Pydantic models
class QuizResponse(BaseModel):
    id: int
    question: str
    options: Dict[str, str]
    correct_answer: str
    explanation: str
    chapter_title: Optional[str]
    course_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class QuizGenerateRequest(BaseModel):
    course_id: int
    chapter_title: Optional[str] = None
    num_questions: int = 3

class QuizGenerateResponse(BaseModel):
    quizzes: List[QuizResponse]
    generation_time: float

class QuizAnswerRequest(BaseModel):
    quiz_id: int
    selected_answer: str

class QuizAnswerResponse(BaseModel):
    correct: bool
    correct_answer: str
    explanation: str
    score: int

@router.post("/generate", response_model=QuizGenerateResponse)
async def generate_quizzes(
    request: QuizGenerateRequest,
    db: Session = Depends(get_db)
):
    """Generate MCQs for a specific course and chapter."""
    import time
    start_time = time.time()
    
    # Validate course exists
    course = db.query(Course).filter(Course.id == request.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Use Model Context Provider to generate MCQs
    mcp = ModelContextProvider()
    
    try:
        mcqs = await mcp.generate_mcqs(
            course_id=request.course_id,
            chapter_title=request.chapter_title,
            num_questions=request.num_questions
        )
        
        # Save generated MCQs to database
        saved_quizzes = []
        for mcq in mcqs:
            if "error" in mcq:
                continue  # Skip failed generations
                
            db_quiz = QuizModel(
                question=mcq["question"],
                options=mcq["options"],
                correct_answer=mcq["correct_answer"],
                explanation=mcq["explanation"],
                chapter_title=request.chapter_title,
                course_id=request.course_id
            )
            
            db.add(db_quiz)
            saved_quizzes.append(db_quiz)
        
        db.commit()
        
        # Refresh to get IDs
        for quiz in saved_quizzes:
            db.refresh(quiz)
        
        generation_time = time.time() - start_time
        
        return QuizGenerateResponse(
            quizzes=saved_quizzes,
            generation_time=round(generation_time, 2)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quizzes: {str(e)}"
        )

@router.get("/course/{course_id}", response_model=List[QuizResponse])
async def get_quizzes_by_course(
    course_id: int,
    chapter_title: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get quizzes for a specific course, optionally filtered by chapter."""
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    query = db.query(QuizModel).filter(QuizModel.course_id == course_id)
    
    if chapter_title:
        query = query.filter(QuizModel.chapter_title == chapter_title)
    
    quizzes = query.order_by(QuizModel.created_at.desc()).offset(skip).limit(limit).all()
    return quizzes

@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(quiz_id: int, db: Session = Depends(get_db)):
    """Get a specific quiz by ID."""
    quiz = db.query(QuizModel).filter(QuizModel.id == quiz_id).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    return quiz

@router.post("/{quiz_id}/answer", response_model=QuizAnswerResponse)
async def answer_quiz(
    quiz_id: int,
    answer: QuizAnswerRequest,
    db: Session = Depends(get_db)
):
    """Submit an answer to a quiz and get feedback."""
    quiz = db.query(QuizModel).filter(QuizModel.id == quiz_id).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    # Validate answer format
    if answer.selected_answer not in quiz.options:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid answer option"
        )
    
    # Check if answer is correct
    is_correct = answer.selected_answer == quiz.correct_answer
    score = 100 if is_correct else 0
    
    return QuizAnswerResponse(
        correct=is_correct,
        correct_answer=quiz.correct_answer,
        explanation=quiz.explanation,
        score=score
    )

@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(quiz_id: int, db: Session = Depends(get_db)):
    """Delete a specific quiz."""
    quiz = db.query(QuizModel).filter(QuizModel.id == quiz_id).first()
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    db.delete(quiz)
    db.commit()
    
    return None

@router.get("/course/{course_id}/stats")
async def get_quiz_stats(course_id: int, db: Session = Depends(get_db)):
    """Get statistics for quizzes in a course."""
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    from sqlalchemy import func
    
    # Get basic stats
    total_quizzes = db.query(func.count(QuizModel.id)).filter(
        QuizModel.course_id == course_id
    ).scalar()
    
    unique_chapters = db.query(func.count(func.distinct(QuizModel.chapter_title))).filter(
        QuizModel.course_id == course_id,
        QuizModel.chapter_title.isnot(None)
    ).scalar()
    
    # Get quizzes by chapter
    quizzes_by_chapter = db.query(
        QuizModel.chapter_title,
        func.count(QuizModel.id).label('quiz_count')
    ).filter(
        QuizModel.course_id == course_id,
        QuizModel.chapter_title.isnot(None)
    ).group_by(QuizModel.chapter_title).all()
    
    return {
        "course_id": course_id,
        "total_quizzes": total_quizzes,
        "unique_chapters": unique_chapters,
        "quizzes_by_chapter": [
            {"chapter": item.chapter_title, "count": item.quiz_count}
            for item in quizzes_by_chapter
        ]
    } 