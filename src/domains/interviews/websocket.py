import asyncio
import base64
import json
import datetime
import cv2
import numpy as np
from fastapi import WebSocket, WebSocketDisconnect
from src.domains.interviews.state import active_sessions
from src.domains.interviews.analysis.video import analyze_frame
from src.domains.interviews.service import evaluate_candidate_frame
from src.shared.redis_client import redis_client
from src.shared.database import log_activity


async def interview_stream(websocket: WebSocket, candidate_id: str):
    await websocket.accept()
    active_sessions[candidate_id] = {}

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await redis_client.set(f"cv_threshold:start_time:{candidate_id}", now_str, ex=7200)

    try:
        while True:
            try:
                data = await websocket.receive_text()
                payload = json.loads(data)

                from src.domains.admin.state import admin_connections
                if payload.get("action") == "live_transcript":
                    transcript_payload = {
                        "action": "live_transcript",
                        "text": payload.get("text", ""),
                        "is_final": payload.get("is_final", False)
                    }
                    disconnected_admins = []
                    for admin_ws in admin_connections.get(candidate_id, []):
                        try:
                            await admin_ws.send_json(transcript_payload)
                        except Exception:
                            disconnected_admins.append(admin_ws)
                    for disconnected in disconnected_admins:
                        admin_connections[candidate_id].remove(disconnected)
                    continue

                if "image" not in payload:
                    continue

                try:
                    base64_data = payload["image"].split(",")[1]
                    image_bytes = base64.b64decode(base64_data)
                    np_array = np.frombuffer(image_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
                except Exception:
                    print(f"[WS DEBUG] Base64 decode failed for {candidate_id}")
                    continue

                if frame is None:
                    continue

                audio_level = payload.get("audio_level", 0.0)

                yaw_val = await redis_client.get(f"cv_threshold:yaw:{candidate_id}")
                pitch_val = await redis_client.get(f"cv_threshold:pitch:{candidate_id}")
                bright_val = await redis_client.get(f"cv_threshold:brightness:{candidate_id}")
                gaze_min_val = await redis_client.get(f"cv_threshold:gaze_min:{candidate_id}")
                gaze_max_val = await redis_client.get(f"cv_threshold:gaze_max:{candidate_id}")
                mic_gain_val = await redis_client.get(f"cv_threshold:mic_gain:{candidate_id}")
                noise_thresh_val = await redis_client.get(f"cv_threshold:noise_thresh:{candidate_id}")

                yaw_thresh = float(yaw_val) if yaw_val is not None else 20.0
                pitch_thresh = float(pitch_val) if pitch_val is not None else 20.0
                brightness_thresh = float(bright_val) if bright_val is not None else 90.0
                gaze_min = float(gaze_min_val) if gaze_min_val is not None else 0.025
                gaze_max = float(gaze_max_val) if gaze_max_val is not None else 0.055
                mic_gain = float(mic_gain_val) if mic_gain_val is not None else 1.0
                noise_thresh = float(noise_thresh_val) if noise_thresh_val is not None else 2.0

                is_violation, details, video_quality, annotated_frame = await asyncio.to_thread(
                    analyze_frame, frame, True, yaw_thresh, pitch_thresh, brightness_thresh, gaze_min, gaze_max
                )

                is_started = payload.get("is_started", True)

                response_data = await evaluate_candidate_frame(
                    candidate_id=candidate_id,
                    is_violation=is_violation,
                    details=details,
                    video_quality=video_quality,
                    is_started=is_started
                )

                response_data["mic_gain"] = mic_gain
                response_data["noise_thresh"] = noise_thresh

                if candidate_id in admin_connections and admin_connections[candidate_id]:
                    _, buffer = cv2.imencode('.jpg', annotated_frame)
                    b64_image = base64.b64encode(buffer).decode('utf-8')
                    admin_payload = {
                        "image": f"data:image/jpeg;base64,{b64_image}",
                        "details": details,
                        "video_quality": video_quality,
                        "is_violation": is_violation,
                        "current_strikes": response_data.get("current_strikes", 0),
                        "audio_level": audio_level
                    }
                    disconnected = []
                    for admin_ws in admin_connections[candidate_id]:
                        try:
                            await admin_ws.send_json(admin_payload)
                        except Exception:
                            disconnected.append(admin_ws)
                    for admin_ws in disconnected:
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
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await redis_client.set(f"cv_threshold:end_time:{candidate_id}", now_str, ex=7200)
        active_sessions.pop(candidate_id, None)
