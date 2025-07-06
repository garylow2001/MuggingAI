from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import courses, files, chunks, quizzes, chat
from app.core.config import settings

app = FastAPI(
    title="MindCrush API",
    description="AI-Powered Learning Compressor API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(courses.router, prefix="/api/courses", tags=["courses"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(chunks.router, prefix="/api/chunks", tags=["chunks"])
app.include_router(quizzes.router, prefix="/api/quizzes", tags=["quizzes"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

@app.get("/")
async def root():
    return {"message": "Welcome to MindCrush API! 🧠"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "mindcrush-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 