import asyncio
from redis.asyncio import Redis

async def main():
    r = Redis.from_url('redis://localhost:6379/0', decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe('admin_telemetry:31f18a80-c4d2-4a44-8eeb-5754a1d38a29')
    print("Listening for messages...")
    async for msg in pubsub.listen():
        if msg['type'] == 'message':
            print("Received:", msg['data'])
            break

asyncio.run(main())
