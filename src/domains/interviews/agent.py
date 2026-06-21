import json
import os
import asyncio
from typing import Dict, List, Tuple
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from src.config.settings import settings

# Bounded context session state
_sessions: Dict[str, List[Tuple[str, str]]] = {}
_injected_questions_queue: Dict[str, List[str]] = {}

def queue_injected_question(candidate_id: str, question: str) -> None:
    """Queues a custom question from the admin for a candidate."""
    _injected_questions_queue.setdefault(candidate_id, []).append(question)

def get_dynamic_prompt(objective: str = None, topics: str = None, num_questions: int = None) -> str:
    """Generates the dynamic prompt string based on settings."""
    obj = objective or settings.interview_objective
    tops = topics or settings.interview_topics
    num_q = num_questions if num_questions is not None else settings.num_questions
    topics_list = [t.strip() for t in tops.split(",")]
    topics_str = "\n".join([f"{i+1}. {topic}" for i, topic in enumerate(topics_list)])
    return f"""You are an expert AI Job Interviewer. Your objective is to {obj}.

Evaluate the candidate on the following REQUIRED TOPICS:
{topics_str}

CRITICAL INSTRUCTIONS:
- Be conversational. Acknowledge their previous answer naturally before moving on.
- Ask exactly ONE question at a time.
- Set `input_type` to one of: "voice", "text", "multiple_choice", or "checkbox".
- If `input_type` is "multiple_choice" or "checkbox", provide options in the `options` array.
- You must end the interview after exactly {num_q} questions.
- Once {num_q} questions are asked, wrap up and set "interview_complete": true.

OUTPUT FORMAT (strict JSON block):
{{
  "text_to_speak": "Question or response the candidate will hear/read.",
  "current_topic": "The topic currently being evaluated",
  "input_type": "voice",
  "options": [],
  "topics_completed": ["List", "of", "completed", "topics"],
  "interview_complete": false
}}"""

@tool
def get_compliance_rules() -> str:
    """Skill to fetch the active interview rules defined by the manager."""
    return (
        "- Max Accepted Yaw (head pose left/right): 20 degrees\n"
        "- Max Accepted Pitch (head pose up/down): 20 degrees\n"
        "- Gaze sensitivity limits: 0.025 to 0.055"
    )

async def transcribe_audio(audio_bytes: bytes) -> str:
    """Uses Groq client to transcribe audio bytes."""
    from groq import AsyncGroq
    if not settings.groq_api_key:
        return "Mock transcription: Please configure GROQ_API_KEY."
    client = AsyncGroq(api_key=settings.groq_api_key)
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

class InterviewAgent:
    """Agent orchestrator for handling active interview responses."""
    def __init__(self):
        self.llm = ChatGroq(
            groq_api_key=settings.groq_api_key,
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        ) if settings.groq_api_key else None

    async def get_response(self, candidate_id: str, candidate_text: str) -> dict:
        if not self.llm:
            return {
                "text_to_speak": "Mock LLM response: Please set GROQ_API_KEY.",
                "current_topic": "Configuration",
                "topics_completed": [],
                "interview_complete": False
            }
        
        from src.shared.postgres_db import get_postgres_config
        config = await get_postgres_config(candidate_id)
        base_limit = config.question_time_limit_seconds if config else 60

        if candidate_id not in _sessions:
            if config:
                raw_prompt = get_dynamic_prompt(
                    objective=config.interview_objective,
                    topics=config.interview_topics,
                    num_questions=config.num_questions
                )
            else:
                raw_prompt = get_dynamic_prompt()
            _sessions[candidate_id] = [("system", raw_prompt)]
            
        if candidate_text:
            _sessions[candidate_id].append(("user", candidate_text))
            
        if _injected_questions_queue.get(candidate_id):
            injected_q = _injected_questions_queue[candidate_id].pop(0)
            msg = f"CRITICAL: The admin has injected a custom question: '{injected_q}'. Ask this question now. Set 'interview_complete': false."
            _sessions[candidate_id].append(("system", msg))
            
        try:
            messages = []
            for role, content in _sessions[candidate_id]:
                if role == "system":
                    messages.append(SystemMessage(content=content))
                elif role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
            
            response = await self.llm.ainvoke(messages)
            reply_json = response.content
            _sessions[candidate_id].append(("assistant", reply_json))
            
            result = json.loads(reply_json)
            inp_type = result.get("input_type", "voice")
            text_to_speak = result.get("text_to_speak", "")
            
            limit = 90 if inp_type == "text" else (45 if inp_type in ("multiple_choice", "checkbox") else base_limit)
            if len(text_to_speak) > 100:
                limit += 15

            result["question_time_limit"] = limit
            return result
        except Exception as e:
            print(f"Agent error: {e}")
            return {
                "text_to_speak": f"I'm sorry, I'm having trouble processing that. Error: {str(e)}",
                "current_topic": "Error",
                "topics_completed": [],
                "interview_complete": False
            }

