from typing import Literal, List, Optional
from pydantic import BaseModel, Field


class GazeMetrics(BaseModel):
    gaze_metric: float = Field(..., description="Geometric distance between left iris and eye corner")
    brightness: float = Field(..., description="Average brightness of the video frame")
    status: Literal["Focused", "Looking Away"] = Field(..., description="Gaze state of the candidate")


class InterviewResponse(BaseModel):
    action: Literal["continue", "warn", "terminate"] = Field(..., description="Action to enforce on client")
    video_quality: Literal["Good", "Too Dark"] = Field(..., description="Quality evaluation status of the camera feed")
    current_strikes: int = Field(..., description="Current cumulative strike count")


class ViolationEvent(BaseModel):
    timestamp: str = Field(..., description="ISO timestamp of the violation event")
    violation_type: str = Field(..., description="Type of violation: gaze_deviation, low_audio, poor_lighting")
    details: dict = Field(default_factory=dict, description="Raw metrics at time of violation")
    strike_number: Optional[int] = Field(None, description="Strike number if applicable")


class ViolationsReport(BaseModel):
    candidate_id: str
    total_violations: int = 0
    total_strikes: int = 0
    events: List[ViolationEvent] = Field(default_factory=list)
    attempt_number: int = 1


class OfferRequest(BaseModel):
    sdp: str
    type: str


class SubmitRequest(BaseModel):
    answer: str = ""


class DeviceTelemetry(BaseModel):
    device: str
    location: str
