import httpx
import json
from typing import Any, Optional, List
from src.config.settings import settings

class UpstashRedisClient:
    def __init__(self, url: str, token: str):
        # Ensure url does not end with /
        self.url = url.rstrip('/')
        self.token = token
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def _execute(self, command: List[Any]) -> Any:
        async with httpx.AsyncClient() as client:
            # Upstash accepts POST to the root with the command array
            response = await client.post(
                self.url,
                headers=self.headers,
                json=command
            )
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise Exception(f"Upstash Error: {data['error']}")
            return data.get("result")

    async def _execute_pipeline(self, commands: List[List[Any]]) -> List[Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/pipeline",
                headers=self.headers,
                json=commands
            )
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data:
                if "error" in item:
                    raise Exception(f"Upstash Pipeline Error: {item['error']}")
                results.append(item.get("result"))
            return results

    async def get(self, key: str) -> Optional[str]:
        return await self._execute(["GET", key])

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> Any:
        cmd = ["SET", key, value]
        if ex is not None:
            cmd.extend(["EX", ex])
        return await self._execute(cmd)

    async def delete(self, key: str) -> Any:
        return await self._execute(["DEL", key])

# Global async redis client wrapper
redis_client = UpstashRedisClient(
    url=settings.upstash_redis_rest_url,
    token=settings.upstash_redis_rest_token
)

def get_strike_key(candidate_id: str) -> str:
    """Returns the Redis key structure for candidate strikes."""
    return f"candidate:{candidate_id}:strikes"

async def get_candidate_strikes(candidate_id: str) -> int:
    """Gets the current number of strikes for a candidate."""
    val = await redis_client.get(get_strike_key(candidate_id))
    return int(val) if val is not None else 0

async def increment_candidate_strikes(candidate_id: str) -> int:
    """Increments and returns candidate strikes in Redis using a pipeline."""
    key = get_strike_key(candidate_id)
    # Set expiration of 2 hours to avoid stale sessions or memory leaks
    results = await redis_client._execute_pipeline([
        ["INCR", key],
        ["EXPIRE", key, 7200]
    ])
    return int(results[0])

async def reset_candidate_strikes(candidate_id: str) -> None:
    """Resets candidate strikes."""
    await redis_client.delete(get_strike_key(candidate_id))
