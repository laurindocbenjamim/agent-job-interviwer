import json
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from src.config.settings import settings
from src.domains.interviews.ai.agent import _sessions, get_compliance_rules


class ComplianceAnalystAgent:
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
                f"- Max Accepted Yaw: 20 degrees\n"
                f"- Max Accepted Pitch: 20 degrees\n"
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
