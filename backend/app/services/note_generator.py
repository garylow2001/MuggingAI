from cerebras.cloud.sdk import Cerebras
from typing import List, Dict, Any, Optional
from app.core.config import settings
import json
import re
import logging

# Get logger for this module
logger = logging.getLogger(__name__)

class NoteGenerator:
    def __init__(self, client=None):
        self.client = client or Cerebras(api_key=settings.cerebras_api_key)
    
    def extract_topics_and_chapters(self, text: str) -> List[Dict[str, Any]]:
        """Extract topics and chapters from text using AI."""
        try:
            prompt = f"""
            Analyze the following text and extract the main topics and chapters. 
            Return a JSON structure with the following format:
            {{
                "chapters": [
                    {{
                        "title": "Chapter Title",
                        "topics": [
                            {{
                                "title": "Topic Title",
                                "description": "Brief description of what this topic covers"
                            }}
                        ]
                    }}
                ]
            }}
            
            Text to analyze:
            {text[:4000]}  # Limit text length for API call
            
            Focus on identifying clear chapter divisions and main topics within each chapter.
            """
            
            stream = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing educational content and extracting structured information."},
                    {"role": "user", "content": prompt}
                ],
                model=settings.cerebras_model,
                stream=True,
                max_completion_tokens=1000,
                temperature=0.3,
                top_p=1
            )
            content = ""
            for chunk in stream:
                content += chunk.choices[0].delta.content or ""
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback: create basic structure
                return self._create_fallback_structure(text)
                
        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            return self._create_fallback_structure(text)
    
    def _create_fallback_structure(self, text: str) -> Dict[str, Any]:
        """Create a fallback structure when AI extraction fails."""
        # Simple text-based chapter detection
        lines = text.split('\n')
        chapters = []
        current_chapter = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Simple chapter detection
            if (line.startswith('Chapter') or 
                re.match(r'^\d+\.', line) or 
                (line.isupper() and len(line) > 3)):
                
                if current_chapter and current_content:
                    chapters.append({
                        "title": current_chapter,
                        "topics": [{"title": "Main Content", "description": "Core content of this chapter"}]
                    })
                
                current_chapter = line
                current_content = []
            else:
                current_content.append(line)
        
        if current_chapter and current_content:
            chapters.append({
                "title": current_chapter,
                "topics": [{"title": "Main Content", "description": "Core content of this chapter"}]
            })
        
        if not chapters:
            chapters.append({
                "title": "Main Content",
                "topics": [{"title": "General Content", "description": "Overall content of the document"}]
            })
        
        return {"chapters": chapters}
    
    def generate_notes_for_topic(self, topic_title: str, topic_description: str, content: str) -> str:
        """Generate concise notes for a specific topic using AI."""
        try:
            prompt = f"""
            Generate concise, well-structured notes for the topic: "{topic_title}"
            
            Topic description: {topic_description}
            
            Content to summarize:
            {content[:3000]}
            
            Generate notes that are:
            - Clear and easy to understand
            - Well-organized with bullet points
            - Include key concepts and definitions
            - Suitable for study and review
            
            Format the notes in a clean, readable structure.
            """
            
            stream = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an expert educator who creates clear, concise study notes."},
                    {"role": "user", "content": prompt}
                ],
                model=settings.cerebras_model,
                stream=True,
                max_completion_tokens=800,
                temperature=0.4,
                top_p=1
            )
            notes = ""
            for chunk in stream:
                notes += chunk.choices[0].delta.content or ""
            return notes
            
        except Exception as e:
            logger.error(f"Error generating notes: {e}")
            # Fallback: return a simple summary
            return f"Notes for {topic_title}:\n\n{content[:500]}..."
    
    def process_course_content(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process course chunks to generate structured notes."""
        # Group chunks by chapter
        chapters = {}
        for chunk in chunks:
            chapter_title = chunk.get('chapter_title', 'Main Content')
            if chapter_title not in chapters:
                chapters[chapter_title] = []
            chapters[chapter_title].append(chunk)
        
        structured_notes = []
        
        for chapter_title, chapter_chunks in chapters.items():
            # Combine all content for this chapter
            chapter_content = ' '.join([chunk['content'] for chunk in chapter_chunks])
            
            # Extract topics for this chapter
            topics_data = self.extract_topics_and_chapters(chapter_content)
            
            for topic_data in topics_data.get('chapters', []):
                if topic_data['title'] == chapter_title:
                    for topic in topic_data.get('topics', []):
                        # Generate notes for this topic
                        topic_content = chapter_content  # Could be refined to focus on specific topic
                        notes_content = self.generate_notes_for_topic(
                            topic['title'], 
                            topic['description'], 
                            topic_content
                        )
                        
                        structured_notes.append({
                            'chapter_title': chapter_title,
                            'topic_title': topic['title'],
                            'topic_description': topic['description'],
                            'notes_content': notes_content,
                            'chunks': chapter_chunks
                        })
        
        return structured_notes
