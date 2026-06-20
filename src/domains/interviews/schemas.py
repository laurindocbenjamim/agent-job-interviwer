from typing import Literal
from pydantic import BaseModel, Field

class GazeMetrics(BaseModel):
    """Gaze estimation and camera frame metrics."""
    gaze_metric: float = Field(..., description="Geometric distance between left iris and eye corner")
    brightness: float = Field(..., description="Average brightness of the video frame")
    status: Literal["Focused", "Looking Away"] = Field(..., description="Gaze state of the candidate")

class InterviewResponse(BaseModel):
    """Response payload returned via WebSocket connection."""
    action: Literal["continue", "warn", "terminate"] = Field(..., description="Action to enforce on client")
    video_quality: Literal["Good", "Too Dark"] = Field(..., description="Quality evaluation status of the camera feed")
    current_strikes: int = Field(..., description="Current cumulative strike count")
