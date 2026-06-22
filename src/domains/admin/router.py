import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

router = APIRouter(prefix="/admin", tags=["admin"])

VOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "voices")

# Mapping from candidate_id to a list of connected admin WebSockets
admin_connections = {}

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "shared" / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard():
    """Serves the real-time admin dashboard HTML."""
    try:
        template = jinja_env.get_template("admin_dashboard.html")
    except Exception:
        raise HTTPException(status_code=404, detail="Template file not found")
    
    rendered = template.render()
    return HTMLResponse(content=rendered)

@router.get("/sessions")
async def get_active_sessions():
    """Returns a list of currently active candidate IDs and their details."""
    from src.domains.interviews.router import active_sessions
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
    return {
        "active_sessions": ids,
        "active_sessions_details": details
    }

@router.websocket("/ws/interview/{candidate_id}")
async def admin_interview_stream(websocket: WebSocket, candidate_id: str):
    """WebSocket stream for admin to receive real-time video and CV metrics via Redis Pub/Sub."""
    await websocket.accept()
    
    if candidate_id not in admin_connections:
        admin_connections[candidate_id] = []
    admin_connections[candidate_id].append(websocket)

    from src.shared.redis_client import redis_client
    import asyncio
    
    # Send cached device telemetry if it exists
    device_data = await redis_client.get(f"telemetry:device:{candidate_id}")
    if device_data:
        try:
            await websocket.send_text(device_data.decode('utf-8') if isinstance(device_data, bytes) else device_data)
        except Exception:
            pass

    # Send current question from transcript
    from src.domains.interviews.agent import _sessions
    import json
    transcript = _sessions.get(candidate_id, [])
    if transcript:
        last_agent = None
        for msg in transcript:
            if isinstance(msg, tuple) and len(msg) >= 2:
                if msg[0] == "assistant":
                    try:
                        # Extract the actual text_to_speak from the JSON payload if possible
                        data = json.loads(msg[1])
                        last_agent = data.get("text_to_speak", "")
                    except Exception:
                        last_agent = msg[1]
        if last_agent:
            try:
                await websocket.send_text(json.dumps({"agent_text": last_agent}))
            except Exception:
                pass
            
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if candidate_id in admin_connections and websocket in admin_connections[candidate_id]:
            admin_connections[candidate_id].remove(websocket)

from pydantic import BaseModel
from src.shared.redis_client import redis_client

class CVSettings(BaseModel):
    yaw_thresh: float
    pitch_thresh: float
    brightness_thresh: float
    gaze_min: float = 0.025
    gaze_max: float = 0.055

class AudioSettings(BaseModel):
    mic_gain: float
    noise_thresh: float = 0.055

@router.post("/cv-settings/{candidate_id}")
async def update_cv_settings(candidate_id: str, settings: CVSettings):
    """Updates CV thresholds for a candidate in Redis."""
    await redis_client.set(f"cv_threshold:yaw:{candidate_id}", settings.yaw_thresh, ex=7200)
    await redis_client.set(f"cv_threshold:pitch:{candidate_id}", settings.pitch_thresh, ex=7200)
    await redis_client.set(f"cv_threshold:brightness:{candidate_id}", settings.brightness_thresh, ex=7200)
    await redis_client.set(f"cv_threshold:gaze_min:{candidate_id}", settings.gaze_min, ex=7200)
    await redis_client.set(f"cv_threshold:gaze_max:{candidate_id}", settings.gaze_max, ex=7200)
    return {"status": "success"}

@router.post("/audio-settings/{candidate_id}")
async def update_audio_settings(candidate_id: str, settings: AudioSettings):
    """Updates Audio settings for a candidate in Redis."""
    await redis_client.set(f"cv_threshold:mic_gain:{candidate_id}", settings.mic_gain, ex=7200)
    await redis_client.set(f"cv_threshold:noise_thresh:{candidate_id}", settings.noise_thresh, ex=7200)
    return {"status": "success"}

