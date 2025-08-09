# MindCrunch File Upload Feature

## Overview
The file upload feature allows users to upload course materials (PDF, DOCX, TXT) to courses, which are then automatically processed to:
- Extract text content
- Create semantic chunks for AI analysis
- Generate embeddings for vector search
- Create structured notes and topics

## Features

### Supported File Types
- **PDF** (.pdf) - Best for documents with complex formatting
- **DOCX** (.docx) - Best for rich text documents
- **TXT** (.txt) - Best for simple text content

### File Processing Pipeline
1. **File Upload** - Secure file storage with unique naming
2. **Text Extraction** - Extract text content from various file formats
3. **Content Chunking** - Break content into semantic chunks (1000 words with 200 word overlap)
4. **Chapter Detection** - Automatically identify chapter boundaries
5. **AI Note Generation** - Generate structured notes using OpenAI
6. **Vector Embeddings** - Create searchable embeddings for content retrieval

### File Size Limits
- Maximum file size: 50MB
- Recommended: Under 20MB for optimal processing

## Backend Implementation

### API Endpoints
- `POST /api/files/upload/{course_id}` - Upload and process a file
- `GET /api/files/{course_id}` - Get all files for a course
- `DELETE /api/files/{file_id}` - Delete a file and associated data

### Key Components
- **Chunker Service** - Handles text extraction and chunking
- **Vector Store** - Manages embeddings and similarity search
- **Note Generator** - Creates AI-powered notes from content
- **Database Models** - Stores files, chunks, topics, and notes

### Error Handling
- Comprehensive error handling for file processing failures
- Graceful degradation when AI services are unavailable
- Detailed logging for debugging

## Frontend Implementation

### FileUpload Component
- Drag & drop file upload interface
- File type validation and size checking
- Real-time upload progress
- Success/error feedback
- File details modal

### Features
- **Drag & Drop** - Intuitive file upload
- **File Validation** - Checks file type and size before upload
- **Progress Tracking** - Visual upload progress indicator
- **Error Handling** - Clear error messages and recovery options
- **File Information** - Detailed file metadata display

## Setup and Usage

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Start the server:
   ```bash
   ./start_server.sh
   ```
   Or manually:
   ```bash
   python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies and start:
   ```bash
   npm install
   npm run dev
   ```

### Environment Configuration
Create a `.env` file in the backend directory with:
```env
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_URL=sqlite:///./mindcrunch.db
SECRET_KEY=your-secret-key-change-in-production
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800
VECTOR_STORE_PATH=./vector_store
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## Testing

### Test Upload Functionality
1. Start the backend server
2. Create a course (if none exist)
3. Use the test script:
   ```bash
   cd backend
   python3 test_upload.py
   ```

### Manual Testing
1. Open the frontend in a browser
2. Navigate to a course
3. Use the file upload component
4. Check the backend logs for processing details

## Troubleshooting

### Common Issues
1. **Import Error**: Make sure to run from the backend directory
2. **File Processing Failures**: Check file format and size
3. **AI Service Errors**: Verify OpenAI API key configuration
4. **Database Errors**: Check database file permissions

### Debug Information
- Backend logs show detailed processing steps
- Frontend console shows API call details
- Database queries are logged for debugging

## Performance Considerations

### Optimization
- Chunk size (1000 words) balances context and searchability
- Overlap (200 words) maintains semantic continuity
- Async processing for non-blocking uploads
- Efficient vector storage with FAISS

### Scalability
- File processing is stateless and parallelizable
- Vector store supports large-scale similarity search
- Database relationships optimize query performance

## Security Features

### File Safety
- Unique filename generation prevents conflicts
- File type validation prevents malicious uploads
- Size limits prevent resource exhaustion
- Secure file storage in dedicated uploads directory

### API Security
- CORS configuration for frontend access
- Input validation and sanitization
- Error messages don't expose system details
