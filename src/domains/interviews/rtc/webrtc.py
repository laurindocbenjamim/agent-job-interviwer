import av
import asyncio
import numpy as np
from aiortc import VideoStreamTrack, AudioStreamTrack
from src.domains.interviews.analysis.video import analyze_frame
from src.domains.interviews.service import evaluate_candidate_frame
from src.domains.interviews.ai.agent import transcribe_audio, generate_agent_response
from src.domains.interviews.ai.tts import generate_speech


class TTSAudioStreamTrack(AudioStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self._timestamp = 0
        self._start = None

    async def add_audio(self, pcm_bytes: bytes):
        audio_data = np.frombuffer(pcm_bytes, dtype=np.int16)
        frame = av.AudioFrame(format='s16', layout='mono', samples=len(audio_data))
        frame.sample_rate = 24000
        frame.planes[0].update(audio_data.tobytes())
        await self.queue.put(frame)

    def clear_queue(self):
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def recv(self):
        try:
            frame = await asyncio.wait_for(self.queue.get(), timeout=0.02)
        except asyncio.TimeoutError:
            frame = av.AudioFrame(format='s16', layout='mono', samples=480)
            frame.sample_rate = 24000
            frame.planes[0].update(b'\x00' * 960)
        pts, time_base = await self.next_timestamp()
        frame.pts = pts
        frame.time_base = time_base
        return frame


class InterviewAudioStreamTrack(AudioStreamTrack):
    kind = "audio"

    def __init__(self, track, candidate_id: str, tts_track: TTSAudioStreamTrack, channel_ref: dict):
        super().__init__()
        self.track = track
        self.candidate_id = candidate_id
        self.tts_track = tts_track
        self.channel_ref = channel_ref
        self.audio_buffer = bytearray()
        self.is_processing = False
        self.frame_count = 0
        self.is_interview_started = False

    async def process_speech(self):
        self.is_processing = True
        audio_data = bytes(self.audio_buffer)
        self.audio_buffer.clear()

        if not self.is_interview_started:
            self.is_processing = False
            return

        text = await transcribe_audio(audio_data)
        if text.strip():
            import json
            from src.domains.admin.state import admin_connections
            if self.candidate_id in admin_connections:
                payload = json.dumps({"candidate_text": text})
                for admin_ws in admin_connections[self.candidate_id]:
                    try:
                        asyncio.create_task(admin_ws.send_text(payload))
                    except Exception:
                        pass

            response = await generate_agent_response(self.candidate_id, text)
            text_to_speak = response.get("text_to_speak", "")
            current_topic = response.get("current_topic", "")

            if text_to_speak:
                if self.candidate_id in admin_connections:
                    payload = json.dumps({"agent_text": text_to_speak, "current_topic": current_topic})
                    for admin_ws in admin_connections[self.candidate_id]:
                        try:
                            asyncio.create_task(admin_ws.send_text(payload))
                        except Exception:
                            pass

            channel = self.channel_ref.get("channel")
            if channel and channel.readyState == "open":
                try:
                    channel.send(json.dumps(response))
                except Exception as e:
                    print(f"Error sending datachannel message: {e}")

            if text_to_speak:
                pcm_bytes = await generate_speech(text_to_speak)
                await self.tts_track.add_audio(pcm_bytes)

        self.is_processing = False

    async def recv(self):
        frame = await self.track.recv()
        self.frame_count += 1
        if self.frame_count % 5 == 0:
            audio_bytes = frame.planes[0].to_bytes()
            if audio_bytes:
                audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                if len(audio_array) > 0:
                    rms = float(np.sqrt(np.mean(audio_array.astype(np.float32)**2)))
                    import json
                    from src.domains.admin.state import admin_connections
                    payload = json.dumps({"audio_level": rms})
                    if self.candidate_id in admin_connections:
                        for admin_ws in admin_connections[self.candidate_id]:
                            try:
                                asyncio.create_task(admin_ws.send_text(payload))
                            except Exception:
                                pass

        if not self.is_processing:
            self.audio_buffer.extend(frame.planes[0].to_bytes())
            if len(self.audio_buffer) > 48000 * 5:
                asyncio.create_task(self.process_speech())

        return frame


class InterviewVideoStreamTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, track, candidate_id: str):
        super().__init__()
        self.track = track
        self.candidate_id = candidate_id
        self.frame_count = 0
        self.analyze_every_n_frames = 15

    async def recv(self):
        frame = await self.track.recv()
        self.frame_count += 1

        if self.frame_count % self.analyze_every_n_frames == 0:
            img = frame.to_ndarray(format="bgr24")
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

            import json, cv2, base64
            from src.domains.admin.state import admin_connections

            _, buffer = cv2.imencode('.jpg', annotated_frame)
            b64_image = base64.b64encode(buffer).decode('utf-8')
            payload = json.dumps({"image": f"data:image/jpeg;base64,{b64_image}", "details": details, "video_quality": video_quality, "is_violation": is_violation})

            if self.candidate_id in admin_connections:
                for admin_ws in admin_connections[self.candidate_id]:
                    try:
                        asyncio.create_task(admin_ws.send_text(payload))
                    except Exception:
                        pass

            await evaluate_candidate_frame(candidate_id=self.candidate_id, is_violation=is_violation, details=details, video_quality=video_quality)

        return frame
