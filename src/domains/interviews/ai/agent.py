import json
from typing import Dict, List, Tuple

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool

from src.config.settings import settings

_sessions: Dict[str, List[Tuple[str, str]]] = {}
_injected_questions_queue: Dict[str, List[str]] = {}


def queue_injected_question(candidate_id: str, question: str) -> None:
    _injected_questions_queue.setdefault(candidate_id, []).append(question)


def get_dynamic_prompt(objective: str = None, topics: str = None, num_questions: int = None) -> str:
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
    """Fetch the active interview rules defined by the manager."""
    return (
        "- Max Accepted Yaw (head pose left/right): 20 degrees\n"
        "- Max Accepted Pitch (head pose up/down): 20 degrees\n"
        "- Gaze sensitivity limits: 0.025 to 0.055"
    )


async def transcribe_audio(audio_bytes: bytes) -> str:
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
    def __init__(self):
        self.llm = ChatGroq(
            groq_api_key=settings.groq_api_key,
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        ) if settings.groq_api_key else None

    async def get_response(self, candidate_id: str, candidate_text: str) -> dict:
        if not self.llm:
            return {"text_to_speak": "Mock LLM response: Please set GROQ_API_KEY.", "current_topic": "Configuration", "topics_completed": [], "interview_complete": False}

        from src.shared.postgres_db import get_postgres_config
        config = await get_postgres_config(candidate_id)
        base_limit = config.question_time_limit_seconds if config else 60

        if candidate_id not in _sessions:
            if config:
                raw_prompt = get_dynamic_prompt(objective=config.interview_objective, topics=config.interview_topics, num_questions=config.num_questions)
            else:
                raw_prompt = get_dynamic_prompt()
            _sessions[candidate_id] = [("system", raw_prompt)]

        if candidate_text:
            _sessions[candidate_id].append(("user", candidate_text))

        if _injected_questions_queue.get(candidate_id):
            injected_q = _injected_questions_queue[candidate_id].pop(0)
            _sessions[candidate_id].append(("system", f"CRITICAL: The admin has injected a custom question: '{injected_q}'. Ask this question now. Set 'interview_complete': false."))

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
            limit = 90 if inp_type == "text" else (45 if inp_type in ("multiple_choice", "checkbox") else base_limit)
            if len(result.get("text_to_speak", "")) > 100:
                limit += 15
            result["question_time_limit"] = limit
            return result
        except Exception as e:
            print(f"Agent error: {e}")
            return {"text_to_speak": f"I'm sorry, I'm having trouble processing that. Error: {str(e)}", "current_topic": "Error", "topics_completed": [], "interview_complete": False}


async def generate_agent_response(candidate_id: str, candidate_text: str) -> dict:
    return await InterviewAgent().get_response(candidate_id, candidate_text)


async def generate_compliance_analysis(candidate_id: str, violations_summary: dict) -> str:
    from src.domains.interviews.ai.compliance_agent import ComplianceAnalystAgent
    return await ComplianceAnalystAgent().analyze(candidate_id, violations_summary)
