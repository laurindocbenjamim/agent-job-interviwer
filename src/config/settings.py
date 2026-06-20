from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database and Caching
    mongodb_uri: str = Field(..., alias="MONGODB_URI")
    mongodb_db_name: str = Field("nutrisentinel_agent_ai", alias="MONGODB_DB_NAME")
    mongodb_collection: str = Field("analysis", alias="MONGODB_COLLECTION")
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    # Sentry DSN
    sentry_dsn: Optional[str] = Field(None, alias="SENTRY_DSN")

    # Security
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    secure_cookie: bool = Field(False, alias="SECURE_COOKIE")

    # Provider and STT config (if needed)
    llm_provider: Optional[str] = Field("groq", alias="LLM_PROVIDER")
    llm_model: Optional[str] = Field("llama-3.1-8b-instant", alias="LLM_MODEL")
    groq_api_key: Optional[str] = Field(None, alias="GROQ_API_KEY")
    groq_stt_model: Optional[str] = Field(None, alias="GROQ_STT_MODEL")

settings = Settings()
