import asyncio
from src.config.settings import settings
from sqlalchemy.ext.asyncio import create_async_engine
from redis.asyncio import Redis
from motor.motor_asyncio import AsyncIOMotorClient

async def test():
    print("Testing Postgres...")
    try:
        engine = create_async_engine(settings.postgres_url)
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print("Postgres OK!")
    except Exception as e:
        print(f"Postgres Error: {e}")

    print("Testing Redis...")
    try:
        r = Redis.from_url(settings.redis_url)
        await r.ping()
        print("Redis OK!")
    except Exception as e:
        print(f"Redis Error: {e}")

    print("Testing MongoDB...")
    try:
        m = AsyncIOMotorClient(settings.mongodb_uri)
        await m.server_info()
        print("MongoDB OK!")
    except Exception as e:
        print(f"MongoDB Error: {e}")

from sqlalchemy import text
asyncio.run(test())
