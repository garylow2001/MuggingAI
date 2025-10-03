from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
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


class RagQueryRequest(BaseModel):
    query: str
    course_ids: List[int]
    context_chunks: int = 3
    use_hybrid_search: bool = True
    with_citations: bool = False


@router.post("/query")
async def query_rag(
    payload: RagQueryRequest,
    db: Session = Depends(get_db),
):
    """
    Query the RAG system with a natural language question.

    Args (in RAGQueryRequest):
        query: The user's question
        course_ids: List of course IDs to filter context
        context_chunks: Number of context chunks to retrieve
        use_hybrid_search: Whether to use hybrid search
        with_citations: Whether to include citations in the response
        db: Database session

    Returns:
        Generated answer with source information
    """
    logger.info(f"RAG query: '{payload.query}' (course_ids={payload.course_ids})")

    # Validate course_ids
    valid_courses = db.query(Course).filter(Course.id.in_(payload.course_ids)).all()
    if len(valid_courses) != len(payload.course_ids):
        raise HTTPException(status_code=404, detail="One or more courses not found")

    rag_service = RAGService()

    # Generate response (update your RAG logic to handle multiple course_ids if needed)
    if payload.with_citations:
        response = await rag_service.answer_with_citations(
            payload.query, payload.course_ids
        )
    else:
        response = await rag_service.generate(
            payload.query,
            payload.course_ids,
            context_chunks=payload.context_chunks,
            use_hybrid_search=payload.use_hybrid_search,
        )

    # Add follow-up questions if we have an answer
    if response.get("answer") and "error" not in response:
        follow_up_questions = await rag_service.generate_follow_up_questions(
            payload.query, response["answer"], payload.course_ids, num_questions=3
        )
        response["follow_up_questions"] = follow_up_questions

    return response


@router.get("/search")
async def search_course_content(
    query: str,
    course_ids: List[int] = Query(..., description="Course IDs to search within"),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Search course content using the RAG retriever.

    Args:
        query: Search query
        course_ids: Course IDs to search within
        limit: Maximum number of results
        db: Database session

    Returns:
        List of matching content chunks
    """
    # Validate courses
    valid_courses = db.query(Course).filter(Course.id.in_(course_ids)).all()
    if len(valid_courses) != len(course_ids):
        raise HTTPException(status_code=404, detail="One or more courses not found")

    # Initialize retriever
    retriever = RAGRetriever()

    # Perform hybrid search
    results = await retriever.hybrid_search(query, course_ids, limit=limit)

    return {"query": query, "results": results, "count": len(results)}


@router.get("/courses/chapters")
async def get_course_chapters(
    course_ids: List[int] = Query(..., description="Course IDs to get chapters from"),
    db: Session = Depends(get_db),
):
    """
    Get available chapters for courses.

    Args:
        course_ids: Course IDs
        db: Database session

    Returns:
        List of chapter titles grouped by course
    """
    # Validate courses
    valid_courses = db.query(Course).filter(Course.id.in_(course_ids)).all()
    if len(valid_courses) != len(course_ids):
        raise HTTPException(status_code=404, detail="One or more courses not found")

    courses_map = {course.id: course for course in valid_courses}
    results = []

    # Get unique chapter titles for each course
    for course_id in course_ids:
        course = courses_map[course_id]

        chapter_rows = (
            db.query(func.distinct(Chunk.chapter_title))
            .filter(Chunk.course_id == course_id)
            .all()
        )

        chapters = [row[0] for row in chapter_rows if row[0]]

        results.append(
            {
                "course_id": course_id,
                "course_name": course.name,
                "chapters": chapters,
                "chapter_count": len(chapters),
            }
        )

    return results


@router.get("/courses/chapters/{chapter_title}/chunks")
async def get_chapter_chunks(
    chapter_title: str,
    course_ids: List[int] = Query(..., description="Course IDs to get chunks from"),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Get content chunks for a specific chapter across multiple courses.

    Args:
        chapter_title: Chapter title
        course_ids: List of course IDs
        limit: Maximum number of chunks to return per course
        db: Database session

    Returns:
        List of content chunks
    """
    # Validate courses
    valid_courses = db.query(Course).filter(Course.id.in_(course_ids)).all()
    if len(valid_courses) != len(course_ids):
        raise HTTPException(status_code=404, detail="One or more courses not found")

    # Initialize retriever
    retriever = RAGRetriever()

    # Get chunks by chapter for all requested courses
    chunks = await retriever.retrieve_by_chapter(course_ids, chapter_title, limit=limit)

    return {
        "course_ids": course_ids,
        "chapter_title": chapter_title,
        "chunks": chunks,
        "chunk_count": len(chunks),
    }
