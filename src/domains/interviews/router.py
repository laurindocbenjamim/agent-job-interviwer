import json
from pathlib import Path
from fastapi import APIRouter, WebSocket
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from aiortc import RTCPeerConnection, RTCSessionDescription
from src.domains.interviews.schemas import OfferRequest, SubmitRequest, DeviceTelemetry
from src.domains.interviews.state import active_sessions, peer_connections
from src.domains.interviews.websocket import interview_stream
from src.domains.interviews.rtc.webrtc import InterviewVideoStreamTrack, InterviewAudioStreamTrack, TTSAudioStreamTrack
from src.domains.interviews.ai.agent import generate_agent_response
from src.domains.interviews.ai.compliance_agent import ComplianceAnalystAgent
from src.domains.interviews.ai.tts import generate_speech
from src.shared.database import log_activity, get_violation_events, save_interview_session, get_interview_session
from src.shared.redis_client import redis_client
from src.config.settings import settings

router = APIRouter()

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "shared" / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


@router.get("/interview/{candidate_id}", response_class=HTMLResponse)
async def serve_interview_console(candidate_id: str):
    from src.shared.postgres_db import get_postgres_config
    config = await get_postgres_config(candidate_id)
    if config:
        rendered = jinja_env.get_template("interview.html").render(
            interview_duration_minutes=config.interview_duration_minutes,
            total_user_attempt=settings.total_user_attempt,
            avatar_gender=config.avatar_gender.lower(),
            agent_speech_speed=settings.agent_speech_speed,
            question_time_limit_seconds=config.question_time_limit_seconds,
            is_active=config.is_active,
            speech_language=config.speech_language,
            text_language=config.text_language
        )
        return HTMLResponse(content=rendered)
    html_content = """<!DOCTYPE html><html lang="en" data-theme="dark">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Interview Not Available</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>body{font-family:'Outfit',sans-serif;background:#000;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:rgba(255,255,255,.05);padding:3rem;border-radius:1rem;border:1px solid rgba(255,255,255,.1);text-align:center}
.icon{font-size:4rem;margin-bottom:1rem;display:block}
h1{margin:0 0 .5rem 0;font-size:2rem;color:#ef4444}
p{margin:0;color:#94a3b8}</style></head>
<body><div class="card"><span class="icon">🚫</span><h1>Interview Not Available</h1>
<p>The requested interview session could not be found or has expired.</p></div></body></html>"""
    return HTMLResponse(content=html_content, status_code=404)


@router.get("/interview/{candidate_id}/violations")
async def get_violations_report(candidate_id: str):
    from src.domains.interviews.schemas import ViolationEvent, ViolationsReport
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
    result = report.model_dump()
    try:
        start_val = await redis_client.get(f"cv_threshold:start_time:{candidate_id}")
        result["start_time"] = start_val.decode() if isinstance(start_val, bytes) else start_val
    except Exception:
        result["start_time"] = None
    try:
        end_val = await redis_client.get(f"cv_threshold:end_time:{candidate_id}")
        result["end_time"] = end_val.decode() if isinstance(end_val, bytes) else end_val
    except Exception:
        result["end_time"] = None
    from src.domains.interviews.ai.agent import _sessions
    try:
        transcript = _sessions.get(candidate_id, [])
        if not transcript:
            transcript = await get_interview_session(candidate_id)
    except Exception:
        transcript = []
    result["transcript"] = transcript
    result["compliance_analysis"] = await ComplianceAnalystAgent().analyze(candidate_id, result)
    return result


@router.websocket("/ws/interview/{candidate_id}")
async def ws_interview_stream(websocket: WebSocket, candidate_id: str):
    await interview_stream(websocket, candidate_id)


@router.post("/interview/{candidate_id}/offer")
async def offer(candidate_id: str, offer_request: OfferRequest):
    offer = RTCSessionDescription(sdp=offer_request.sdp, type=offer_request.type)
    pc = RTCPeerConnection()
    peer_connections.add(pc)

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
        if pc.connectionState in ("failed", "closed"):
            await pc.close()
            peer_connections.discard(pc)
            active_sessions.pop(candidate_id, None)
            await log_activity(candidate_id, "session_disconnected", {"status": pc.connectionState})

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            local_video = InterviewVideoStreamTrack(track, candidate_id)
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
            local_audio = InterviewAudioStreamTrack(track, candidate_id, tts_track, channel_ref)
            audio_transceiver = next((t for t in pc.getTransceivers() if t.kind == "audio" and t.sender.track is None), None)
            if audio_transceiver:
                audio_transceiver.sender.replaceTrack(local_audio)
                audio_transceiver.direction = "sendrecv"
            else:
                pc.addTrack(local_audio)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


