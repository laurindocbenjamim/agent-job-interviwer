import redis.asyncio as aioredis
from src.config.settings import settings

# Global async redis client
redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

def get_strike_key(candidate_id: str) -> str:
    """Returns the Redis key structure for candidate strikes."""
    return f"candidate:{candidate_id}:strikes"

async def get_candidate_strikes(candidate_id: str) -> int:
    """Gets the current number of strikes for a candidate."""
    val = await redis_client.get(get_strike_key(candidate_id))
    return int(val) if val is not None else 0

async def increment_candidate_strikes(candidate_id: str) -> int:
    """Increments and returns candidate strikes in Redis."""
    key = get_strike_key(candidate_id)
    # Set expiration of 2 hours to avoid stale sessions or memory leaks
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, 7200)
    res = await pipe.execute()
    return int(res[0])

async def reset_candidate_strikes(candidate_id: str) -> None:
    """Resets candidate strikes."""
    await redis_client.delete(get_strike_key(candidate_id))
