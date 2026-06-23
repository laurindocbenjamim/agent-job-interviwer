from typing import Optional
from pydantic import BaseModel, Field


class CVSettings(BaseModel):
    yaw_thresh: float
    pitch_thresh: float
    brightness_thresh: float
    gaze_min: float = 0.025
    gaze_max: float = 0.055


class AudioSettings(BaseModel):
    mic_gain: float
    noise_thresh: float = 0.055


class InjectedQuestion(BaseModel):
    question: str


class InterviewConfigSchema(BaseModel):
    interview_duration_minutes: int
    avatar_gender: str
    question_time_limit_seconds: int
    num_questions: int
    interview_objective: str
    interview_topics: str
    speech_language: str
    text_language: str
    candidate_name: Optional[str] = None
    job_specialty: Optional[str] = None
    is_active: bool


class CreateCandidateSchema(BaseModel):
    name: str
    job_specialty: str


class DeleteCandidatesSchema(BaseModel):
    candidate_ids: list[str]
