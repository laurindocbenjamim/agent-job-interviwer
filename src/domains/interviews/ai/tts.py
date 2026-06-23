import os
import io
import wave
import asyncio
import numpy as np

# Lazy load TTS to avoid slow startup and handle missing dependencies gracefully
_tts_model = None
_tts_loaded = False
_mock_mode = False

def get_tts_model():
    global _tts_model, _tts_loaded, _mock_mode
    if _tts_loaded:
        return _tts_model
        
    try:
        from TTS.api import TTS
        # Load XTTS-v2 for voice cloning
        print("Loading Coqui TTS XTTS-v2 model... This may take a while.")
        _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        # Move to MPS or CPU depending on availability
        import torch
        if torch.backends.mps.is_available():
            _tts_model.to("mps")
        print("Coqui TTS loaded successfully.")
    except Exception as e:
        print(f"Failed to load Coqui TTS, falling back to mock mode: {e}")
        _mock_mode = True
        
    _tts_loaded = True
    return _tts_model

async def generate_speech(text: str) -> bytes:
    """
    Generates PCM audio bytes from text using the cloned voice.
    Returns 16-bit PCM audio, 24000 Hz, Mono.
    """
    voice_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "voices")
    speaker_wav = os.path.join(voice_dir, "cloned_voice.wav")
    
    # Check if we have a cloned voice, otherwise use a default (or fail in mock mode)
    if not os.path.exists(speaker_wav):
        print("No cloned voice found. Generating mock audio.")
        _mock_mode_local = True
    else:
        _mock_mode_local = False
        
    model = get_tts_model()
    
    if _mock_mode or _mock_mode_local:
        # Generate 1 second of silence as mock PCM bytes
        # 24000 Hz * 2 bytes (16-bit) = 48000 bytes per second
        return b'\x00' * 48000
        
    # Run TTS generation in a thread since it's blocking
    try:
        # output is a list of floats or numpy array
        wav_array = await asyncio.to_thread(
            model.tts, 
            text=text, 
            speaker_wav=speaker_wav, 
            language="en"
        )
        
        # Convert the float array (-1.0 to 1.0) to 16-bit PCM
        audio_np = np.array(wav_array)
        audio_int16 = (audio_np * 32767).astype(np.int16)
        
        # We return the raw PCM bytes (mono, 24000Hz typically for XTTS)
        return audio_int16.tobytes()
        
    except Exception as e:
        print(f"TTS generation error: {e}")
        return b'\x00' * 48000
