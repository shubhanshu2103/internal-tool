from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    chroma_persist_dir: str = "./data/chroma_db"
    rubric_path: str = "./data/rubric/rubric.json"
    outputs_dir: str = "./data/outputs"

    # Jina AI — used for embeddings (free API, no local process, deployment-safe)
    jina_api_key: str = ""
    jina_embed_model: str = "jina-embeddings-v2-base-en"  # 768-dim, 1M free tokens

    # Groq — used for LLM judge (free API, zero local RAM)
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"        # 500K TPD free tier (5× more quota)

    # Embedding config — jina-embeddings-v2-base-en produces 768-dim vectors
    embedding_dims: int = 768

    # RAG config
    top_k_retrieval: int = 3        # how many approved chunks to retrieve per section
    min_similarity: float = 0.30    # below this → rubric-only mode (no similar chunk found)

    class Config:
        env_file = ".env"


settings = Settings()
