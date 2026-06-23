import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_interview_html_renders_with_config():
    """Test that the dashboard renders with injected interview config."""
    mock_config = MagicMock()
    mock_config.interview_duration_minutes = 30
    mock_config.avatar_gender = "female"
    mock_config.question_time_limit_seconds = 60
    mock_config.is_active = True
    mock_config.speech_language = "en-US"
    mock_config.text_language = "en"

    with patch("src.shared.postgres_db.get_postgres_config", new_callable=AsyncMock, return_value=mock_config):
        response = client.get("/interview/candidate_test")
        assert response.status_code == 200
        assert "Interview AI" in response.text
        assert "Start Interview" in response.text
        assert "PREVIEW" in response.text

@patch("src.domains.interviews.router.get_violation_events", new_callable=AsyncMock)
def test_violations_endpoint_with_events(mock_get_events):
    """Test violations endpoint returns structured report with events."""
    from datetime import datetime, timezone

    mock_get_events.return_value = [
        {
            "timestamp": datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
            "event_type": "strike_issued",
            "details": {
                "strike_count": 1,
                "cause": {"gaze_metric": 0.01, "brightness": 120.0, "status": "Looking Away"},
            },
        },
        {
            "timestamp": datetime(2026, 6, 20, 10, 5, 0, tzinfo=timezone.utc),
            "event_type": "strike_issued",
            "details": {
                "strike_count": 2,
                "cause": {"gaze_metric": 0.008, "brightness": 115.0, "status": "Looking Away"},
            },
        },
    ]

    response = client.get("/interview/candidate_test/violations")
    assert response.status_code == 200

    data = response.json()
    assert data["candidate_id"] == "candidate_test"
    assert data["total_violations"] == 2
    assert data["total_strikes"] == 2
    assert len(data["events"]) == 2
    assert data["events"][0]["strike_number"] == 1

@patch("src.domains.interviews.router.get_violation_events", new_callable=AsyncMock)
def test_violations_endpoint_empty(mock_get_events):
    """Test violations endpoint returns empty report for clean candidate."""
    mock_get_events.return_value = []

    response = client.get("/interview/candidate_clean/violations")
    assert response.status_code == 200

    data = response.json()
    assert data["candidate_id"] == "candidate_clean"
    assert data["total_violations"] == 0
    assert data["total_strikes"] == 0
    assert data["events"] == []
