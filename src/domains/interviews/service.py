from typing import Dict, Any
from src.shared.database import log_activity
from src.shared.redis_client import increment_candidate_strikes, get_candidate_strikes

async def evaluate_candidate_frame(
    candidate_id: str,
    is_violation: bool,
    details: Dict[str, Any],
    video_quality: str
) -> Dict[str, Any]:
    """
    Evaluates candidate metrics, increments strikes if needed,
    and logs telemetry to MongoDB asynchronously.
    """
    # 1. Asynchronously log telemetry metrics to MongoDB
    await log_activity(candidate_id, "telemetry_update", {
        "metrics": details,
        "video_quality": video_quality
    })
    
    # 2. Get current strikes from Redis
    current_strikes = await get_candidate_strikes(candidate_id)
    
    response_data = {
        "action": "continue",
        "video_quality": video_quality,
        "current_strikes": current_strikes
    }

    # 3. Handle violation rules engine
    if is_violation:
        current_strikes = await increment_candidate_strikes(candidate_id)
        response_data["current_strikes"] = current_strikes
        
        await log_activity(candidate_id, "strike_issued", {
            "strike_count": current_strikes,
            "cause": details
        })
        
        if current_strikes >= 4:
            response_data["action"] = "terminate"
        else:
            response_data["action"] = "warn"
            
    return response_data
