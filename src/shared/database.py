import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from src.config.settings import settings

# Global motor client instance
client: AsyncIOMotorClient = AsyncIOMotorClient(settings.mongodb_uri)
db = client[settings.mongodb_db_name]
logs_collection = db[settings.mongodb_collection]

async def log_activity(candidate_id: str, event_type: str, details: dict) -> None:
    """Asynchronously saves tracking data or alert events directly to MongoDB."""
    log_entry = {
        "candidate_id": candidate_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "event_type": event_type,
        "details": details
    }
    await logs_collection.insert_one(log_entry)

async def get_violation_events(candidate_id: str) -> list:
    """Retrieves all strike_issued events for a candidate from MongoDB."""
    cursor = logs_collection.find(
        {"candidate_id": candidate_id, "event_type": "strike_issued"},
        {"_id": 0}
    ).sort("timestamp", 1)
    return await cursor.to_list(length=500)

async def save_interview_session(candidate_id: str, session_data: list) -> None:
    """Saves the final interview transcript session to MongoDB."""
    document = {
        "candidate_id": candidate_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc),
        "event_type": "interview_finalized",
        "transcript": session_data
    }
    await logs_collection.insert_one(document)

async def get_interview_session(candidate_id: str) -> list:
    """Retrieves the final interview transcript session from MongoDB."""
    document = await logs_collection.find_one(
        {"candidate_id": candidate_id, "event_type": "interview_finalized"},
        {"_id": 0}
    )
    if document:
        return document.get("transcript", [])
    return []

