from typing import List, Dict, Any, Optional
import openai
from app.core.config import settings
from app.services.vector_store import VectorStore
import json

class ModelContextProvider:
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.vector_store = VectorStore()
        
        # Prompt templates for different tasks
        self.prompts = {
            "summarize": {
                "system": """You are an expert educational content summarizer. Your task is to create clear, concise summaries of educational materials that highlight key learning points.

Guidelines:
- Focus on the most important concepts and ideas
- Use clear, academic language
- Organize information logically
- Include key definitions and examples
- Keep summaries concise but comprehensive
- Highlight main takeaways for students""",
                
                "user_template": """Please create a comprehensive summary of the following educational content. Focus on the key learning points and main concepts:

{content}

Please structure your response as:
1. Main Concepts
2. Key Definitions
3. Important Examples
4. Key Takeaways"""
            },
            
            "mcq_generation": {
                "system": """You are an expert educational quiz creator. Your task is to generate high-quality multiple choice questions based on educational content.

Guidelines:
- Create questions that test understanding, not just memorization
- Ensure all options are plausible
- Provide clear, educational explanations for correct answers
- Focus on key concepts and important details
- Use academic language appropriate for the content level
- Generate exactly the requested number of questions""",
                
                "user_template": """Based on the following educational content, generate {num_questions} multiple choice questions. Each question should have 4 options (A, B, C, D) and include an explanation for the correct answer.

Content:
{content}

Please format your response as a JSON array with the following structure:
[
  {{
    "question": "Question text here?",
    "options": {{
      "A": "Option A text",
      "B": "Option B text", 
      "C": "Option C text",
      "D": "Option D text"
    }},
    "correct_answer": "A",
    "explanation": "Explanation of why this answer is correct"
  }}
]"""
            },
            
            "qa": {
                "system": """You are an expert educational tutor. Your task is to answer questions based on the provided educational content.

Guidelines:
- Base your answers only on the provided content
- If the content doesn't contain information to answer the question, say so
- Provide clear, educational explanations
- Use examples from the content when helpful
- Maintain an encouraging, supportive tone
- Structure your answers logically""",
                
                "user_template": """Based on the following educational content, please answer this question: {question}

Content:
{content}

Please provide a comprehensive answer that directly addresses the question using information from the provided content."""
            }
        }
    
    async def get_relevant_context(self, course_id: int, chapter_title: Optional[str] = None, query: Optional[str] = None, limit: int = 5) -> str:
        """Retrieve relevant context from vector store based on course, chapter, and optional query."""
        if query:
            # Semantic search based on query
            results = await self.vector_store.search(query, course_id=course_id, limit=limit)
        else:
            # Get chunks by course and chapter
            results = await self.vector_store.get_chunks_by_course_chapter(course_id, chapter_title, limit=limit)
        
        if not results:
            return "No relevant content found."
        
        # Combine content from top results
        context_parts = []
        for result in results:
            if hasattr(result, 'content'):
                context_parts.append(result.content)
            elif isinstance(result, dict):
                context_parts.append(result.get('content', ''))
        
        return "\n\n".join(context_parts)
    
    async def generate_summary(self, course_id: int, chapter_title: Optional[str] = None) -> str:
        """Generate a summary for a specific course chapter."""
        context = await self.get_relevant_context(course_id, chapter_title, limit=7)
        
        response = await self.client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": self.prompts["summarize"]["system"]},
                {"role": "user", "content": self.prompts["summarize"]["user_template"].format(content=context)}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    
    async def generate_mcqs(self, course_id: int, chapter_title: Optional[str] = None, num_questions: int = 3) -> List[Dict[str, Any]]:
        """Generate multiple choice questions for a specific course chapter."""
        context = await self.get_relevant_context(course_id, chapter_title, limit=7)
        
        response = await self.client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": self.prompts["mcq_generation"]["system"]},
                {"role": "user", "content": self.prompts["mcq_generation"]["user_template"].format(
                    content=context, num_questions=num_questions
                )}
            ],
            temperature=0.4,
            max_tokens=2000
        )
        
        try:
            # Parse JSON response
            content = response.choices[0].message.content
            # Extract JSON from the response (in case there's extra text)
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            json_str = content[start_idx:end_idx]
            
            mcqs = json.loads(json_str)
            return mcqs
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: return a simple error message
            return [{"error": f"Failed to generate MCQs: {str(e)}"}]
    
    async def answer_question(self, question: str, course_id: int, chapter_title: Optional[str] = None) -> str:
        """Answer a question based on course content using RAG."""
        context = await self.get_relevant_context(course_id, chapter_title, query=question, limit=5)
        
        response = await self.client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": self.prompts["qa"]["system"]},
                {"role": "user", "content": self.prompts["qa"]["user_template"].format(
                    question=question, content=context
                )}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    
    async def extract_key_points(self, course_id: int, chapter_title: Optional[str] = None) -> List[str]:
        """Extract key learning points from course content."""
        context = await self.get_relevant_context(course_id, chapter_title, limit=7)
        
        response = await self.client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "You are an expert at identifying key learning points from educational content. Extract the most important concepts, definitions, and takeaways."},
                {"role": "user", "content": f"From the following content, extract 5-7 key learning points:\n\n{context}\n\nFormat as a numbered list."}
            ],
            temperature=0.2,
            max_tokens=800
        )
        
        content = response.choices[0].message.content
        # Parse numbered list into array
        points = [point.strip() for point in content.split('\n') if point.strip() and (point.strip()[0].isdigit() or point.strip().startswith('-'))]
        return points 