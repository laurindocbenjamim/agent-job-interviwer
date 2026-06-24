import os
import json
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from src.domains.admin.schemas import CVSettings, AudioSettings, InjectedQuestion, InterviewConfigSchema, CreateCandidateSchema, DeleteCandidatesSchema
from src.domains.admin.service import update_cv_settings, update_audio_settings, get_candidate_config, update_candidate_config, create_candidate, get_all_candidates, delete_candidates, get_active_sessions, register_admin, unregister_admin
from src.domains.admin.state import admin_connections
from src.shared.redis_client import redis_client

router = APIRouter(prefix="/admin", tags=["admin"])

VOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "voices")
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "shared" / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard():
    try:
        template = jinja_env.get_template("admin_dashboard.html")
    except Exception:
        raise HTTPException(status_code=404, detail="Template file not found")
    return HTMLResponse(content=template.render())


@router.get("/sessions")
async def admin_get_active_sessions():
    return await get_active_sessions()


@router.websocket("/ws/interview/{candidate_id}")
async def admin_interview_stream(websocket: WebSocket, candidate_id: str):
    await websocket.accept()
    register_admin(websocket, candidate_id)

    device_data = await redis_client.get(f"telemetry:device:{candidate_id}")
    if device_data:
        try:
            await websocket.send_text(device_data.decode('utf-8') if isinstance(device_data, bytes) else device_data)
        except Exception:
            pass

    from src.domains.interviews.ai.agent import _sessions
    transcript = _sessions.get(candidate_id, [])
    if transcript:
        last_agent = None
        for msg in transcript:
            if isinstance(msg, tuple) and len(msg) >= 2 and msg[0] == "assistant":
                try:
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
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        unregister_admin(websocket, candidate_id)


@router.post("/cv-settings/{candidate_id}")
async def admin_update_cv_settings(candidate_id: str, settings: CVSettings):
    return await update_cv_settings(candidate_id, settings.model_dump())


@router.post("/audio-settings/{candidate_id}")
async def admin_update_audio_settings(candidate_id: str, settings: AudioSettings):
    return await update_audio_settings(candidate_id, settings.model_dump())


@router.post("/voice/clone")
async def clone_voice(file: UploadFile = File(...)):
    if not file.content_type.startswith("audio/"):
        raise HTTPException(400, "Uploaded file must be an audio file.")
    os.makedirs(VOICE_DIR, exist_ok=True)
    with open(os.path.join(VOICE_DIR, "cloned_voice.wav"), "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"status": "success", "message": "Voice cloned successfully.", "filename": file.filename}


@router.get("/voice/file")
async def get_cloned_voice():
    from fastapi.responses import FileResponse
    voice_path = os.path.join(VOICE_DIR, "cloned_voice.wav")
    if os.path.exists(voice_path):
        return FileResponse(voice_path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="No cloned voice found.")


@router.delete("/voice/file")
async def delete_cloned_voice():
    voice_path = os.path.join(VOICE_DIR, "cloned_voice.wav")
    if os.path.exists(voice_path):
        os.remove(voice_path)
        return {"status": "success", "message": "Cloned voice deleted."}
    raise HTTPException(status_code=404, detail="No cloned voice found.")


@router.post("/inject-question/{candidate_id}")
async def admin_inject_question(candidate_id: str, payload: InjectedQuestion):
    from src.domains.interviews.ai.agent import queue_injected_question
    queue_injected_question(candidate_id, payload.question)
    return {"status": "success", "message": "Question queued successfully."}


@router.get("/config/{candidate_id}")
async def admin_get_config(candidate_id: str):
    return await get_candidate_config(candidate_id)


@router.post("/config/{candidate_id}")
async def admin_update_config(candidate_id: str, payload: InterviewConfigSchema):
    return await update_candidate_config(candidate_id, payload.model_dump())


@router.post("/candidate/create")
async def admin_create_candidate(payload: CreateCandidateSchema):
    return await create_candidate(payload.model_dump())


@router.get("/candidates")
async def admin_get_candidates():
    return await get_all_candidates()


@router.delete("/candidates")
async def admin_delete_candidates(payload: DeleteCandidatesSchema):
    return await delete_candidates(payload.candidate_ids)


@router.get("/candidates-directory", response_class=HTMLResponse)
async def candidates_directory():
    return HTMLResponse(content=jinja_env.get_template("admin_candidates.html").render())


@router.get("/voice-cloning", response_class=HTMLResponse)
async def voice_cloning_page():
    return HTMLResponse(content=jinja_env.get_template("admin_voice_cloning.html").render())


@router.get("/report/{candidate_id}/pdf", response_class=HTMLResponse)
async def admin_get_pdf_report(candidate_id: str):
    import datetime
    from src.domains.admin.report_agent import ReportAgent
    
    agent = ReportAgent()
    report_text = await agent.generate_report(candidate_id)
    
    # Fetch times for the header
    try:
        start_val = await redis_client.get(f"cv_threshold:start_time:{candidate_id}")
        start_time = start_val.decode() if isinstance(start_val, bytes) else start_val
    except Exception:
        start_time = "N/A"
        
    try:
        end_val = await redis_client.get(f"cv_threshold:end_time:{candidate_id}")
        end_time = end_val.decode() if isinstance(end_val, bytes) else end_val
    except Exception:
        end_time = "N/A"

    try:
        template = jinja_env.get_template("pdf_report.html")
    except Exception:
        raise HTTPException(status_code=404, detail="PDF Template file not found")
        
    return HTMLResponse(content=template.render(
        candidate_id=candidate_id,
        date=datetime.datetime.now().strftime("%Y-%m-%d"),
        start_time=start_time if start_time else "N/A",
        end_time=end_time if end_time else "N/A",
        report_text=report_text
    ))
