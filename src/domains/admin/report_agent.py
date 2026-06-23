import json
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from src.config.settings import settings
from src.domains.interviews.ai.agent import _sessions, get_compliance_rules
from src.shared.redis_client import redis_client

class ReportAgent:
    def __init__(self):
        self.llm = ChatGroq(
            groq_api_key=settings.groq_api_key,
            model="llama-3.1-8b-instant"
        ) if settings.groq_api_key else None

    async def generate_report(self, candidate_id: str) -> str:
        if not self.llm:
            return "GROQ API key is not configured. Unable to generate report."

        # Fetch transcript
        from src.shared.database import get_interview_session
        transcript = _sessions.get(candidate_id, [])
        if not transcript:
            transcript = await get_interview_session(candidate_id)

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

        # Fetch violations
        from src.shared.database import get_violation_events
        raw_events = await get_violation_events(candidate_id)
        
        # Fetch times
        try:
            start_val = await redis_client.get(f"cv_threshold:start_time:{candidate_id}")
            start_time = start_val.decode() if isinstance(start_val, bytes) else start_val
        except Exception:
            start_time = "N/A"
            
        try:
            end_val = await redis_client.get(f"cv_threshold:end_time:{candidate_id}")
            end_time = end_val.decode() if isinstance(end_val, bytes) else end_val
        except Exception:
            end_time = "N/A"

        # Fetch rules
        from src.shared.postgres_db import get_postgres_config
        config = await get_postgres_config(candidate_id)
        if config:
            rules = (
                f"- Interview Duration: {config.interview_duration_minutes} minutes\n"
                f"- Max Questions: {config.num_questions}\n"
                f"- Speech Language: {config.speech_language}\n"
                f"- Text/Question Language: {config.text_language}"
            )
        else:
            rules = "Standard settings applied."

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a Specialist Analyst Agent generating an official interview report."),
            ("user", """Generate a formal interview report based on the following data:
Candidate ID: {candidate_id}
Start Time: {start_time}
End Time: {end_time}
Total CV/Camera Violations: {total_violations}

Manager Rules:
{rules}

Transcript:
{transcript}

Provide a clear, detailed, and professional analysis covering:
1. Candidate CV & Compliance Results (based on violations and rules).
2. Time and Session Management.
3. Quality of Answers vs Questions.
4. Final Manager Recommendation.

CRITICAL REQUIREMENT: Do NOT use markdown headers or formatting like '##' or '**' or '*'. Use pure plain text with capitalized headers (e.g., '1. COMPLIANCE RESULTS') and standard text formatting. The output will be directly printed on a PDF.""")
        ])

        try:
            chain = prompt_template | self.llm
            response = await chain.ainvoke({
                "candidate_id": candidate_id,
                "total_violations": len(raw_events),
                "start_time": start_time,
                "end_time": end_time,
                "rules": rules,
                "transcript": transcript_text
            })
            return response.content.replace("**", "").replace("##", "").replace("#", "").replace("*", "")
        except Exception as e:
            return f"Report generation failed: {e}"
