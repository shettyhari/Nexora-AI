import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "NEXORA AI"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Security & Tokens
    SECRET_KEY: str = "nexora_ai_super_secret_jwt_encryption_key_change_in_production_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 48
    RESET_TOKEN_EXPIRE_HOURS: int = 2

    # Database
    # Defaults to SQLite async for zero-dependency local dev & testing, supports PostgreSQL async via asyncpg
    DATABASE_URL: str = "sqlite+aiosqlite:///./nexora.db"
    DATABASE_ECHO: bool = False

    # Redis Cache & Sessions
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

    # File uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: List[str] = [
        "png", "jpg", "jpeg", "webp", "gif",
        "pdf", "txt", "md", "csv", "json", "py", "ts", "tsx", "js"
    ]

    # AI Provider Keys & Gateway
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    HUGGINGFACE_API_KEY: str = ""
    HUGGINGFACE_ENDPOINT_URL: str = ""
    OPENAI_COMPATIBLE_BASE_URL: str = ""
    OPENAI_COMPATIBLE_API_KEY: str = ""
    DEFAULT_LLM_PROVIDER: str = "gemini"
    DEFAULT_MODEL_ID: str = "nexora-auto"

    # Intelligence Engine Settings
    ENABLE_INTELLIGENT_ROUTING: bool = True
    ENABLE_MEMORY: bool = True
    ENABLE_RAG: bool = True
    EMBEDDING_PROVIDER: str = "auto"  # "auto", "openai", "gemini", "local"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    VECTOR_DIMENSION: int = 384
    MAX_CONTEXT_TOKENS: int = 128000
    OUTPUT_RESERVE_TOKENS: int = 4096

    # Web search
    TAVILY_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""
    ENABLE_WEB_SEARCH: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]


settings = Settings()

