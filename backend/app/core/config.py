import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from dotenv import load_dotenv

# Load .env file into os.environ for non-Pydantic config usage
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Load from .env in backend directory, or fallback
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PORT: int = 8000
    HOST: str = "127.0.0.1"
    ENVIRONMENT: str = "development"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Databases
    DATABASE_URL: str = "sqlite:///./local_db.db"
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Third Party APIs
    OPENAI_API_KEY: str = ""
    FIREBASE_PROJECT_ID: str = ""

    # Chunker & Embedding Configuration
    DEFAULT_CHUNK_SIZE: int = 450
    DEFAULT_CHUNK_OVERLAP: int = 90
    EMBEDDING_PROVIDER: str = "local"  # 'openai' or 'local'
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_MODEL_TIER: str = "base"  # 'base' or 'large'
    MIN_RERANK_CONFIDENCE: float = -15.0  # may need empirical tuning once real testing starts

    # Chunk Quality Filtering Configurations
    MIN_CHUNK_CHAR_LENGTH: int = 20
    MIN_ALPHA_DENSITY: float = 0.25
    OUTLIER_SIMILARITY_THRESHOLD: float = 0.40
    STRICT_OUTLIER_FILTERING: bool = False

    # OLD: defined LLM_PROVIDER as a simple string without ollama support — replaced below to add ollama variables
    # LLM_PROVIDER: str = "openai"  # 'openai' or 'claude'
    LLM_PROVIDER: str = "openai"  # 'openai', 'claude', or 'ollama'
    OLLAMA_API_URL: str = "http://localhost:11434"
    # OLD: default model was set to mistral:7b-instruct-q4_0 (7B parameter model, too slow for CPU), kept for reference
    # OLLAMA_MODEL: str = "mistral:7b-instruct-q4_0"
    OLLAMA_MODEL: str = "llama3.2"
    CLAUDE_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 1000
    CONVERSATION_MEMORY_LIMIT: int = 10
    MONTHLY_SPEND_LIMIT_USD: float = 50.0
    
    # Centralized RAG Retrieval Settings
    # OLD: default settings retrieved 15 chunks per search, kept for reference
    # VECTOR_TOP_K: int = 15
    # BM25_TOP_K: int = 15
    VECTOR_TOP_K: int = 10
    BM25_TOP_K: int = 10
    FINAL_TOP_N: int = 5
    ENABLE_QUERY_EXPANSION: bool = True

    # BM25 Persistent Index Storage
    # Subfolder under CHROMA_PERSIST_DIR where per-document BM25 pickle files are stored.
    BM25_INDEX_SUBDIR: str = "bm25_indexes"

    # In-process BM25 LRU cache: max number of BM25 indexes held in memory at once.
    # Oldest entry is evicted when the limit is exceeded.
    BM25_CACHE_MAX_SIZE: int = 10

    # Dynamic top-k scaling for large documents.
    # When a document's chunk count exceeds LARGE_DOC_CHUNK_THRESHOLD, retrieval
    # breadth is increased to LARGE_DOC_VECTOR_TOP_K / LARGE_DOC_BM25_TOP_K so that
    # relevant content buried beyond the default top-15 window is still surfaced before
    # the cross-encoder reranker narrows results back down to FINAL_TOP_N.
    LARGE_DOC_CHUNK_THRESHOLD: int = 500
    LARGE_DOC_VECTOR_TOP_K: int = 25
    LARGE_DOC_BM25_TOP_K: int = 25

    @property
    def cors_origins_list(self) -> List[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if "*" in origins:
            raise ValueError("CORS_ORIGINS cannot contain wildcard '*' per project security guidelines.")
        return origins

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors(cls, v: str) -> str:
        origins = [origin.strip() for origin in v.split(",") if origin.strip()]
        if "*" in origins:
            raise ValueError("CORS_ORIGINS cannot contain wildcard '*' per project security guidelines.")
        return v

# Instantiate settings globally
settings = Settings()
