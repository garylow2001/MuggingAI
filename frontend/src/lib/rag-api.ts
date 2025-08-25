// Add these types to your api.ts file

export interface RAGResult {
  query: string;
  answer: string;
  sources: RAGSource[];
  source_count: number;
  follow_up_questions?: string[];
  error?: string;
}

export interface RAGSource {
  chapter?: string;
  relevance?: number;
  content_preview?: string;
  id?: number;
  content?: string;
}

export interface RAGSearchResult {
  query: string;
  results: RAGSource[];
  count: number;
}

export interface RAGQueryParams {
  query: string;
  course_id?: number;
  context_chunks?: number;
  use_hybrid_search?: boolean;
  with_citations?: boolean;
}

// Add these methods to your api object

/**
 * Query the RAG system with a natural language question
 */
async function queryRAG(params: RAGQueryParams): Promise<RAGResult> {
  const queryParams = new URLSearchParams();
  queryParams.append("query", params.query);

  if (params.course_id !== undefined) {
    queryParams.append("course_id", params.course_id.toString());
  }

  if (params.context_chunks !== undefined) {
    queryParams.append("context_chunks", params.context_chunks.toString());
  }

  if (params.use_hybrid_search !== undefined) {
    queryParams.append(
      "use_hybrid_search",
      params.use_hybrid_search.toString()
    );
  }

  if (params.with_citations !== undefined) {
    queryParams.append("with_citations", params.with_citations.toString());
  }

  const response = await fetch(
    `${API_BASE_URL}/rag/query?${queryParams.toString()}`
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to query RAG system");
  }

  return response.json();
}

/**
 * Search course content using the RAG retriever
 */
async function searchCourseContent(
  query: string,
  courseId: number,
  limit: number = 5
): Promise<RAGSearchResult> {
  const queryParams = new URLSearchParams({
    query,
    course_id: courseId.toString(),
    limit: limit.toString(),
  });

  const response = await fetch(
    `${API_BASE_URL}/rag/search?${queryParams.toString()}`
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to search course content");
  }

  return response.json();
}

/**
 * Get available chapters for a course
 */
async function getCourseChapters(courseId: number): Promise<{
  course_id: number;
  course_name: string;
  chapters: string[];
  chapter_count: number;
}> {
  const response = await fetch(
    `${API_BASE_URL}/rag/courses/${courseId}/chapters`
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to get course chapters");
  }

  return response.json();
}

/**
 * Get content chunks for a specific chapter
 */
async function getChapterChunks(
  courseId: number,
  chapterTitle: string,
  limit: number = 20
): Promise<{
  course_id: number;
  chapter_title: string;
  chunks: RAGSource[];
  chunk_count: number;
}> {
  const queryParams = new URLSearchParams({
    limit: limit.toString(),
  });

  const response = await fetch(
    `${API_BASE_URL}/rag/courses/${courseId}/chapters/${encodeURIComponent(
      chapterTitle
    )}/chunks?${queryParams.toString()}`
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to get chapter chunks");
  }

  return response.json();
}