@router.post("/voice/clone")
async def clone_voice(file: UploadFile = File(...)):
    if not file.content_type.startswith("audio/"):
        raise HTTPException(400, "Uploaded file must be an audio file.")
    os.makedirs(VOICE_DIR, exist_ok=True)
    with open(os.path.join(VOICE_DIR, "cloned_voice.wav"), "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"status": "success", "message": "Voice cloned successfully.", "filename": file.filename}

class InjectedQuestion(BaseModel):
    question: str

@router.post("/inject-question/{candidate_id}")
async def inject_question(candidate_id: str, payload: InjectedQuestion):
    """Queues a custom question from the admin to be asked to the candidate."""
    from src.domains.interviews.agent import queue_injected_question
    queue_injected_question(candidate_id, payload.question)
    return {"status": "success", "message": "Question queued successfully."}

class InterviewConfigSchema(BaseModel):
    interview_duration_minutes: int
    avatar_gender: str
    question_time_limit_seconds: int
    num_questions: int
    interview_objective: str
    interview_topics: str
    speech_language: str
    text_language: str
    candidate_name: Optional[str] = None
    job_specialty: Optional[str] = None
    is_active: bool

DEFAULTS = {
    "interview_duration_minutes": 30, "avatar_gender": "female", "question_time_limit_seconds": 60,
    "num_questions": 5, "interview_objective": "Assess engineering skills and culture fit.",
    "interview_topics": "Experience with FastAPI and Async Python,System design concepts,Handling real-time streaming data pipelines",
    "speech_language": "en-US", "text_language": "en", "candidate_name": "", "job_specialty": "", "is_active": True
}

@router.get("/config/{candidate_id}")
async def get_candidate_config(candidate_id: str):
    """Fetches the candidate configuration from Postgres, or defaults if not set."""
    from src.shared.postgres_db import get_postgres_config
    config = await get_postgres_config(candidate_id)
    if not config:
        return DEFAULTS
    return {k: getattr(config, k, DEFAULTS[k]) or "" for k in DEFAULTS}

@router.post("/config/{candidate_id}")
async def update_candidate_config(candidate_id: str, payload: InterviewConfigSchema):
    """Updates candidate configuration in Postgres."""
    from src.shared.postgres_db import save_postgres_config
    config = await save_postgres_config(candidate_id, payload.model_dump())
    return {"status": "success", "message": "Configuration updated successfully"}

import uuid
from typing import Optional

class CreateCandidateSchema(BaseModel):
    name: str
    job_specialty: str

@router.post("/candidate/create")
async def create_candidate(payload: CreateCandidateSchema):
    """Creates a new candidate with an automatically generated UUID."""
    from src.shared.postgres_db import save_postgres_config
    candidate_uuid = str(uuid.uuid4())
    
    default_config = {
        "interview_duration_minutes": 30,
        "avatar_gender": "female",
        "question_time_limit_seconds": 60,
        "num_questions": 5,
        "interview_objective": f"Assess engineering skills and culture fit for a {payload.job_specialty} role.",
        "interview_topics": f"Experience with {payload.job_specialty},FastAPI and Async Python,System design concepts",
        "speech_language": "en-US",
        "text_language": "en",
        "candidate_name": payload.name,
        "job_specialty": payload.job_specialty,
        "is_active": True
    }
    
    await save_postgres_config(candidate_uuid, default_config)
    return {
        "status": "success",
        "candidate_id": candidate_uuid,
        "candidate_name": payload.name,
        "job_specialty": payload.job_specialty
    }

@router.get("/candidates")
async def get_all_candidates():
    """Returns a list of all candidate configurations from Postgres."""
    from src.shared.postgres_db import get_all_postgres_configs
    configs = await get_all_postgres_configs()
    return [{
        "candidate_id": c.candidate_id,
        "candidate_name": c.candidate_name or "",
        "job_specialty": c.job_specialty or "",
        "is_active": c.is_active,
        "num_questions": c.num_questions,
        "interview_duration_minutes": c.interview_duration_minutes
    } for c in configs]

class DeleteCandidatesSchema(BaseModel):
    candidate_ids: list[str]

@router.delete("/candidates")
async def delete_candidates(payload: DeleteCandidatesSchema):
    """Deletes one or more candidates."""
    from src.shared.postgres_db import delete_postgres_configs
    await delete_postgres_configs(payload.candidate_ids)
    return {"status": "success", "message": f"{len(payload.candidate_ids)} candidates deleted successfully."}

@router.get("/candidates-directory", response_class=HTMLResponse)
async def candidates_directory():
    """Serves the candidates directory HTML page."""
    return HTMLResponse(content=jinja_env.get_template("admin_candidates.html").render())

@router.get("/voice-cloning", response_class=HTMLResponse)
async def voice_cloning_page():
    """Serves the voice cloning studio HTML page."""
    return HTMLResponse(content=jinja_env.get_template("admin_voice_cloning.html").render())

