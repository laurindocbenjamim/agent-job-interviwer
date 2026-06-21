import os
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
    """WebSocket stream for admin to receive real-time video and CV metrics."""
    await websocket.accept()
    if candidate_id not in admin_connections:
        admin_connections[candidate_id] = []
    admin_connections[candidate_id].append(websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in admin_connections.get(candidate_id, []):
            admin_connections[candidate_id].remove(websocket)
        if not admin_connections.get(candidate_id):
            admin_connections.pop(candidate_id, None)

from pydantic import BaseModel
from src.shared.redis_client import redis_client

class CVSettings(BaseModel):
    yaw_thresh: float
    pitch_thresh: float
    brightness_thresh: float
    gaze_min: float = 0.025
    gaze_max: float = 0.055

@router.post("/cv-settings/{candidate_id}")
async def update_cv_settings(candidate_id: str, settings: CVSettings):
    """Updates CV thresholds for a candidate in Redis."""
    await redis_client.set(f"cv_threshold:yaw:{candidate_id}", settings.yaw_thresh, ex=7200)
    await redis_client.set(f"cv_threshold:pitch:{candidate_id}", settings.pitch_thresh, ex=7200)
    await redis_client.set(f"cv_threshold:brightness:{candidate_id}", settings.brightness_thresh, ex=7200)
    await redis_client.set(f"cv_threshold:gaze_min:{candidate_id}", settings.gaze_min, ex=7200)
    await redis_client.set(f"cv_threshold:gaze_max:{candidate_id}", settings.gaze_max, ex=7200)
    return {"status": "success"}

@router.post("/voice/clone")
async def clone_voice(file: UploadFile = File(...)):
    """Accepts an audio file upload and saves it to be used as a reference for Coqui TTS XTTS-v2."""
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an audio file.")
        
    os.makedirs(VOICE_DIR, exist_ok=True)
    
    file_location = os.path.join(VOICE_DIR, "cloned_voice.wav")
    
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save audio file: {str(e)}")
        
    return {"status": "success", "message": "Voice cloned successfully.", "filename": file.filename}
