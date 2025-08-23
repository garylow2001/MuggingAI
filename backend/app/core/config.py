from pydantic_settings import BaseSettings
from typing import Optional
import os
from openai import OpenAI

class Settings(BaseSettings):
    # API Configuration
    api_v1_str: str = "/api/v1"
    project_name: str = "MindCrush"
    
    # Database
    database_url: str = "sqlite:///./mindcrush.db"
    
    # Cerebras Configuration
    cerebras_api_key: str = os.environ.get("CEREBRAS_API_KEY", "no_api_key_provided")
    cerebras_model: str = "llama3.1-8b"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # File Upload
    uploads_dir: str = "./uploads"
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    
    # Vector Store
    vector_store_path: str = "./vector_store"
    
    # Chunking Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        env_prefix = ""
        extra = "ignore"

settings = Settings()

# Cerebras client initialization using OpenAI-compatible API
# def get_cerebras_client():
#     api_key = os.environ.get("CEREBRAS_API_KEY", settings.cerebras_api_key)
#     if api_key == "no_api_key_provided":
#         raise RuntimeError("Cerebras API key not provided. Set CEREBRAS_API_KEY environment variable.")
    
#     return OpenAI(
#         api_key=api_key,
#         base_url="https://api.cerebras.ai/v1",
#     )

# Ensure upload directory exists
os.makedirs(settings.uploads_dir, exist_ok=True)
os.makedirs(settings.vector_store_path, exist_ok=True)