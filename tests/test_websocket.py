import json
import pytest
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from src.main import app

client = TestClient(app)

def test_interview_html_route():
    """Test that the dashboard HTML page renders and returns 200."""
    response = client.get("/interview/candidate_123")
    assert response.status_code == 200
    assert "Secure Interview Console" in response.text
    assert "AI-Monitored Interview Session" in response.text

@patch("src.domains.interviews.router.log_activity", new_callable=AsyncMock)
@patch("src.domains.interviews.router.cv2.imdecode")
@patch("src.domains.interviews.router.analyze_frame")
@patch("src.domains.interviews.router.evaluate_candidate_frame")
def test_websocket_stream_flow(mock_evaluate, mock_analyze, mock_imdecode, mock_log):
    """Test the WebSocket stream process using mock analyzer and rules engine."""
    mock_imdecode.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_analyze.return_value = (False, {"status": "Focused"}, "Good")
    mock_evaluate.return_value = {
        "action": "continue",
        "video_quality": "Good",
        "current_strikes": 0
    }

    # Dummy base64 image payload (valid base64 string padding)
    dummy_payload = {
        "image": "data:image/jpeg;base64,AAAA"
    }

    with client.websocket_connect("/ws/interview/candidate_123") as websocket:
        websocket.send_json(dummy_payload)
        data = websocket.receive_json()
        
        assert data["action"] == "continue"
        assert data["video_quality"] == "Good"
        assert data["current_strikes"] == 0

        mock_imdecode.assert_called_once()
        mock_analyze.assert_called_once()
        mock_evaluate.assert_called_once()
