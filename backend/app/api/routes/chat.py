from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.database import get_db, ChatSession, ChatMessage, Course
from app.services.model_context_provider import ModelContextProvider
from pydantic import BaseModel
from datetime import datetime
import uuid

router = APIRouter()

# Pydantic models
class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    course_id: Optional[int] = None

class ChatMessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatSessionResponse(BaseModel):
    session_id: str
    course_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    message_count: int
    
    class Config:
        from_attributes = True

class ChatResponse(BaseModel):
    session_id: str
    response: str
    processing_time: float

@router.post("/", response_model=ChatResponse)
async def chat_with_tutor(
    request: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """Chat with the AI tutor using RAG."""
    import time
    start_time = time.time()
    
    # Validate course if provided
    if request.course_id:
        course = db.query(Course).filter(Course.id == request.course_id).first()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
    
    # Get or create session
    session_id = request.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        db_session = ChatSession(
            session_id=session_id,
            course_id=request.course_id
        )
        db.add(db_session)
        db.commit()
    else:
        # Validate existing session
        db_session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found"
            )
    
    # Save user message
    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    
    # Use Model Context Provider to get AI response
    mcp = ModelContextProvider()
    
    try:
        ai_response = await mcp.answer_question(
            question=request.message,
            course_id=request.course_id
        )
        
        # Save AI response
        ai_message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=ai_response
        )
        db.add(ai_message)
        
        # Update session timestamp
        db_session.updated_at = datetime.utcnow()
        
        db.commit()
        
        processing_time = time.time() - start_time
        
        return ChatResponse(
            session_id=session_id,
            response=ai_response,
            processing_time=round(processing_time, 2)
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate response: {str(e)}"
        )

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    course_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get chat sessions, optionally filtered by course."""
    query = db.query(ChatSession)
    
    if course_id:
        query = query.filter(ChatSession.course_id == course_id)
    
    sessions = query.order_by(ChatSession.updated_at.desc()).offset(skip).limit(limit).all()
    
    # Add message count to each session
    from sqlalchemy import func
    result = []
    for session in sessions:
        message_count = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.session_id == session.session_id
        ).scalar()
        
        session_data = ChatSessionResponse(
            session_id=session.session_id,
            course_id=session.course_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=message_count
        )
        result.append(session_data)
    
    return result

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get messages for a specific chat session."""
    # Validate session exists
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).offset(skip).limit(limit).all()
    
    return messages

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a chat session and all its messages."""
    # Validate session exists
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Delete all messages first (cascade should handle this, but being explicit)
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    
    # Delete session
    db.delete(session)
    db.commit()
    
    return None

@router.post("/summarize")
async def generate_summary(
    course_id: int,
    chapter_title: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Generate a summary for a course or specific chapter."""
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Use Model Context Provider to generate summary
    mcp = ModelContextProvider()
    
    try:
        summary = await mcp.generate_summary(
            course_id=course_id,
            chapter_title=chapter_title
        )
        
        return {
            "course_id": course_id,
            "chapter_title": chapter_title,
            "summary": summary
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )

@router.post("/key-points")
async def extract_key_points(
    course_id: int,
    chapter_title: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Extract key learning points from course content."""
    # Validate course exists
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Use Model Context Provider to extract key points
    mcp = ModelContextProvider()
    
    try:
        key_points = await mcp.extract_key_points(
            course_id=course_id,
            chapter_title=chapter_title
        )
        
        return {
            "course_id": course_id,
            "chapter_title": chapter_title,
            "key_points": key_points
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract key points: {str(e)}"
        ) 