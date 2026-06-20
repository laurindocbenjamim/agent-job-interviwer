import asyncio
import base64
import json
import cv2
import numpy as np
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse

from src.domains.interviews.video_analyzer import analyze_frame
from src.domains.interviews.service import evaluate_candidate_frame
from src.shared.database import log_activity

router = APIRouter()

# Locate the template path relative to project layout
TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "shared" / "templates" / "interview.html"

@router.get("/interview/{candidate_id}", response_class=HTMLResponse)
async def serve_interview_console(candidate_id: str):
    """
    Serves the dashboard HTML page for a candidate.
    """
    if not TEMPLATE_PATH.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
        
    html_content = TEMPLATE_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=html_content)

@router.websocket("/ws/interview/{candidate_id}")
async def interview_stream(websocket: WebSocket, candidate_id: str):
    """
    Main WebSocket processing stream for camera frames and candidate compliance verification.
    """
    await websocket.accept()
    
    try:
        while True:
            try:
                # 1. Receive JSON packet containing the image frame
                data = await websocket.receive_text()
                payload = json.loads(data)
                
                # Allow skipping frames if they are not image updates
                if "image" not in payload:
                    continue
                    
                # 2. Decode the base64 BGR/RGB image frame
                try:
                    base64_data = payload["image"].split(",")[1]
                    image_bytes = base64.b64decode(base64_data)
                    np_array = np.frombuffer(image_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
                except Exception as e:
                    print(f"[WS DEBUG] Base64 decode failed for candidate {candidate_id}: {e}")
                    continue
                    
                if frame is None:
                    print(f"[WS DEBUG] Decoded frame is None for candidate {candidate_id}")
                    continue
                    
                # 3. Analyze the frame (gaze, lighting)
                is_violation, details, video_quality = await asyncio.to_thread(analyze_frame, frame)
                
                # 4. Evaluate strikes and compliance using the service
                response_data = await evaluate_candidate_frame(
                    candidate_id=candidate_id,
                    is_violation=is_violation,
                    details=details,
                    video_quality=video_quality
                )
                
                # 5. Send rules directive back to candidate console
                await websocket.send_json(response_data)
            except Exception as inner_e:
                print(f"[WS DEBUG] Inner loop error for candidate {candidate_id}: {inner_e}")
                
    except WebSocketDisconnect:
        # Asynchronously log disconnect event
        await log_activity(candidate_id, "session_disconnected", {"status": "closed"})
    except Exception as outer_e:
        print(f"[WS DEBUG] Outer loop error for candidate {candidate_id}: {outer_e}")
