

add an AI interviewer agent that dynamically asks questions based on a list of required topics, speaks to the candidate, and reacts to their answers in real-time, you need a Conversational AI pipeline combined with Text-to-Speech (TTS). Tools to Combine with FastAPITo build a real-time conversational agent, integrate these tools into your existing FastAPI application:LLM Engine: It has exceptional conversational flow, strictly adheres to interview criteria, and handles structured JSON tool outputs seamlessly.Text-to-Speech (Audio Output): Kokoro-82M TTS Engine . These provide low-latency, human-like voice synthesis. You can stream the raw audio bytes directly through your FastAPI WebSocket to the frontend.Speech-to-Text (Candidate Audio Input): Deepgram Nova-2 or OpenAI Whisper Live. This tool converts the candidate's spoken answers into text in real time so Claude can read and evaluate them.2. Live Agent System Architecturemermaidgraph LR
    A[Candidate Speaks] -->|Audio via WebSocket| B(Deepgram Live STT)
    B -->|Transcribed Text| C(FastAPI Orchestrator)
    C -->|Text + History + Topics| D(Claude API)
    D -->|Next Question Text| E(Kokoro-82M TTS Engine)
    E -->|Audio Stream Bytes| F[Candidate Hears & Sees Text]
Use code with caution.

3. How to Design the Prompt for AI Interview Agent  

The prompt must instruct Agent to act as a professional recruiter. It must enforce three strict rules:Cover every topic on the checklist.Adapt dynamically to what the candidate says (no rigid reading off a script).Output JSON format only so FastAPI can separate the spoken text from the backend tracking metrics.The Recommended System Prompt for Agent:textYou are an expert AI Job Interviewer. Your objective is to conduct a professional, friendly, and rigorous interview. 

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
}
Use code with caution.