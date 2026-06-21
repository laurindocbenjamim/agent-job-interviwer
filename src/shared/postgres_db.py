import logging
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, Boolean, Text, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from src.config.settings import settings

logger = logging.getLogger("postgres_db")

# Setup SQLAlchemy engine (asyncpg uses async engine, but since FastAPI is async, 
# we can use standard async engine, or synchronous engine for simpler integration, 
# but the prompt env says asyncpg. Let's use SQLAlchemy async or synchronous with asyncpg.
# Wait! Standard SQLAlchemy supports asyncpg with 'postgresql+asyncpg://' driver.)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

Base = declarative_base()

class InterviewConfig(Base):
    __tablename__ = "interview_configurations"

    candidate_id = Column(String(100), primary_key=True, index=True)
    interview_duration_minutes = Column(Integer, default=30)
    avatar_gender = Column(String(20), default="female")
    question_time_limit_seconds = Column(Integer, default=60)
    num_questions = Column(Integer, default=5)
    interview_objective = Column(Text, default="Conduct a professional, friendly, and rigorous interview.")
    interview_topics = Column(Text, default="Experience with FastAPI and Async Python,System design concepts,Handling real-time streaming data pipelines")
    speech_language = Column(String(50), default="en-US")
    text_language = Column(String(50), default="en")
    candidate_name = Column(String(100), nullable=True)
    job_specialty = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)

import asyncio

_engines = {}
_sessionmakers = {}
_db_initialized = False

async def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        await init_postgres_db()
        _db_initialized = True

def get_engine_and_sessionmaker():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    key = loop or "default"
    if key not in _engines:
        db_url = settings.postgres_url
        if not db_url:
            db_url = "sqlite+aiosqlite:///./test_postgres.db"
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            
        eng = create_async_engine(db_url, echo=False)
        _engines[key] = eng
        _sessionmakers[key] = sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        
    return _engines[key], _sessionmakers[key]

async def init_postgres_db():
    """Initializes the database tables and runs schema migration if needed."""
    engine, _ = get_engine_and_sessionmaker()
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Alter table to add candidate_name and job_specialty if they don't exist
        try:
            if "sqlite" in str(engine.url):
                await conn.execute(text("ALTER TABLE interview_configurations ADD COLUMN candidate_name VARCHAR(100)"))
            else:
                await conn.execute(text("ALTER TABLE interview_configurations ADD COLUMN IF NOT EXISTS candidate_name VARCHAR(100)"))
        except Exception:
            pass
            
        try:
            if "sqlite" in str(engine.url):
                await conn.execute(text("ALTER TABLE interview_configurations ADD COLUMN job_specialty VARCHAR(100)"))
            else:
                await conn.execute(text("ALTER TABLE interview_configurations ADD COLUMN IF NOT EXISTS job_specialty VARCHAR(100)"))
        except Exception:
            pass

async def get_postgres_config(candidate_id: str) -> Optional[InterviewConfig]:
    """Retrieves an interview configuration for a candidate by UUID/ID."""
    await ensure_db_initialized()
    _, AsyncSessionLocal = get_engine_and_sessionmaker()
    async with AsyncSessionLocal() as session:
        result = await session.get(InterviewConfig, candidate_id)
        return result

async def save_postgres_config(candidate_id: str, data: Dict[str, Any]) -> InterviewConfig:
    """Saves or updates an interview configuration for a candidate."""
    await ensure_db_initialized()
    _, AsyncSessionLocal = get_engine_and_sessionmaker()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            config = await session.get(InterviewConfig, candidate_id)
            if not config:
                config = InterviewConfig(candidate_id=candidate_id)
                session.add(config)
            
            # Update fields
            config.interview_duration_minutes = int(data.get("interview_duration_minutes", config.interview_duration_minutes))
            config.avatar_gender = str(data.get("avatar_gender", config.avatar_gender))
            config.question_time_limit_seconds = int(data.get("question_time_limit_seconds", config.question_time_limit_seconds))
            config.num_questions = int(data.get("num_questions", config.num_questions))
            config.interview_objective = str(data.get("interview_objective", config.interview_objective))
            config.interview_topics = str(data.get("interview_topics", config.interview_topics))
            config.speech_language = str(data.get("speech_language", config.speech_language))
            config.text_language = str(data.get("text_language", config.text_language))
            config.candidate_name = str(data.get("candidate_name", config.candidate_name)) if data.get("candidate_name") is not None else config.candidate_name
            config.job_specialty = str(data.get("job_specialty", config.job_specialty)) if data.get("job_specialty") is not None else config.job_specialty
            config.is_active = bool(data.get("is_active", config.is_active))
            
            await session.commit()
            return config

async def get_all_postgres_configs():
    """Retrieves all candidate configurations from Postgres/SQLite."""
    from sqlalchemy import select
    await ensure_db_initialized()
    _, AsyncSessionLocal = get_engine_and_sessionmaker()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(InterviewConfig))
        return result.scalars().all()

async def delete_postgres_configs(candidate_ids: list[str]):
    """Deletes one or more candidate configurations from Postgres/SQLite."""
    from sqlalchemy import delete
    await ensure_db_initialized()
    _, AsyncSessionLocal = get_engine_and_sessionmaker()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(InterviewConfig).where(InterviewConfig.candidate_id.in_(candidate_ids)))
            await session.commit()
