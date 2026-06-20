import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from src.domains.interviews.video_analyzer import analyze_frame

def test_analyze_frame_dark_room():
    """Test that a dark frame results in a 'Too Dark' quality status."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    with patch("src.domains.interviews.video_analyzer.landmarker.detect") as mock_detect:
        mock_detect.return_value.face_landmarks = []
        
        is_violation, details, quality = analyze_frame(frame)
        
        assert quality == "Too Dark"
        assert is_violation is False
        assert details == {"reason": "No face in frame"}

def test_analyze_frame_bright_room_no_face():
    """Test that a bright frame with no face returns Good quality but no face."""
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 255
    
    with patch("src.domains.interviews.video_analyzer.landmarker.detect") as mock_detect:
        mock_detect.return_value.face_landmarks = []
        
        is_violation, details, quality = analyze_frame(frame)
        
        assert quality == "Good"
        assert is_violation is False
        assert details == {"reason": "No face in frame"}

def test_analyze_frame_focused_gaze():
    """Test when horizontal distance is in focused range (0.02 - 0.06)."""
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    
    # Mock landmarks
    mock_landmark_left_iris = MagicMock()
    mock_landmark_left_iris.x = 0.54  # horizontal diff is 0.04
    mock_landmark_left_eye_corner = MagicMock()
    mock_landmark_left_eye_corner.x = 0.50
    
    # Create landmark list where index 468 is iris, 33 is corner
    mock_landmarks = [MagicMock()] * 500
    mock_landmarks[468] = mock_landmark_left_iris
    mock_landmarks[33] = mock_landmark_left_eye_corner
    
    with patch("src.domains.interviews.video_analyzer.landmarker.detect") as mock_detect:
        mock_detect.return_value.face_landmarks = [mock_landmarks]
        
        is_violation, details, quality = analyze_frame(frame)
        
        assert quality == "Good"
        assert is_violation is False
        assert details["status"] == "Focused"
        assert pytest.approx(details["gaze_metric"]) == 0.04

def test_analyze_frame_looking_away_gaze():
    """Test when candidate is looking away (diff < 0.02 or diff > 0.06)."""
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    
    # Mock landmarks - diff is 0.01 (too narrow)
    mock_landmark_left_iris = MagicMock()
    mock_landmark_left_iris.x = 0.51
    mock_landmark_left_eye_corner = MagicMock()
    mock_landmark_left_eye_corner.x = 0.50
    
    mock_landmarks = [MagicMock()] * 500
    mock_landmarks[468] = mock_landmark_left_iris
    mock_landmarks[33] = mock_landmark_left_eye_corner
    
    with patch("src.domains.interviews.video_analyzer.landmarker.detect") as mock_detect:
        mock_detect.return_value.face_landmarks = [mock_landmarks]
        
        is_violation, details, quality = analyze_frame(frame)
        
        assert quality == "Good"
        assert is_violation is True
        assert details["status"] == "Looking Away"
        assert pytest.approx(details["gaze_metric"]) == 0.01
