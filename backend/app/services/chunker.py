import re
from typing import List, Dict, Any, Optional
import PyPDF2
from docx import Document
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
import os

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class Chunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.stop_words = set(stopwords.words('english'))
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text.strip():
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            # Return a placeholder text if PDF extraction fails
            text = f"PDF content could not be extracted. Error: {e}"
        return text
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        text = ""
        try:
            doc = Document(file_path)
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            # Return a placeholder text if DOCX extraction fails
            text = f"DOCX content could not be extracted. Error: {e}"
        return text
    
    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading TXT file: {e}")
            return ""
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from file based on its extension."""
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_extension == '.docx':
            return self.extract_text_from_docx(file_path)
        elif file_extension == '.txt':
            return self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    def detect_chapters(self, text: str) -> List[Dict[str, Any]]:
        """Detect chapter boundaries in text."""
        chapters = []
        
        # Common chapter patterns
        chapter_patterns = [
            r'^Chapter\s+\d+[:\s]*([^\n]+)',
            r'^\d+\.\s*([^\n]+)',
            r'^[A-Z][A-Z\s]+\n',
            r'^[A-Z][a-z\s]+\n',
        ]
        
        lines = text.split('\n')
        current_chapter = None
        current_content = []
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check if this line is a chapter header
            is_chapter_header = False
            chapter_title = None
            
            for pattern in chapter_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    is_chapter_header = True
                    chapter_title = match.group(1) if len(match.groups()) > 0 else line
                    break
            
            if is_chapter_header and chapter_title:
                # Save previous chapter if exists
                if current_chapter and current_content:
                    chapters.append({
                        'title': current_chapter,
                        'content': '\n'.join(current_content),
                        'start_line': line_num
                    })
                
                # Start new chapter
                current_chapter = chapter_title
                current_content = [line]
            else:
                current_content.append(line)
        
        # Add the last chapter
        if current_chapter and current_content:
            chapters.append({
                'title': current_chapter,
                'content': '\n'.join(current_content),
                'start_line': len(lines)
            })
        
        # If no chapters detected, treat entire text as one chapter
        if not chapters:
            chapters.append({
                'title': 'Main Content',
                'content': text,
                'start_line': 0
            })
        
        return chapters
    
    def chunk_text(self, text: str, chapter_title: Optional[str] = None) -> List[Dict[str, Any]]:
        """Chunk text into smaller pieces while preserving semantic meaning."""
        chunks = []
        
        # Split into sentences first
        sentences = sent_tokenize(text)
        
        current_chunk = []
        current_length = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_length = len(sentence.split())
            
            # If adding this sentence would exceed chunk size, save current chunk
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                chunks.append({
                    'content': chunk_text,
                    'chunk_index': chunk_index,
                    'chapter_title': chapter_title,
                    'word_count': current_length
                })
                
                # Start new chunk with overlap
                overlap_sentences = current_chunk[-3:] if len(current_chunk) >= 3 else current_chunk
                current_chunk = overlap_sentences + [sentence]
                current_length = sum(len(s.split()) for s in current_chunk)
                chunk_index += 1
            else:
                current_chunk.append(sentence)
                current_length += sentence_length
        
        # Add the last chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append({
                'content': chunk_text,
                'chunk_index': chunk_index,
                'chapter_title': chapter_title,
                'word_count': current_length
            })
        
        return chunks
    
    def process_file(self, file_path: str, course_id: int, file_id: int) -> List[Dict[str, Any]]:
        """Process a file and return chunks with metadata."""
        # Extract text
        text = self.extract_text(file_path)
        
        # Detect chapters
        chapters = self.detect_chapters(text)
        
        all_chunks = []
        
        for chapter in chapters:
            # Chunk the chapter content
            chapter_chunks = self.chunk_text(chapter['content'], chapter['title'])
            
            # Add metadata to chunks
            for chunk in chapter_chunks:
                chunk.update({
                    'course_id': course_id,
                    'file_id': file_id,
                    'page_number': None  # Could be enhanced to track page numbers
                })
                all_chunks.append(chunk)
        
        return all_chunks
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)]', '', text)
        
        # Normalize quotes and dashes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace('–', '-').replace('—', '-')
        
        return text.strip()
    
    def get_chunk_statistics(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about the chunks."""
        if not chunks:
            return {}
        
        total_chunks = len(chunks)
        total_words = sum(chunk.get('word_count', 0) for chunk in chunks)
        avg_chunk_size = total_words / total_chunks if total_chunks > 0 else 0
        
        chapters = set(chunk.get('chapter_title') for chunk in chunks if chunk.get('chapter_title'))
        
        return {
            'total_chunks': total_chunks,
            'total_words': total_words,
            'average_chunk_size': round(avg_chunk_size, 2),
            'unique_chapters': len(chapters),
            'chapters': list(chapters)
        } 