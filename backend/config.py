from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    chroma_persist_dir: str = "./data/chroma_db"
    rubric_path: str = "./data/rubric/rubric.json"
    outputs_dir: str = "./data/outputs"

    # Ollama — used ONLY for local embeddings (lightweight, no RAM pressure)
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"   # pull with: ollama pull nomic-embed-text

    # Groq — used for LLM judge (free API, 70B model, zero local RAM)
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"        # 500K TPD free tier (5× more quota)

    # Embedding config — nomic-embed-text produces 768-dim vectors
    embedding_dims: int = 768

    # RAG config
    top_k_retrieval: int = 3        # how many approved chunks to retrieve per section
    min_similarity: float = 0.30    # below this → rubric-only mode (no similar chunk found)

    class Config:
        env_file = ".env"


settings = Settings()
