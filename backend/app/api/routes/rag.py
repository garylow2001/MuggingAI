from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List, Dict, Any
from app.models.database import get_db, Course, Chunk
from app.services.rag_service import RAGService
from app.services.rag_retriever import RAGRetriever
import logging

# Get logger for this module
logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])

@router.get("/query")
async def query_rag(
    query: str,
    course_id: Optional[int] = None,
    context_chunks: int = Query(default=5, ge=1, le=10),
    use_hybrid_search: bool = Query(default=True),
    with_citations: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """
    Query the RAG system with a natural language question.
    
    Args:
        query: The user's question
        course_id: Optional course ID to filter context
        context_chunks: Number of context chunks to retrieve (1-10)
        use_hybrid_search: Whether to use hybrid search
        with_citations: Whether to include citations in the response
        db: Database session
        
    Returns:
        Generated answer with source information
    """
    logger.info(f"RAG query: '{query}' (course_id={course_id})")
    
    # Validate course_id if provided
    if course_id is not None:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
    
    # Initialize RAG service
    rag_service = RAGService()
    
    # Generate response
    if with_citations:
        response = await rag_service.answer_with_citations(query, course_id)
    else:
        response = await rag_service.generate(
            query, 
            course_id, 
            context_chunks=context_chunks,
            use_hybrid_search=use_hybrid_search
        )
    
    # Add follow-up questions if we have an answer
    if response.get("answer") and "error" not in response:
        follow_up_questions = await rag_service.generate_follow_up_questions(
            query, response["answer"], course_id, num_questions=3
        )
        response["follow_up_questions"] = follow_up_questions
    
    return response

@router.get("/search")
async def search_course_content(
    query: str,
    course_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    Search course content using the RAG retriever.
    
    Args:
        query: Search query
        course_id: Course ID to search within
        limit: Maximum number of results
        db: Database session
        
    Returns:
        List of matching content chunks
    """
    # Validate course
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Initialize retriever
    retriever = RAGRetriever()
    
    # Perform hybrid search
    results = await retriever.hybrid_search(query, course_id, limit=limit)
    
    return {
        "query": query,
        "results": results,
        "count": len(results)
    }

@router.get("/courses/{course_id}/chapters")
async def get_course_chapters(
    course_id: int,
    db: Session = Depends(get_db)
):
    """
    Get available chapters for a course.
    
    Args:
        course_id: Course ID
        db: Database session
        
    Returns:
        List of chapter titles
    """
    # Validate course
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Get unique chapter titles from the database
    from sqlalchemy import func
    chapter_rows = db.query(func.distinct(Chunk.chapter_title))\
        .filter(Chunk.course_id == course_id)\
        .all()
    
    chapters = [row[0] for row in chapter_rows if row[0]]
    
    return {
        "course_id": course_id,
        "course_name": course.name,
        "chapters": chapters,
        "chapter_count": len(chapters)
    }

@router.get("/courses/{course_id}/chapters/{chapter_title}/chunks")
async def get_chapter_chunks(
    course_id: int,
    chapter_title: str,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get content chunks for a specific chapter.
    
    Args:
        course_id: Course ID
        chapter_title: Chapter title
        limit: Maximum number of chunks to return
        db: Database session
        
    Returns:
        List of content chunks
    """
    # Validate course
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Initialize retriever
    retriever = RAGRetriever()
    
    # Get chunks by chapter
    chunks = await retriever.retrieve_by_chapter(
        course_id, 
        chapter_title,
        limit=limit
    )
    
    return {
        "course_id": course_id,
        "chapter_title": chapter_title,
        "chunks": chunks,
        "chunk_count": len(chunks)
    }
