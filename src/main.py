from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.domains.interviews.router import router as interviews_router
from src.shared.sentry import init_sentry
from src.shared.redis_client import redis_client
from src.shared.database import client as mongo_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the FastAPI application.
    """
    # 1. Initialize Sentry tracking from day one
    init_sentry()
    # Initialize Postgres tables
    from src.shared.postgres_db import init_postgres_db
    await init_postgres_db()
    yield
    # 2. Cleanup database clients to prevent connection leaks
    await redis_client.close()
    mongo_client.close()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI-Monitored Job Interview System",
    description="Compliance monitoring using MediaPipe and real-time WebRTC communication",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.domains.admin.router import router as admin_router

# Register interviews bounded context router
app.include_router(interviews_router)

# Register admin bounded context router
app.include_router(admin_router)
