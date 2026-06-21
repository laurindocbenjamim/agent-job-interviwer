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

active_sessions = {}

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
        avatar_gender=settings.avatar_gender.lower(),
        agent_speech_speed=settings.agent_speech_speed,
        question_time_limit_seconds=settings.question_time_limit_seconds,
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
    active_sessions[candidate_id] = {}

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

                from src.shared.redis_client import redis_client
                yaw_val = await redis_client.get(f"cv_threshold:yaw:{candidate_id}")
                pitch_val = await redis_client.get(f"cv_threshold:pitch:{candidate_id}")
                bright_val = await redis_client.get(f"cv_threshold:brightness:{candidate_id}")
                gaze_min_val = await redis_client.get(f"cv_threshold:gaze_min:{candidate_id}")
                gaze_max_val = await redis_client.get(f"cv_threshold:gaze_max:{candidate_id}")

                yaw_thresh = float(yaw_val) if yaw_val is not None else 20.0
                pitch_thresh = float(pitch_val) if pitch_val is not None else 20.0
                brightness_thresh = float(bright_val) if bright_val is not None else 90.0
                gaze_min = float(gaze_min_val) if gaze_min_val is not None else 0.025
                gaze_max = float(gaze_max_val) if gaze_max_val is not None else 0.055

                is_violation, details, video_quality, annotated_frame = await asyncio.to_thread(
                    analyze_frame, frame, True, yaw_thresh, pitch_thresh, brightness_thresh, gaze_min, gaze_max
                )

                response_data = await evaluate_candidate_frame(
                    candidate_id=candidate_id,
                    is_violation=is_violation,
                    details=details,
                    video_quality=video_quality,
                )

                # Broadcast to admins if any are connected
                from src.domains.admin.router import admin_connections
                if candidate_id in admin_connections and admin_connections[candidate_id]:
                    _, buffer = cv2.imencode('.jpg', annotated_frame)
                    b64_image = base64.b64encode(buffer).decode('utf-8')
                    admin_payload = {
                        "image": f"data:image/jpeg;base64,{b64_image}",
                        "details": details,
                        "video_quality": video_quality,
                        "is_violation": is_violation,
                        "current_strikes": response_data.get("current_strikes", 0)
                    }
                    disconnected_admins = []
                    for admin_ws in admin_connections[candidate_id]:
                        try:
                            await admin_ws.send_json(admin_payload)
                        except Exception:
                            disconnected_admins.append(admin_ws)
                    for admin_ws in disconnected_admins:
                        admin_connections[candidate_id].remove(admin_ws)

                await websocket.send_json(response_data)
            except WebSocketDisconnect:
                break
            except RuntimeError as re:
                if "disconnect" in str(re).lower() or "receive" in str(re).lower():
                    break
                print(f"[WS DEBUG] Inner loop error for {candidate_id}: {re}")
            except Exception as inner_e:
                print(f"[WS DEBUG] Inner loop error for {candidate_id}: {inner_e}")

    except WebSocketDisconnect:
        await log_activity(candidate_id, "session_disconnected", {"status": "closed"})
    except Exception as outer_e:
        print(f"[WS DEBUG] Outer loop error for {candidate_id}: {outer_e}")
    finally:
        active_sessions.pop(candidate_id, None)

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

    channel_ref = {"channel": None}
    active_sessions[candidate_id] = {"tts_track": tts_track, "channel_ref": channel_ref}

    @pc.on("datachannel")
    def on_datachannel(channel):
        channel_ref["channel"] = channel

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            peer_connections.discard(pc)
            active_sessions.pop(candidate_id, None)
            await log_activity(candidate_id, "session_disconnected", {"status": pc.connectionState})

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            # Wrap the incoming video track with our custom tracker
            local_video = InterviewVideoStreamTrack(track, candidate_id)
            # Find an existing video transceiver with no sender track to reuse
            video_transceiver = next((t for t in pc.getTransceivers() if t.kind == "video" and t.sender.track is None), None)
            if video_transceiver:
                video_transceiver.sender.replaceTrack(local_video)
                video_transceiver.direction = "sendrecv"
            else:
                pc.addTrack(local_video)
            
            @track.on("ended")
            async def on_ended():
                await log_activity(candidate_id, "video_track_ended", {})
                
        elif track.kind == "audio":
            # Wrap the incoming audio track
            local_audio = InterviewAudioStreamTrack(track, candidate_id, tts_track, channel_ref)
            # Find an existing audio transceiver with no sender track to reuse
            audio_transceiver = next((t for t in pc.getTransceivers() if t.kind == "audio" and t.sender.track is None), None)
            if audio_transceiver:
                audio_transceiver.sender.replaceTrack(local_audio)
                audio_transceiver.direction = "sendrecv"
            else:
                pc.addTrack(local_audio)

    # Handle offer and create answer
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

from src.domains.interviews.agent import _sessions, generate_agent_response
from src.shared.database import save_interview_session
from src.domains.interviews.tts import generate_speech
import json

class SubmitRequest(BaseModel):
    answer: str = ""

@router.post("/interview/{candidate_id}/submit")
async def force_submit_answer(candidate_id: str, request: SubmitRequest):
    """Forces the LLM to generate the next question based on current history and user's answer."""
    response = await generate_agent_response(candidate_id, request.answer)
    
    session = active_sessions.get(candidate_id)
    if session:
        # Send JSON via DataChannel
        channel = session["channel_ref"].get("channel")
        if channel and channel.readyState == "open":
            try:
                channel.send(json.dumps(response))
            except Exception as e:
                print(f"Error sending datachannel message: {e}")
                
        # Send Audio via TTS track
        text_to_speak = response.get("text_to_speak", "")
        if text_to_speak:
            pcm_bytes = await generate_speech(text_to_speak)
            await session["tts_track"].add_audio(pcm_bytes)
            
    return response

@router.post("/interview/{candidate_id}/finalize")
async def finalize_interview(candidate_id: str):
    """Saves the interview data to MongoDB and cleans up the session."""
    session_data = _sessions.get(candidate_id, [])
    await save_interview_session(candidate_id, session_data)
    
    # Clean up memory
    if candidate_id in _sessions:
        del _sessions[candidate_id]
        
    return {"status": "success", "message": "Interview finalized and saved to MongoDB"}
