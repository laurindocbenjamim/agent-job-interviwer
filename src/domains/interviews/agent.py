import json
import os
import asyncio
from typing import Dict, List, Tuple
from groq import AsyncGroq
from src.config.settings import settings

# In-memory session store for interview states.
# For production, move this to Redis.
_sessions: Dict[str, List[Dict[str, str]]] = {}

PROMPT = """You are an expert AI Job Interviewer. Your objective is to conduct a professional, friendly, and rigorous interview. 

You must evaluate the candidate on the following REQUIRED TOPICS:
1. Experience with FastAPI and Async Python.
2. System design concepts (Caching with Redis, Databases with MongoDB).
3. Handling real-time streaming data pipelines.

CRITICAL INSTRUCTIONS:
- Be conversational. Do not just jump from topic to topic. Acknowledge their previous answer naturally before moving on or asking a follow-up question.
- Ask only ONE question at a time. Keep questions concise and optimized for spoken audio.
- Never step out of character. Do not give feedback like "Great answer!" unless a real human recruiter would say it.
- Track which topics have been fully covered. Once all topics are completed, politely wrap up the interview.

OUTPUT FORMAT:
You must ALWAYS respond in a strict JSON format. Do not include any conversational text outside the JSON block. Use the following schema:

{
  "text_to_speak": "The exact question or response the candidate will hear and read on screen.",
  "current_topic": "The topic currently being evaluated (e.g., 'FastAPI and Async Python')",
  "topics_completed": ["List", "of", "completed", "topics"],
  "interview_complete": false
}"""

async def transcribe_audio(audio_bytes: bytes) -> str:
    """Uses Groq Whisper to transcribe PCM audio bytes."""
    if not settings.groq_api_key:
        print("Warning: GROQ_API_KEY not set. Returning mock transcription.")
        return "This is a mock transcription of what I just said."
        
    client = AsyncGroq(api_key=settings.groq_api_key)
    
    # Write bytes to a temporary wav file for Groq API
    # Groq whisper requires file-like objects with a valid extension
    # We assume the incoming bytes are a valid wav file for this function
    # In reality, we'll construct the WAV header in webrtc.py before calling this.
    try:
        response = await client.audio.transcriptions.create(
            file=("candidate.wav", audio_bytes),
            model="whisper-large-v3",
            response_format="text"
        )
        return response
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""

async def generate_agent_response(candidate_id: str, candidate_text: str) -> dict:
    """Calls Groq LLaMA to generate the next response based on history."""
    if not settings.groq_api_key:
        return {
            "text_to_speak": "Mock LLM response: Please set GROQ_API_KEY.",
            "current_topic": "Configuration",
            "topics_completed": [],
            "interview_complete": False
        }
        
    if candidate_id not in _sessions:
        _sessions[candidate_id] = [
            {"role": "system", "content": PROMPT}
        ]
        
    if candidate_text:
        _sessions[candidate_id].append({"role": "user", "content": candidate_text})
        
    client = AsyncGroq(api_key=settings.groq_api_key)
    
    try:
        response = await client.chat.completions.create(
            messages=_sessions[candidate_id],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        
        reply_json = response.choices[0].message.content
        _sessions[candidate_id].append({"role": "assistant", "content": reply_json})
        
        return json.loads(reply_json)
    except Exception as e:
        print(f"Agent error: {e}")
        return {
            "text_to_speak": "I'm sorry, I'm having trouble processing that.",
            "current_topic": "Error",
            "topics_completed": [],
            "interview_complete": False
        }
