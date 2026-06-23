import uuid
from typing import Any
from src.shared.redis_client import redis_client
from src.shared.postgres_db import save_postgres_config, get_postgres_config, get_all_postgres_configs, delete_postgres_configs
from src.domains.admin.state import admin_connections


DEFAULTS = {
    "interview_duration_minutes": 30, "avatar_gender": "female", "question_time_limit_seconds": 60,
    "num_questions": 5, "interview_objective": "Assess engineering skills and culture fit.",
    "interview_topics": "Experience with FastAPI and Async Python,System design concepts,Handling real-time streaming data pipelines",
    "speech_language": "en-US", "text_language": "en", "candidate_name": "", "job_specialty": "", "is_active": True
}


async def update_cv_settings(candidate_id: str, settings: dict) -> dict:
    await redis_client.set(f"cv_threshold:yaw:{candidate_id}", settings["yaw_thresh"], ex=7200)
    await redis_client.set(f"cv_threshold:pitch:{candidate_id}", settings["pitch_thresh"], ex=7200)
    await redis_client.set(f"cv_threshold:brightness:{candidate_id}", settings["brightness_thresh"], ex=7200)
    await redis_client.set(f"cv_threshold:gaze_min:{candidate_id}", settings["gaze_min"], ex=7200)
    await redis_client.set(f"cv_threshold:gaze_max:{candidate_id}", settings["gaze_max"], ex=7200)
    return {"status": "success"}


async def update_audio_settings(candidate_id: str, settings: dict) -> dict:
    await redis_client.set(f"cv_threshold:mic_gain:{candidate_id}", settings["mic_gain"], ex=7200)
    await redis_client.set(f"cv_threshold:noise_thresh:{candidate_id}", settings["noise_thresh"], ex=7200)
    return {"status": "success"}


async def get_candidate_config(candidate_id: str) -> dict:
    config = await get_postgres_config(candidate_id)
    if not config:
        return DEFAULTS
    return {k: getattr(config, k, DEFAULTS[k]) or "" for k in DEFAULTS}


async def update_candidate_config(candidate_id: str, data: dict) -> dict:
    await save_postgres_config(candidate_id, data)
    return {"status": "success", "message": "Configuration updated successfully"}


async def create_candidate(data: dict) -> dict:
    candidate_uuid = str(uuid.uuid4())
    default_config = {
        "interview_duration_minutes": 30,
        "avatar_gender": "female",
        "question_time_limit_seconds": 60,
        "num_questions": 5,
        "interview_objective": f"Assess engineering skills and culture fit for a {data['job_specialty']} role.",
        "interview_topics": f"Experience with {data['job_specialty']},FastAPI and Async Python,System design concepts",
        "speech_language": "en-US",
        "text_language": "en",
        "candidate_name": data["name"],
        "job_specialty": data["job_specialty"],
        "is_active": True
    }
    await save_postgres_config(candidate_uuid, default_config)
    return {
        "status": "success",
        "candidate_id": candidate_uuid,
        "candidate_name": data["name"],
        "job_specialty": data["job_specialty"]
    }


async def get_all_candidates() -> list:
    configs = await get_all_postgres_configs()
    return [{
        "candidate_id": c.candidate_id,
        "candidate_name": c.candidate_name or "",
        "job_specialty": c.job_specialty or "",
        "is_active": c.is_active,
        "num_questions": c.num_questions,
        "interview_duration_minutes": c.interview_duration_minutes
    } for c in configs]


async def delete_candidates(candidate_ids: list[str]) -> dict:
    await delete_postgres_configs(candidate_ids)
    return {"status": "success", "message": f"{len(candidate_ids)} candidates deleted successfully."}


async def get_active_sessions() -> list:
    from src.domains.interviews.state import active_sessions
    from src.shared.redis_client import get_candidate_strikes
    ids = list(active_sessions.keys())
    details = []
    for cid in ids:
        strikes = await get_candidate_strikes(cid)
        details.append({
            "candidate_id": cid,
            "strikes": strikes,
            "status": "Live" if strikes < 3 else "Flagged"
        })
    return {"active_sessions": ids, "active_sessions_details": details}


def register_admin(websocket, candidate_id: str):
    if candidate_id not in admin_connections:
        admin_connections[candidate_id] = []
    admin_connections[candidate_id].append(websocket)


def unregister_admin(websocket, candidate_id: str):
    if candidate_id in admin_connections and websocket in admin_connections[candidate_id]:
        admin_connections[candidate_id].remove(websocket)