class ComplianceAnalystAgent:
    """Agent orchestrator for compiling compliance review recommendations."""
    def __init__(self):
        self.llm = ChatGroq(
            groq_api_key=settings.groq_api_key,
            model="llama-3.1-8b-instant"
        ) if settings.groq_api_key else None

    async def analyze(self, candidate_id: str, violations_summary: dict) -> str:
        if not self.llm:
            return "GROQ API key is not configured. Mock: Candidate showed general compliance."
            
        transcript = _sessions.get(candidate_id, [])
        transcript_text = ""
        for role, content in transcript:
            if role == "user":
                transcript_text += f"Candidate Answer: {content}\n"
            elif role == "assistant":
                try:
                    content_dict = json.loads(content)
                    transcript_text += f"Agent Question: {content_dict.get('text_to_speak', '')}\n"
                except Exception:
                    transcript_text += f"Agent Question: {content}\n"

        from src.shared.postgres_db import get_postgres_config
        config = await get_postgres_config(candidate_id)
        if config:
            rules = (
                f"- Interview Duration: {config.interview_duration_minutes} minutes\n"
                f"- Max Questions: {config.num_questions}\n"
                f"- Speech Language: {config.speech_language}\n"
                f"- Text/Question Language: {config.text_language}\n"
                f"- Max Accepted Yaw (head pose left/right): 20 degrees\n"
                f"- Max Accepted Pitch (head pose up/down): 20 degrees\n"
                f"- Gaze sensitivity limits: 0.025 to 0.055"
            )
        else:
            rules = get_compliance_rules.invoke({})

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a Specialist compliance analyst agent. Analyze compliance rules and logs."),
            ("user", """Analyze the following interview data:
Candidate ID: {candidate_id}
Total Violations: {total_violations}
Total Strikes: {total_strikes}
Start Time: {start_time}
End Time: {end_time}

Rules Defined by Manager:
{rules}

Transcript:
{transcript}

Provide a clear, detailed, and professional analysis explaining:
1. Candidate compliance behaviors.
2. Evaluation of answers in relation to questions.
3. Final integrity recommendation.

CRITICAL: Do NOT use markdown headers or formatting like '##' or '**'. Use CAPITALIZED plain text headers.""")
        ])
        
        try:
            chain = prompt_template | self.llm
            response = await chain.ainvoke({
                "candidate_id": candidate_id,
                "total_violations": violations_summary.get('total_violations', 0),
                "total_strikes": violations_summary.get('total_strikes', 0),
                "start_time": violations_summary.get('start_time', 'N/A'),
                "end_time": violations_summary.get('end_time', 'N/A'),
                "rules": rules,
                "transcript": transcript_text
            })
            return response.content.replace("**", "").replace("##", "").replace("#", "")
        except Exception as e:
            return f"Analysis generation failed: {e}"

async def generate_agent_response(candidate_id: str, candidate_text: str) -> dict:
    return await InterviewAgent().get_response(candidate_id, candidate_text)

async def generate_compliance_analysis(candidate_id: str, violations_summary: dict) -> str:
    return await ComplianceAnalystAgent().analyze(candidate_id, violations_summary)
