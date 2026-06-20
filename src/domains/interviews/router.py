import asyncio
import base64
import json
import cv2
import numpy as np
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

from src.domains.interviews.video_analyzer import analyze_frame
from src.domains.interviews.service import evaluate_candidate_frame
from src.domains.interviews.schemas import ViolationsReport, ViolationEvent
from src.shared.database import log_activity, get_violation_events
from src.config.settings import settings

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "shared" / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

@router.get("/interview/{candidate_id}", response_class=HTMLResponse)
async def serve_interview_console(candidate_id: str):
    """Serves the dashboard HTML page with injected configuration."""
    try:
        template = jinja_env.get_template("interview.html")
    except Exception:
        raise HTTPException(status_code=404, detail="Template file not found")

    rendered = template.render(
        interview_duration_minutes=settings.interview_duration_minutes,
        total_user_attempt=settings.total_user_attempt,
    )
    return HTMLResponse(content=rendered)

@router.get("/interview/{candidate_id}/violations")
async def get_violations_report(candidate_id: str):
    """Returns aggregated violations for a candidate after the interview."""
    raw_events = await get_violation_events(candidate_id)

    events = [
        ViolationEvent(
            timestamp=e["timestamp"].isoformat() if hasattr(e["timestamp"], "isoformat") else str(e["timestamp"]),
            violation_type=e.get("details", {}).get("cause", {}).get("status", "gaze_deviation"),
            details=e.get("details", {}),
            strike_number=e.get("details", {}).get("strike_count"),
        )
        for e in raw_events
    ]

    report = ViolationsReport(
        candidate_id=candidate_id,
        total_violations=len(events),
        total_strikes=max((ev.strike_number or 0 for ev in events), default=0),
        events=events,
    )
    return report.model_dump()

@router.websocket("/ws/interview/{candidate_id}")
async def interview_stream(websocket: WebSocket, candidate_id: str):
    """WebSocket stream for camera frames and compliance verification."""
    await websocket.accept()

    try:
        while True:
            try:
                data = await websocket.receive_text()
                payload = json.loads(data)

                if "image" not in payload:
                    continue

                try:
                    base64_data = payload["image"].split(",")[1]
                    image_bytes = base64.b64decode(base64_data)
                    np_array = np.frombuffer(image_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
                except Exception as e:
                    print(f"[WS DEBUG] Base64 decode failed for {candidate_id}: {e}")
                    continue

                if frame is None:
                    continue

                is_violation, details, video_quality = await asyncio.to_thread(analyze_frame, frame)

                response_data = await evaluate_candidate_frame(
                    candidate_id=candidate_id,
                    is_violation=is_violation,
                    details=details,
                    video_quality=video_quality,
                )

                await websocket.send_json(response_data)
            except Exception as inner_e:
                print(f"[WS DEBUG] Inner loop error for {candidate_id}: {inner_e}")

    except WebSocketDisconnect:
        await log_activity(candidate_id, "session_disconnected", {"status": "closed"})
    except Exception as outer_e:
        print(f"[WS DEBUG] Outer loop error for {candidate_id}: {outer_e}")
