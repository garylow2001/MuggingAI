import logging
from typing import List, Dict, Any, Optional, Union
import json
import re
from cerebras.cloud.sdk import Cerebras
from app.core.config import settings
from app.services.rag_retriever import RAGRetriever
from app.services.vector_store import VectorStore
from app.services.prompts import clean_formatting
from app.models.database import Course, File, get_db

# Get logger for this module
logger = logging.getLogger(__name__)


class RAGService:
    """
    Retrieval-Augmented Generation (RAG) service that combines retrieval with LLM generation.
    """

    def __init__(
        self,
        retriever: Optional[RAGRetriever] = None,
        llm_client: Optional[Cerebras] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ):
        """
        Initialize the RAG service with retriever and LLM components.

        Args:
            retriever: RAG retriever for context fetching
            llm_client: Cerebras client for LLM access
            temperature: LLM temperature parameter
            max_tokens: Maximum tokens for LLM output
        """
        self.retriever = retriever or RAGRetriever()
        self.llm_client = llm_client or Cerebras(api_key=settings.cerebras_api_key)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model = getattr(settings, "cerebras_model", "gpt-oss-120b")
        logger.info(f"Initialized RAG Service with model: {self.model}")

    async def _format_context(self, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Format retrieved context chunks into a string for the LLM.

        Args:
            retrieved_chunks: List of context chunks from retriever

        Returns:
            Formatted context string
        """
        if not retrieved_chunks:
            return ""
        db = next(get_db())

        # Cache lookups to avoid repeated DB queries
        course_cache = {}
        file_cache = {}

        context_parts = []
        for i, chunk in enumerate(retrieved_chunks):
            content = clean_formatting(chunk.get("content", ""))
            course_id = chunk.get("course_id")
            if course_id in course_cache:
                course_name = course_cache[course_id]
            else:
                course = db.query(Course).filter(Course.id == course_id).first()
                course_name = course.name if course else "Unknown"
                course_cache[course_id] = course_name
            file_id = chunk.get("file_id")
            if file_id in file_cache:
                file_name = file_cache[file_id]
            else:
                file = db.query(File).filter(File.id == file_id).first()
                file_name = file.original_filename if file else "Unknown"
                file_cache[file_id] = file_name

            # Format each chunk with metadata
            context_parts.append(
                f"[Document {i+1}] [Course: {course_name}] [File: {file_name}]\n"
                f"{content}\n"
            )

        return "\n\n".join(context_parts)

    def _build_rag_prompt(self, query: str, context: str) -> str:
        """
        Build a RAG prompt combining the user query and retrieved context, requesting a JSON response.

        Args:
            query: User query
            context: Retrieved context

        Returns:
            Full RAG prompt
        """
        if not context:
            return (
                f"Answer the following question based on your knowledge. Respond in the following JSON format:\n\n"
                '{"answer": <answer>}'
                f"\n\nQuestion: {query}\n\n"
            )

        return (
            "Answer the following question based only on the provided context. "
            "Take note of the sources that helped answer the question with the course name, file name, and page number(s) as shown in the context. "
            "Respond in the following JSON format:\n"
            '{"answer": <answer>, "sources": [{"source_course": <course name>, "source_file": <file name>, "source_page": <page number or range>}]}'
            "\nIf the context doesn't contain the information needed, say so - don't make up information.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
        )

    def _post_process_sources(self, sources):
        """
        Remove duplicate or invalid sources from the list.
        """
        seen = set()
        result = []
        for src in sources:
            # Get values using the source_ prefixed keys from LLM response
            course = src.get("source_course")
            file = src.get("source_file")
            page = src.get("source_page")

            # Skip sources with missing or unknown values
            if not course or not file or not page:
                continue
            if "Unknown" in (course, file, page):
                continue

            # Deduplicate based on the combination of all fields
            key = (course, file, page)
            if key not in seen:
                seen.add(key)
                # Create a new source dict with renamed keys for the frontend
                result.append({"course": course, "file": file, "page": page})
        return result

    async def generate(
        self,
        query: str,
        course_ids: Optional[List[int]] = None,
        context_chunks: int = 5,
        use_hybrid_search: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a response to a query using RAG.

        Args:
            query: User query
            course_id: Optional course ID to filter context
            context_chunks: Number of context chunks to retrieve
            use_hybrid_search: Whether to use hybrid search

        Returns:
            Dictionary with generated answer and metadata
        """
        logger.info(f"RAG generation for query: '{query}' (course_ids={course_ids})")

        # Retrieve relevant context from all specified courses
        retrieved_chunks = []
        if course_ids:
            if use_hybrid_search:
                chunks = await self.retriever.hybrid_search(
                    query, course_ids, limit=context_chunks
                )
            else:
                chunks = await self.retriever.retrieve_for_query(
                    query, course_ids, limit=context_chunks
                )
            retrieved_chunks.extend(chunks)
        else:
            # If no course_ids provided, search all courses (or none)
            if use_hybrid_search:
                retrieved_chunks = await self.retriever.hybrid_search(
                    query, None, limit=context_chunks
                )
            else:
                retrieved_chunks = await self.retriever.retrieve_for_query(
                    query, None, limit=context_chunks
                )

        # Format context for the prompt
        context = await self._format_context(retrieved_chunks)

        # Build the full prompt
        prompt = self._build_rag_prompt(query, context)

        # Generate response with LLM
        try:
            logger.debug(f"Sending prompt to LLM: {prompt[:200]}...")

            response = self.llm_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=self.temperature,
                max_completion_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            # Extract answer and sources from LLM JSON response
            raw_content = response.choices[0].message.content.strip()
            logger.debug(f"LLM raw response: {raw_content}")
            try:
                # Try to parse as JSON
                parsed = json.loads(raw_content)
                answer = parsed.get("answer", raw_content)
                sources = parsed.get("sources", [])
            except Exception:
                # Fallback: treat whole output as answer
                logger.warning(
                    "Failed to parse LLM response as JSON; using raw content as answer"
                )
                answer = raw_content
                sources = []

            # Clean, deduplicate, and transform sources to frontend format
            processed_sources = self._post_process_sources(sources)

            return {
                "query": query,
                "answer": answer,
                "sources": processed_sources,  # Already in the right format with course, file, page keys
                "source_count": len(retrieved_chunks),
            }

        except Exception as e:
            logger.error(f"Error generating RAG response: {str(e)}")
            return {
                "query": query,
                "answer": f"Error generating answer: {str(e)}",
                "sources": [],
                "source_count": 0,
                "error": str(e),
            }

    async def answer_with_citations(
        self, query: str, course_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Generate a response with explicit citations to source chunks.

        Args:
            query: User query
            course_id: Optional course ID to filter context

        Returns:
            Dictionary with generated answer and citation metadata
        """
        # Retrieve relevant context (use more chunks for better coverage)
        retrieved_chunks = []
        if course_ids:
            for cid in course_ids:
                chunks = await self.retriever.hybrid_search(query, cid, limit=8)
                retrieved_chunks.extend(chunks)
        else:
            retrieved_chunks = await self.retriever.hybrid_search(query, None, limit=8)

        # Add citation IDs to chunks
        for i, chunk in enumerate(retrieved_chunks):
            chunk["citation_id"] = i + 1

        # Format context with citation IDs
        context_parts = []
        for chunk in retrieved_chunks:
            content = clean_formatting(chunk.get("content", ""))
            chapter = chunk.get("chapter_title", "Unknown")
            citation_id = chunk.get("citation_id")

            context_parts.append(f"[{citation_id}] Chapter: {chapter}\n{content}")

        context = "\n\n".join(context_parts)

        # Build citation-aware prompt
        prompt = (
            f"Answer the following question based on the provided context. "
            f"Include citations to your sources using the format [1], [2], etc. "
            f"If multiple sources support a statement, include all relevant citations like [1,2]. "
            f"If the context doesn't contain the information needed, say so - don't make up information.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            f"Answer (with citations):"
        )

        # Generate response with LLM
        try:
            response = self.llm_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.3,  # Lower temperature for more factual responses
                max_completion_tokens=self.max_tokens,
            )

            # Extract answer
            answer = response.choices[0].message.content.strip()

            # Return with citation metadata
            return {
                "query": query,
                "answer": answer,
                "sources": [
                    {
                        "id": chunk.get("citation_id"),
                        "chapter": chunk.get("chapter_title"),
                        "content": chunk.get("content"),
                        "relevance": chunk.get("score", 0),
                    }
                    for chunk in retrieved_chunks
                ],
                "source_count": len(retrieved_chunks),
            }

        except Exception as e:
            logger.error(f"Error generating cited RAG response: {str(e)}")
            return {
                "query": query,
                "answer": f"Error generating answer: {str(e)}",
                "sources": [],
                "source_count": 0,
                "error": str(e),
            }

    async def generate_follow_up_questions(
        self,
        query: str,
        answer: str,
        course_ids: Optional[List[int]] = None,
        num_questions: int = 3,
    ) -> List[str]:
        """
        Generate follow-up questions based on the query and answer.

        Args:
            query: Original user query
            answer: Generated answer
            course_id: Optional course ID for context
            num_questions: Number of follow-up questions to generate

        Returns:
            List of follow-up questions
        """
        # Build a prompt for generating follow-up questions
        prompt = (
            f"Based on the following question and answer about a course topic, "
            f"generate {num_questions} interesting follow-up questions that would help "
            f"the student deepen their understanding of the subject.\n\n"
            f"Original Question: {query}\n\n"
            f"Answer: {answer}\n\n"
            f"Courses: {course_ids}\n\n"
            f"Follow-up Questions (return as a JSON array of strings):"
        )

        try:
            response = self.llm_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.7,
                max_completion_tokens=256,
                response_format={"type": "json_object"},
            )

            # Extract and parse the response
            content = response.choices[0].message.content.strip()
            questions_json = json.loads(content)
            return questions_json[:num_questions]

        except Exception as e:
            logger.error(f"Error generating follow-up questions: {str(e)}")
            # Default fallback question
            return [f"What else can you tell me about {query}?"]
