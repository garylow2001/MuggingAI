# 🧠 MindCrush Setup Guide

This guide will help you set up the MindCrush AI-powered learning compressor project.

## Prerequisites

- Python 3.9+
- Node.js 18+
- OpenAI API key
- Git

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd mindcrush

# Create environment files
cp backend/env.example backend/.env
cp frontend/env.example frontend/.env
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
# Edit backend/.env and add your OpenAI API key:
# OPENAI_API_KEY=your_actual_openai_api_key_here

# Run the backend
uvicorn main:app --reload
```

The backend will be available at `http://localhost:8000`

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Environment Configuration

### Backend (.env)

```env
# Required: Your OpenAI API key
OPENAI_API_KEY=sk-your-openai-api-key-here

# Database (SQLite for development)
DATABASE_URL=sqlite:///./mindcrush.db

# Security (change in production)
SECRET_KEY=your-secret-key-change-in-production

# File upload settings
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=52428800

# Vector store
VECTOR_STORE_PATH=./vector_store

# Chunking settings
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### Frontend (.env)

```env
# API URL (default should work with proxy)
VITE_API_URL=http://localhost:8000
```

## Project Structure

```
mindcrush/
├── backend/
│   ├── app/
│   │   ├── api/routes/     # API endpoints
│   │   ├── core/           # Configuration
│   │   ├── models/         # Database models
│   │   └── services/       # Business logic
│   ├── main.py            # FastAPI app
│   └── requirements.txt   # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── stores/        # Zustand stores
│   │   └── utils/         # Utilities
│   ├── package.json       # Node dependencies
│   └── vite.config.ts     # Vite config
└── README.md
```

## API Endpoints

### Courses
- `GET /api/courses` - List all courses
- `POST /api/courses` - Create a new course
- `GET /api/courses/{id}` - Get course details
- `PUT /api/courses/{id}` - Update course
- `DELETE /api/courses/{id}` - Delete course

### Files
- `POST /api/files/upload` - Upload and process file
- `GET /api/files/course/{courseId}` - Get files for course
- `DELETE /api/files/{id}` - Delete file

### Chunks
- `GET /api/chunks/course/{courseId}` - Get chunks for course
- `GET /api/chunks/course/{courseId}/chapters` - Get chapters
- `GET /api/chunks/course/{courseId}/search` - Search chunks

### Quizzes
- `POST /api/quizzes/generate` - Generate MCQs
- `GET /api/quizzes/course/{courseId}` - Get quizzes
- `POST /api/quizzes/{id}/answer` - Answer quiz

### Chat
- `POST /api/chat` - Chat with AI tutor
- `GET /api/chat/sessions` - Get chat sessions
- `POST /api/chat/summarize` - Generate summary
- `POST /api/chat/key-points` - Extract key points

## Usage

1. **Create a Course**: Use the frontend or API to create a new course
2. **Upload Files**: Upload PDF, DOCX, or TXT files to your course
3. **Generate Content**: The system will automatically:
   - Extract text from files
   - Chunk content into chapters
   - Create embeddings for semantic search
4. **Generate Quizzes**: Create MCQs for any chapter
5. **Chat with Tutor**: Ask questions about your course content
6. **Get Summaries**: Generate chapter summaries and key points

## Development

### Backend Development

```bash
cd backend
source venv/bin/activate

# Run with auto-reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests (when implemented)
pytest

# Format code
black .
isort .
```

### Frontend Development

```bash
cd frontend

# Start dev server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint
```

## Troubleshooting

### Common Issues

1. **OpenAI API Key Error**
   - Ensure your API key is valid and has sufficient credits
   - Check the key is correctly set in `backend/.env`

2. **Database Issues**
   - Delete `mindcrush.db` and restart to reset database
   - Check SQLite is installed and accessible

3. **File Upload Issues**
   - Ensure `uploads/` directory exists and is writable
   - Check file size limits in configuration

4. **Frontend Build Issues**
   - Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
   - Check Node.js version is 18+

### Logs

- Backend logs appear in the terminal where you run `uvicorn`
- Frontend logs appear in browser console and terminal
- Check browser Network tab for API request issues

## Production Deployment

### Backend
- Use PostgreSQL instead of SQLite
- Set up proper environment variables
- Use a production WSGI server like Gunicorn
- Set up proper CORS configuration

### Frontend
- Build with `npm run build`
- Serve static files with nginx or similar
- Configure API URL for production

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details. 