@router.post("/interview/{candidate_id}/start")
async def start_interview(candidate_id: str):
    import datetime
    from src.domains.interviews.rtc.webrtc import InterviewAudioStreamTrack
    
    session = active_sessions.get(candidate_id)
    if not session:
        return {"status": "error", "message": "Session not found"}
        
    # Find the audio track and enable interview mode
    pc = next((p for p in peer_connections if getattr(p, "candidate_id", None) == candidate_id), None)
    # The transceiver holds the sender with the track, but since we have a reference to active_sessions it might not have the track directly.
    # Wait, pc.getTransceivers() doesn't expose candidate_id. We can search pc's receivers.
    # A more robust way is to just set it on all InterviewAudioStreamTrack for this candidate.
    import gc
    for obj in gc.get_objects():
        if isinstance(obj, InterviewAudioStreamTrack) and obj.candidate_id == candidate_id:
            obj.is_interview_started = True

    start_time = datetime.datetime.utcnow().isoformat()
    await redis_client.set(f"cv_threshold:start_time:{candidate_id}", start_time)
    
    from src.domains.admin.state import admin_connections
    import json
    if candidate_id in admin_connections:
        payload = json.dumps({"start_time": start_time})
        for admin_ws in admin_connections[candidate_id]:
            try:
                import asyncio
                asyncio.create_task(admin_ws.send_text(payload))
            except Exception:
                pass
                
    return {"status": "success", "start_time": start_time}


@router.post("/interview/{candidate_id}/submit")
async def force_submit_answer(candidate_id: str, request: SubmitRequest):
    from src.domains.admin.state import admin_connections
    response = await generate_agent_response(candidate_id, request.answer)
    session = active_sessions.get(candidate_id)
    if session:
        channel = session["channel_ref"].get("channel")
        if channel and channel.readyState == "open":
            try:
                channel.send(json.dumps(response))
            except Exception as e:
                print(f"Error sending datachannel message: {e}")
    text_to_speak = response.get("text_to_speak", "")
    if text_to_speak:
        pcm_bytes = await generate_speech(text_to_speak)
        await session["tts_track"].add_audio(pcm_bytes)
        if candidate_id in admin_connections:
            payload = json.dumps({"agent_text": text_to_speak})
            for admin_ws in admin_connections[candidate_id]:
                try:
                    await admin_ws.send_text(payload)
                except Exception:
                    pass
    return response


@router.post("/interview/{candidate_id}/finalize")
async def finalize_interview(candidate_id: str):
    import datetime
    
    end_time = datetime.datetime.utcnow().isoformat()
    await redis_client.set(f"cv_threshold:end_time:{candidate_id}", end_time)
    
    from src.domains.admin.state import admin_connections
    import json
    if candidate_id in admin_connections:
        payload = json.dumps({"end_time": end_time})
        for admin_ws in admin_connections[candidate_id]:
            try:
                import asyncio
                asyncio.create_task(admin_ws.send_text(payload))
            except Exception:
                pass
    
    session = active_sessions.pop(candidate_id, None)
    if not session:
        return {"status": "error", "message": "Session not found"}
        
    # Stop TTS processing
    if "tts_track" in session:
        session["tts_track"].clear_queue()
        
    # Stop the agent transcript generation 
    import gc
    from src.domains.interviews.rtc.webrtc import InterviewAudioStreamTrack
    for obj in gc.get_objects():
        if isinstance(obj, InterviewAudioStreamTrack) and obj.candidate_id == candidate_id:
            obj.is_interview_started = False
            
    transcript = session.get("transcript", [])
    await save_interview_session(candidate_id, transcript)
    return {"status": "success", "message": "Interview finalized", "end_time": end_time}


@router.post("/interview/{candidate_id}/telemetry/device")
async def receive_device_telemetry(candidate_id: str, payload: DeviceTelemetry):
    from src.domains.admin.state import admin_connections
    data = {"action": "telemetry", "device": payload.device, "location": payload.location}
    await redis_client.set(f"telemetry:device:{candidate_id}", json.dumps(data), ex=7200)
    if candidate_id in admin_connections:
        for admin_ws in admin_connections[candidate_id]:
            try:
                await admin_ws.send_text(json.dumps(data))
            except Exception:
                pass
    return {"status": "success"}
