# 🧠 MindCrush – AI-Powered Learning Compressor

Transform lengthy educational materials into digestible, interactive learning experiences using AI.

## 🚀 Features

- **Smart Content Processing**: Upload PDFs, DOCX, and text files for automatic chunking and summarization
- **Chapter-Based Organization**: Content is automatically organized into logical learning units
- **Key Point Extraction**: AI identifies and highlights essential learning points per chapter
- **Interactive Quizzes**: Generate MCQs with explanations to reinforce learning
- **Tutor Mode**: Ask contextual questions and get grounded answers using RAG
- **Organized Storage**: All content, quizzes, and metadata stored in structured folders

## 🏗️ Architecture

### Frontend

- **React** with **Vite** for fast development
- **ShadCN UI** for beautiful, accessible components
- **Zustand** for state management
- **TanStack Query** for data fetching

### Backend

- **FastAPI** for high-performance API
- **OpenAI GPT-4** for content processing and quiz generation
- **FAISS** for vector similarity search
- **PostgreSQL** for data persistence
- **Model Context Provider (MCP)** for optimized LLM interactions

## 🛠️ Setup

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL (optional, SQLite for development)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## 📁 Project Structure

```
mindcrush/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── services/
│   │   └── utils/
│   ├── requirements.txt
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── stores/
│   │   └── utils/
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## 🔧 Environment Variables

Create `.env` files in both `backend/` and `frontend/` directories:

### Backend (.env)

```
CEREBRAS_API_KEY=your_cerebras_api_key
DATABASE_URL=postgresql://user:password@localhost/mindcrush
SECRET_KEY=your_secret_key
```

### Frontend (.env)

```
VITE_API_URL=http://localhost:8000
```

## 🎯 Core AI Concepts

- **RAG (Retrieval-Augmented Generation)**: For tutor chat and focused QA
- **Model Context Provider (MCP)**: Middleware layer for optimized LLM prompts
- **Embedding Search**: Semantic retrieval from notes
- **Prompt Engineering**: Structured output generation
- **Chunking Logic**: Semantic content segmentation

## 📝 License

MIT License - see LICENSE file for details.
