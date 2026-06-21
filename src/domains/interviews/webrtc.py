import av
import asyncio
import numpy as np
from aiortc import VideoStreamTrack, AudioStreamTrack
from src.domains.interviews.video_analyzer import analyze_frame
from src.domains.interviews.service import evaluate_candidate_frame
from src.domains.interviews.agent import transcribe_audio, generate_agent_response
from src.domains.interviews.tts import generate_speech

class TTSAudioStreamTrack(AudioStreamTrack):
    """
    An AudioStreamTrack that plays synthesized audio from the TTS engine.
    """
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self._timestamp = 0
        self._start = None

    async def add_audio(self, pcm_bytes: bytes):
        """Enqueue raw PCM bytes to be sent to the candidate."""
        # Convert bytes to numpy array (16-bit, mono)
        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16)
        # Create PyAV audio frame
        # PyAV typically expects a specific layout, e.g., s16, 24000Hz.
        frame = av.AudioFrame(format='s16', layout='mono', samples=len(audio_data))
        frame.sample_rate = 24000
        frame.planes[0].update(audio_data.tobytes())
        await self.queue.put(frame)

    async def recv(self):
        # We must return frames continuously or the WebRTC connection drops.
        # If queue is empty, return silence.
        try:
            # wait a short bit
            frame = await asyncio.wait_for(self.queue.get(), timeout=0.02)
        except asyncio.TimeoutError:
            # Return silence
            frame = av.AudioFrame(format='s16', layout='mono', samples=480) # 20ms at 24000Hz
            frame.sample_rate = 24000
            frame.planes[0].update(b'\x00' * 960)
            
        pts, time_base = await self.next_timestamp()
        frame.pts = pts
        frame.time_base = time_base
        return frame

class InterviewAudioStreamTrack(AudioStreamTrack):
    """
    Receives audio from candidate, sends to STT and triggers LLM/TTS.
    """
    kind = "audio"

    def __init__(self, track, candidate_id: str, tts_track: TTSAudioStreamTrack, channel_ref: dict):
        super().__init__()
        self.track = track
        self.candidate_id = candidate_id
        self.tts_track = tts_track
        self.channel_ref = channel_ref
        self.audio_buffer = bytearray()
        self.is_processing = False
        
    async def process_speech(self):
        """Process buffered speech when enough has accumulated."""
        self.is_processing = True
        audio_data = bytes(self.audio_buffer)
        self.audio_buffer.clear()
        
        # 1. Transcribe audio
        text = await transcribe_audio(audio_data)
        if text.strip():
            # 2. Get LLM response
            response = await generate_agent_response(self.candidate_id, text)
            text_to_speak = response.get("text_to_speak", "")
            
            # Send text over data channel
            channel = self.channel_ref.get("channel")
            if channel and channel.readyState == "open":
                import json
                try:
                    channel.send(json.dumps(response))
                except Exception as e:
                    print(f"Error sending datachannel message: {e}")
            
            # 3. Generate TTS
            if text_to_speak:
                pcm_bytes = await generate_speech(text_to_speak)
                # 4. Push to TTS track
                await self.tts_track.add_audio(pcm_bytes)
                
        self.is_processing = False

    async def recv(self):
        frame = await self.track.recv()
        # Collect audio
        if not self.is_processing:
            # We extract raw bytes. This is simplified, real implementations 
            # should handle VAD (Voice Activity Detection).
            self.audio_buffer.extend(frame.planes[0].to_bytes())
            
            # If buffer gets large enough (e.g. roughly 5 seconds), trigger process
            if len(self.audio_buffer) > 48000 * 5: # Assuming 48kHz, 5 seconds
                asyncio.create_task(self.process_speech())
                
        return frame

class InterviewVideoStreamTrack(VideoStreamTrack):
    """
    A WebRTC VideoStreamTrack subclass that intercepts frames from the client,
    runs the MediaPipe video_analyzer, and logs violations.
    """
    kind = "video"

    def __init__(self, track, candidate_id: str):
        super().__init__()
        self.track = track
        self.candidate_id = candidate_id
        # We don't want to analyze 30fps. Analyze every N frames to save CPU.
        self.frame_count = 0
        self.analyze_every_n_frames = 15  # roughly twice a second at 30fps

    async def recv(self):
        # Receive frame from the client's webcam
        frame = await self.track.recv()
        
        self.frame_count += 1
        
        if self.frame_count % self.analyze_every_n_frames == 0:
            # Convert av.VideoFrame to numpy array (BGR for OpenCV/MediaPipe)
            img = frame.to_ndarray(format="bgr24")
            
            # analyze_frame is CPU bound, run in thread
            from src.shared.redis_client import redis_client
            yaw_val = await redis_client.get(f"cv_threshold:yaw:{self.candidate_id}")
            pitch_val = await redis_client.get(f"cv_threshold:pitch:{self.candidate_id}")
            bright_val = await redis_client.get(f"cv_threshold:brightness:{self.candidate_id}")
            gaze_min_val = await redis_client.get(f"cv_threshold:gaze_min:{self.candidate_id}")
            gaze_max_val = await redis_client.get(f"cv_threshold:gaze_max:{self.candidate_id}")

            yaw_thresh = float(yaw_val) if yaw_val is not None else 20.0
            pitch_thresh = float(pitch_val) if pitch_val is not None else 20.0
            brightness_thresh = float(bright_val) if bright_val is not None else 90.0
            gaze_min = float(gaze_min_val) if gaze_min_val is not None else 0.025
            gaze_max = float(gaze_max_val) if gaze_max_val is not None else 0.055

            is_violation, details, video_quality, annotated_frame = await asyncio.to_thread(
                analyze_frame, img, True, yaw_thresh, pitch_thresh, brightness_thresh, gaze_min, gaze_max
            )
            
            # Broadcast to admins if any are connected
            from src.domains.admin.router import admin_connections
            import cv2
            import base64
            
            if self.candidate_id in admin_connections and admin_connections[self.candidate_id]:
                # encode frame to jpeg
                _, buffer = cv2.imencode('.jpg', annotated_frame)
                b64_image = base64.b64encode(buffer).decode('utf-8')
                
                payload = {
                    "image": f"data:image/jpeg;base64,{b64_image}",
                    "details": details,
                    "video_quality": video_quality,
                    "is_violation": is_violation
                }
                
                disconnected_admins = []
                for ws in admin_connections[self.candidate_id]:
                    try:
                        # Send without awaiting if possible or use a safe method, 
                        # but sending json over websocket is async so we await
                        await ws.send_json(payload)
                    except Exception as e:
                        disconnected_admins.append(ws)
                for ws in disconnected_admins:
                    admin_connections[self.candidate_id].remove(ws)
            
            # Evaluate the frame (logs telemetry and checks strike count)
            # This triggers MongoDB writes and Redis updates asynchronously.
            # In a full implementation, we might send "warn" or "terminate" 
            # signals back to the client via WebRTC DataChannel.
            await evaluate_candidate_frame(
                candidate_id=self.candidate_id,
                is_violation=is_violation,
                details=details,
                video_quality=video_quality
            )
        
        return frame
