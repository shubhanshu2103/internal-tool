from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    chroma_persist_dir: str = "./data/chroma_db"
    rubric_path: str = "./data/rubric/rubric.json"
    outputs_dir: str = "./data/outputs"

    # Ollama config — run `ollama serve` locally before starting the server
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"   # pull with: ollama pull nomic-embed-text
    ollama_chat_model: str = "llama3.2"            # pull with: ollama pull llama3.2

    # Embedding config — nomic-embed-text produces 768-dim vectors
    embedding_dims: int = 768

    # RAG config
    top_k_retrieval: int = 3        # how many approved chunks to retrieve per section
    min_similarity: float = 0.30    # below this → rubric-only mode (no similar chunk found)

    class Config:
        env_file = ".env"


settings = Settings()
