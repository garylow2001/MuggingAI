import logging
from typing import List, Dict, Any, Optional, Union
import json
import re
from cerebras.cloud.sdk import Cerebras
from app.core.config import settings
from app.services.rag_retriever import RAGRetriever
from app.services.vector_store import VectorStore
from app.services.prompts import clean_formatting

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

        context_parts = []
        for i, chunk in enumerate(retrieved_chunks):
            content = clean_formatting(chunk.get("content", ""))
            chapter = chunk.get("chapter_title", "Unknown")

            # Format each chunk with metadata
            context_parts.append(
                f"[Document {i+1}] Chapter: {chapter}\n" f"{content}\n"
            )

        return "\n\n".join(context_parts)

    def _build_rag_prompt(self, query: str, context: str) -> str:
        """
        Build a RAG prompt combining the user query and retrieved context.

        Args:
            query: User query
            context: Retrieved context

        Returns:
            Full RAG prompt
        """
        if not context:
            # If no context, use a standard prompt
            return (
                f"Answer the following question based on your knowledge:\n\n"
                f"Question: {query}\n\n"
                f"Answer:"
            )

        # Build RAG prompt with context
        return (
            f"Answer the following question based only on the provided context. "
            f"If the context doesn't contain the information needed, say so - don't make up information.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            f"Answer:"
        )

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
            )

            # Extract answer
            answer = response.choices[0].message.content.strip()

            logger.info(f"Generated RAG answer ({len(answer)} chars)")

            # Return with metadata
            return {
                "query": query,
                "answer": answer,
                "sources": [
                    {
                        "chapter": chunk.get("chapter_title"),
                        "relevance": chunk.get("score", 0),
                        "content_preview": chunk.get("content", "")[:100] + "...",
                    }
                    for chunk in retrieved_chunks
                ],
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
            )

            # Extract and parse the response
            content = response.choices[0].message.content.strip()

            # Try to extract a JSON array
            match = re.search(r"\[(.*)\]", content, re.DOTALL)
            if match:
                try:
                    # Try to parse as JSON
                    questions_json = json.loads(f"[{match.group(1)}]")
                    return questions_json[:num_questions]
                except json.JSONDecodeError:
                    # Fallback to regex extraction
                    pass

            # Fallback: extract questions based on numbering
            questions = re.findall(r"(?:\d+\.|\-)\s*(.+?)(?=\n\d+\.|\n\-|$)", content)
            if questions:
                return questions[:num_questions]

            # Final fallback: split by newlines
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            return lines[:num_questions]

        except Exception as e:
            logger.error(f"Error generating follow-up questions: {str(e)}")
            return [f"What else can you tell me about {query}?"]
