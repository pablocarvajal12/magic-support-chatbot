from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación, cargada desde variables de entorno / .env"""

    # --- App ---
    app_name: str = "Magic Chatbot"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # --- LLM (Groq) ---
    groq_api_key: str  # Requerida: el servidor no arranca sin ella
    groq_model: str = "llama-3.1-70b-versatile"
    groq_temperature: float = 0.1

    # --- Embeddings ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Vector store (Chroma) ---
    chroma_persist_dir: str = "./chroma_db"
    chroma_collection_name: str = "magic_rules"

    # --- RAG / Chunking ---
    rules_pdf_path: str = "./data/magic_rules.pdf"
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_k: int = 4

    # --- Memoria de conversación ---
    memory_window_k: int = 10

    # --- API externa de cartas ---
    mtg_api_base_url: str = "https://api.magicthegathering.io/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Devuelve una instancia cacheada de Settings (singleton de facto).

    Se usa como dependencia de FastAPI (`Depends(get_settings)`) y desde
    los servicios. `lru_cache` evita releer/parsear el `.env` en cada uso.
    """
    return Settings()