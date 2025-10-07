import logging
from typing import List, Dict, Any, Optional, Union
from app.services.vector_store import VectorStore
import asyncio
import re
from collections import Counter

# Get logger for this module
logger = logging.getLogger(__name__)


class RAGRetriever:
    """
    Retrieval component for Retrieval-Augmented Generation (RAG).
    Fetches relevant context from the vector store based on queries.
    """

    def __init__(self, vector_store: Optional[VectorStore] = None):
        """Initialize the retriever with a vector store instance."""
        self.vector_store = vector_store or VectorStore()
        logger.info("Initialized RAG Retriever with vector store")

    async def retrieve_for_query(
        self,
        query: str,
        course_ids: Optional[List[int]] = None,
        limit: int = 5,
        rerank: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context chunks for a given query.

        Args:
            query: The search query
            course_id: Optional course ID to filter results
            limit: Maximum number of results to return
            rerank: Whether to rerank results based on query relevance

        Returns:
            List of context chunks with content and metadata
        """
        logger.info(
            f"Retrieving context for query: '{query}' (course_ids={course_ids}, limit={limit})"
        )

        # Search the vector store with the query for all courses
        all_results = await self.vector_store.search(query, course_ids, limit=limit * 2)

        if not all_results:
            logger.warning(f"No results found for query: '{query}'")
            return []

        if rerank:
            # Rerank results based on additional relevance signals
            reranked_results = self._rerank_results(query, all_results)
            results = reranked_results[:limit]
        else:
            # Use original vector similarity order
            results = all_results[:limit]

        logger.info(f"Retrieved {len(results)} context chunks for query")
        return results

    def _rerank_results(
        self, query: str, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rerank search results based on additional relevance signals.

        Args:
            query: The original search query
            results: Initial search results from vector store

        Returns:
            Reranked results
        """
        if not results:
            return []

        # Extract query keywords (simple approach)
        query_terms = set(re.findall(r"\b\w+\b", query.lower()))
        query_terms = {
            term for term in query_terms if len(term) > 2
        }  # Filter short terms

        # Score each result with additional signals
        scored_results = []
        for result in results:
            # Start with vector similarity score
            base_score = result.get("score", 0)

            # Calculate keyword match score
            content = result.get("content", "").lower()
            keyword_matches = sum(1 for term in query_terms if term in content)
            keyword_score = keyword_matches / max(1, len(query_terms))

            # Calculate exact phrase match score
            exact_phrase_score = 0
            if len(query) > 5:  # Only for non-trivial queries
                if query.lower() in content:
                    exact_phrase_score = 0.5

            # Combine scores (weighted sum)
            combined_score = (
                base_score * 0.6  # Vector similarity
                + keyword_score * 0.3  # Keyword matches
                + exact_phrase_score * 0.1  # Exact phrase match
            )

            scored_results.append((combined_score, result))

        # Sort by combined score
        scored_results.sort(reverse=True, key=lambda x: x[0])
        return [item for _, item in scored_results]

    async def retrieve_multi_query(
        self,
        queries: List[str],
        course_ids: Optional[List[int]] = None,
        limit_per_query: int = 3,
        total_limit: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context using multiple query variations to improve recall.

        Args:
            queries: List of query variations
            course_ids: Optional course IDs to filter results
            limit_per_query: Maximum results per individual query
            total_limit: Maximum total results to return

        Returns:
            Combined and deduplicated list of context chunks
        """
        logger.info(f"Running multi-query retrieval with {len(queries)} queries")

        # Gather results from all queries in parallel for all courses
        tasks = [
            self.retrieve_for_query(q, course_ids, limit=limit_per_query)
            for q in queries
        ]
        results = await asyncio.gather(*tasks)
        flat_results = [item for sublist in results for item in sublist]

        # Deduplicate by ID
        seen_ids = set()
        unique_results = []
        for result in flat_results:
            result_id = result.get("id")
            if result_id not in seen_ids:
                seen_ids.add(result_id)
                unique_results.append(result)

        # Return top results up to total_limit
        return unique_results[:total_limit]

    async def retrieve_by_chapter(
        self,
        course_ids: Optional[List[int]] = None,
        chapter_title: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context chunks by chapter for a specific course.

        Args:
            course_ids: The course IDs
            chapter_title: Optional chapter title to filter by
            limit: Maximum number of chunks to retrieve

        Returns:
            List of context chunks for the specified chapter
        """
        logger.info(
            f"Retrieving context chunks for courses {course_ids}, "
            + f"chapter {'all chapters' if chapter_title is None else chapter_title}"
        )

        # Get chunks directly from vector store for all courses
        all_chunks = await self.vector_store.get_chunks_by_course_chapter(
            course_ids, chapter_title, limit
        )

        return all_chunks

    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Extract important keywords from text for query expansion.

        Args:
            text: The text to extract keywords from
            max_keywords: Maximum number of keywords to extract

        Returns:
            List of extracted keywords
        """
        # Simple keyword extraction based on word frequency
        # In a production system, you might use a more sophisticated approach

        # Tokenize and clean
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

        # Filter common words
        stopwords = {
            "the",
            "and",
            "that",
            "this",
            "with",
            "for",
            "from",
            "you",
            "are",
            "but",
            "not",
            "have",
            "what",
            "can",
            "all",
            "will",
        }
        filtered_words = [w for w in words if w not in stopwords]

        # Count word frequency
        word_counts = Counter(filtered_words)

        # Get most common words
        keywords = [word for word, _ in word_counts.most_common(max_keywords)]

        return keywords

    async def hybrid_search(
        self, query: str, course_ids: Optional[List[int]] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search using both vector and keyword matching.

        Args:
            query: The search query
            course_ids: Optional course IDs to filter results
            limit: Maximum number of results to return

        Returns:
            List of context chunks from hybrid search
        """
        # Extract query keywords
        keywords = self._extract_keywords(query)

        # Create query variations
        query_variations = [query]  # Original query

        # Add a keyword-focused variation if we have keywords
        if len(keywords) >= 2:
            keyword_query = " ".join(keywords[:5])  # Use top 5 keywords
            query_variations.append(keyword_query)

        # Run multi-query retrieval with variations
        results = await self.retrieve_multi_query(
            query_variations, course_ids, limit_per_query=limit, total_limit=limit
        )

        return results
