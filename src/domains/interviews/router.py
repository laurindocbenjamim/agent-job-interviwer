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

from pydantic import BaseModel
from aiortc import RTCPeerConnection, RTCSessionDescription
from src.domains.interviews.webrtc import InterviewVideoStreamTrack, InterviewAudioStreamTrack, TTSAudioStreamTrack

# Store peer connections to prevent garbage collection and allow cleanup
peer_connections = set()

class OfferRequest(BaseModel):
    sdp: str
    type: str

@router.post("/interview/{candidate_id}/offer")
async def offer(candidate_id: str, offer_request: OfferRequest):
    """WebRTC signaling endpoint. Accepts an SDP offer and returns an answer."""
    offer = RTCSessionDescription(sdp=offer_request.sdp, type=offer_request.type)
    pc = RTCPeerConnection()
    peer_connections.add(pc)
    
    # Setup TTS Audio Track to send to the candidate
    tts_track = TTSAudioStreamTrack()
    pc.addTrack(tts_track)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            peer_connections.discard(pc)
            await log_activity(candidate_id, "session_disconnected", {"status": pc.connectionState})

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            # Wrap the incoming video track with our custom tracker
            local_video = InterviewVideoStreamTrack(track, candidate_id)
            pc.addTrack(local_video)
            
            @track.on("ended")
            async def on_ended():
                await log_activity(candidate_id, "video_track_ended", {})
                
        elif track.kind == "audio":
            # Wrap the incoming audio track
            local_audio = InterviewAudioStreamTrack(track, candidate_id, tts_track)
            pc.addTrack(local_audio)

    # Handle offer and create answer
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
