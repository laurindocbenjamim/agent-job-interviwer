import pytest
from unittest.mock import AsyncMock, patch
from src.domains.interviews.service import evaluate_candidate_frame

@pytest.mark.asyncio
async def test_evaluate_frame_no_violation():
    """Test candidate evaluation when there is no violation."""
    candidate_id = "candidate_test"
    details = {"gaze_metric": 0.04, "brightness": 120.0, "status": "Focused"}
    video_quality = "Good"
    
    with patch("src.domains.interviews.service.get_candidate_strikes", new_callable=AsyncMock) as mock_get_strikes, \
         patch("src.domains.interviews.service.log_activity", new_callable=AsyncMock) as mock_log_activity:
        
        mock_get_strikes.return_value = 0
        
        result = await evaluate_candidate_frame(
            candidate_id=candidate_id,
            is_violation=False,
            details=details,
            video_quality=video_quality
        )
        
        assert result["action"] == "continue"
        assert result["video_quality"] == "Good"
        assert result["current_strikes"] == 0
        
        mock_log_activity.assert_any_call(
            candidate_id, 
            "telemetry_update", 
            {"metrics": details, "video_quality": video_quality}
        )

@pytest.mark.asyncio
async def test_evaluate_frame_with_violation_warning():
    """Test that a violation increments strikes and issues a warn action below 4 strikes."""
    candidate_id = "candidate_test"
    details = {"gaze_metric": 0.01, "brightness": 120.0, "status": "Looking Away"}
    video_quality = "Good"
    
    with patch("src.domains.interviews.service.get_candidate_strikes", new_callable=AsyncMock) as mock_get_strikes, \
         patch("src.domains.interviews.service.increment_candidate_strikes", new_callable=AsyncMock) as mock_incr_strikes, \
         patch("src.domains.interviews.service.log_activity", new_callable=AsyncMock) as mock_log_activity:
        
        mock_get_strikes.return_value = 1
        mock_incr_strikes.return_value = 2  # Incremented to 2
        
        result = await evaluate_candidate_frame(
            candidate_id=candidate_id,
            is_violation=True,
            details=details,
            video_quality=video_quality
        )
        
        assert result["action"] == "warn"
        assert result["video_quality"] == "Good"
        assert result["current_strikes"] == 2
        
        mock_log_activity.assert_any_call(
            candidate_id,
            "strike_issued",
            {"strike_count": 2, "cause": details}
        )

@pytest.mark.asyncio
async def test_evaluate_frame_with_violation_no_termination():
    """Test that the 4th strike (or higher) does not trigger termination but continues to warn."""
    candidate_id = "candidate_test"
    details = {"gaze_metric": 0.01, "brightness": 120.0, "status": "Looking Away"}
    video_quality = "Good"
    
    with patch("src.domains.interviews.service.get_candidate_strikes", new_callable=AsyncMock) as mock_get_strikes, \
         patch("src.domains.interviews.service.increment_candidate_strikes", new_callable=AsyncMock) as mock_incr_strikes, \
         patch("src.domains.interviews.service.log_activity", new_callable=AsyncMock) as mock_log_activity:
        
        mock_get_strikes.return_value = 3
        mock_incr_strikes.return_value = 4  # Strike count reached 4
        
        result = await evaluate_candidate_frame(
            candidate_id=candidate_id,
            is_violation=True,
            details=details,
            video_quality=video_quality
        )
        
        assert result["action"] == "warn"
        assert result["video_quality"] == "Good"
        assert result["current_strikes"] == 4
        
        mock_log_activity.assert_any_call(
            candidate_id,
            "strike_issued",
            {"strike_count": 4, "cause": details}
        )
