import os
from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil

router = APIRouter(prefix="/admin", tags=["admin"])

VOICE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "voices")

@router.post("/voice/clone")
async def clone_voice(file: UploadFile = File(...)):
    """Accepts an audio file upload and saves it to be used as a reference for Coqui TTS XTTS-v2."""
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an audio file.")
        
    os.makedirs(VOICE_DIR, exist_ok=True)
    
    file_location = os.path.join(VOICE_DIR, "cloned_voice.wav")
    
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save audio file: {str(e)}")
        
    return {"status": "success", "message": "Voice cloned successfully.", "filename": file.filename}
