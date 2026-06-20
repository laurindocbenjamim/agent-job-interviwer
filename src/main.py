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
    yield
    # 2. Cleanup database clients to prevent connection leaks
    await redis_client.close()
    mongo_client.close()

app = FastAPI(
    title="AI-Monitored Job Interview System",
    description="Compliance monitoring using MediaPipe and real-time WebSocket communication",
    version="1.0.0",
    lifespan=lifespan
)

# Register interviews bounded context router
app.include_router(interviews_router)
