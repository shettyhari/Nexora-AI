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
    APP_VERSION: str = "2.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production
    STRICT_SECRET_VALIDATION: bool = False

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
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [
        "png", "jpg", "jpeg", "webp", "gif", "svg",
        "pdf", "docx", "xlsx", "csv", "pptx", "txt", "md", "json", "py", "ts", "tsx", "js",
        "mp3", "wav", "m4a", "ogg", "mp4", "webm", "mov", "avi"
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

    # Multimodal & Voice Settings
    IMAGE_GEN_PROVIDER: str = "openai"  # "openai", "stability", "nexora"
    SPEECH_PROVIDER: str = "openai"     # "openai", "local", "nexora"
    VOICE_DEFAULT_MODEL: str = "tts-1"
    VOICE_DEFAULT_SPEAKER: str = "alloy"
    WHISPER_MODEL: str = "whisper-1"

    # Agent & Tool Execution Settings
    MAX_AGENT_STEPS: int = 10
    TOOL_TIMEOUT_SECONDS: float = 30.0
    SANDBOX_TIMEOUT_SECONDS: float = 15.0
    REQUIRE_APPROVAL_FOR_EXECUTE: bool = True
    MAX_RESEARCH_SOURCES: int = 5

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

    # Object Storage (S3-compatible or local fallback)
    STORAGE_BACKEND: str = "local"  # "local" or "s3"
    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = "nexora-assets"
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "us-east-1"
    BACKUP_DIR: str = "./backups"

    # Commercial Billing & Payment Provider
    PAYMENT_PROVIDER: str = "local"  # "local" or "stripe"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Rate Limiting & Browser Security
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_RPM: int = 120
    RATE_LIMIT_AUTH_RPM: int = 30
    ALLOWED_BROWSER_DOMAINS: List[str] = []

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("ALLOWED_BROWSER_DOMAINS", mode="before")
    @classmethod
    def assemble_browser_domains(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip().lower() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(i).strip().lower() for i in v if str(i).strip()]
        return []

    def validate_production_secrets(self) -> List[str]:
        """Validate critical security settings before running in production."""
        issues: List[str] = []
        default_secret = "nexora_ai_super_secret_jwt_encryption_key_change_in_production_2026"
        if self.SECRET_KEY == default_secret:
            issues.append("SECRET_KEY is using the built-in development default.")
        if len(self.SECRET_KEY) < 32:
            issues.append("SECRET_KEY is shorter than 32 characters.")
        if self.ENVIRONMENT.lower() == "production" or self.STRICT_SECRET_VALIDATION:
            if issues:
                raise RuntimeError(f"Production security configuration invalid: {'; '.join(issues)}")
        return issues


settings = Settings()

