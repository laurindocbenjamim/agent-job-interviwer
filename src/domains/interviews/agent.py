import json
import os
import asyncio
from typing import Dict, List, Tuple
from groq import AsyncGroq
from src.config.settings import settings

# In-memory session store for interview states.
# For production, move this to Redis.
_sessions: Dict[str, List[Dict[str, str]]] = {}
_injected_questions_queue: Dict[str, List[str]] = {}

def queue_injected_question(candidate_id: str, question: str) -> None:
    """Queues a custom question from the admin for a candidate."""
    if candidate_id not in _injected_questions_queue:
        _injected_questions_queue[candidate_id] = []
    _injected_questions_queue[candidate_id].append(question)

def get_dynamic_prompt() -> str:
    topics_list = [t.strip() for t in settings.interview_topics.split(",")]
    topics_str = "\n".join([f"{i+1}. {topic}" for i, topic in enumerate(topics_list)])
    
    return f"""You are an expert AI Job Interviewer. Your objective is to {settings.interview_objective}.

You must evaluate the candidate on the following REQUIRED TOPICS:
{topics_str}

CRITICAL INSTRUCTIONS:
- Be conversational. Acknowledge their previous answer naturally before moving on or asking a follow-up question.
- Ask exactly ONE question at a time.
- You can ask different types of questions. Set `input_type` to one of: "voice" (for spoken answers), "text" (for written answers), "multiple_choice" (for radio buttons), or "checkbox" (for multi-select).
- If `input_type` is "multiple_choice" or "checkbox", you MUST provide an array of strings in the `options` field. Otherwise, leave it empty.
- You must end the interview after exactly {settings.num_questions} questions have been asked in total.
- Keep track of which topics have been fully covered. Once {settings.num_questions} questions are asked or all topics are completed, politely wrap up the interview and set "interview_complete": true.

OUTPUT FORMAT:
You must ALWAYS respond in a strict JSON format. Do not include any conversational text outside the JSON block. Use the following schema:

{{
  "text_to_speak": "The exact question or response the candidate will hear and read on screen.",
  "current_topic": "The topic currently being evaluated",
  "input_type": "voice",
  "options": [],
  "topics_completed": ["List", "of", "completed", "topics"],
  "interview_complete": false
}}"""

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
            {"role": "system", "content": get_dynamic_prompt()}
        ]
        
    if candidate_text:
        _sessions[candidate_id].append({"role": "user", "content": candidate_text})
        
    # Check for queued questions and inject them
    if _injected_questions_queue.get(candidate_id):
        injected_q = _injected_questions_queue[candidate_id].pop(0)
        _sessions[candidate_id].append({
            "role": "system",
            "content": f"CRITICAL: The admin has injected a custom question: '{injected_q}'. You must analyze the candidate's previous responses and ask this question to the candidate now. Do not end the interview yet; set 'interview_complete': false in your response."
        })
        
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

async def generate_compliance_analysis(candidate_id: str, violations_summary: dict) -> str:
    """Uses Groq to analyze the interview timeline, answers, and compliance log."""
    transcript = _sessions.get(candidate_id, [])
    transcript_text = ""
    for msg in transcript:
        if msg["role"] == "user":
            transcript_text += f"Candidate Answer: {msg['content']}\n"
        elif msg["role"] == "assistant":
            try:
                content_dict = json.loads(msg["content"])
                transcript_text += f"Agent Question: {content_dict.get('text_to_speak', '')}\n"
            except Exception:
                transcript_text += f"Agent Question: {msg['content']}\n"

    prompt = f"""You are a Specialist compliance analyst agent.
Analyze the following interview data:
Candidate ID: {candidate_id}
Total Violations: {violations_summary.get('total_violations', 0)}
Total Strikes: {violations_summary.get('total_strikes', 0)}
Start Time: {violations_summary.get('start_time', 'N/A')}
End Time: {violations_summary.get('end_time', 'N/A')}

Rules Defined by Manager:
- Max Accepted Yaw (head pose left/right): 20 degrees
- Max Accepted Pitch (head pose up/down): 20 degrees
- Gaze sensitivity limits: 0.025 to 0.055

Transcript:
{transcript_text}

Provide a clear, detailed, and professional analysis explaining:
1. Candidate compliance behaviors, listing specific violation patterns if any.
2. An evaluation of candidate's answers in relation to the questions asked.
3. Final recommendation regarding compliance/integrity.

CRITICAL: Do NOT use markdown headers or formatting like '##' or '**'. Instead, use CAPITALIZED plain text headers and clear spacing.
"""
    if not settings.groq_api_key:
        return "GROQ API key is not configured. Compliance analysis unavailable. Mock Analysis: Candidate showed general compliance throughout the interview."

    client = AsyncGroq(api_key=settings.groq_api_key)
    try:
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant"
        )
        # Clean up any remaining markdown characters just in case
        cleaned_content = response.choices[0].message.content.replace("**", "").replace("##", "").replace("#", "")
        return cleaned_content
    except Exception as e:
        return f"Analysis generation failed: {e}"
