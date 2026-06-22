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
    upstash_redis_rest_url: str = Field(..., alias="UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token: str = Field(..., alias="UPSTASH_REDIS_REST_TOKEN")
    postgres_url: Optional[str] = Field(None, alias="POSTGRES_URL")

    # Sentry DSN
    sentry_dsn: Optional[str] = Field(None, alias="SENTRY_DSN")

    # Security
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    secure_cookie: bool = Field(False, alias="SECURE_COOKIE")

    # Interview configuration
    interview_duration_minutes: int = Field(30, alias="INTERVIEW_DURATION_MINUTES")
    total_user_attempt: int = Field(1, alias="TOTAL_USER_ATTEMPT")
    interview_objective: str = Field("Conduct a professional, friendly, and rigorous interview.", alias="INTERVIEW_OBJECTIVE")
    interview_topics: str = Field("Experience with FastAPI and Async Python,System design concepts,Handling real-time streaming data pipelines", alias="INTERVIEW_TOPICS")
    num_questions: int = Field(5, alias="NUM_QUESTIONS")
    question_time_limit_seconds: int = Field(60, alias="QUESTION_TIME_LIMIT_SECONDS")
    avatar_gender: str = Field("female", alias="AVATAR_GENDER")
    agent_speech_speed: float = Field(1.0, alias="AGENT_SPEECH_SPEED")

    # Provider and STT config (if needed)
    llm_provider: Optional[str] = Field("groq", alias="LLM_PROVIDER")
    llm_model: Optional[str] = Field("llama-3.1-8b-instant", alias="LLM_MODEL")
    groq_api_key: Optional[str] = Field(None, alias="GROQ_API_KEY")
    groq_stt_model: Optional[str] = Field(None, alias="GROQ_STT_MODEL")

settings = Settings()
