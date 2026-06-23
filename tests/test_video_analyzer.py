import numpy as np
import pytest
import math
from unittest.mock import MagicMock, patch
from src.domains.interviews.analysis.video import analyze_frame

def test_analyze_frame_dark_room():
    """Test that a dark frame results in a 'Poor Lighting' quality status."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    with patch("src.domains.interviews.analysis.video.get_landmarker") as mock_get_landmarker:
        mock_detect = mock_get_landmarker.return_value.detect
        mock_detect.return_value.face_landmarks = []
        
        is_violation, details, quality, _ = analyze_frame(frame)
        
        assert quality == "Poor Lighting"
        assert is_violation is True
        assert details["status"] == "No Face Detected"

def test_analyze_frame_bright_room_no_face():
    """Test that a bright frame with no face returns Good quality but no face."""
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 255
    
    with patch("src.domains.interviews.analysis.video.get_landmarker") as mock_get_landmarker:
        mock_detect = mock_get_landmarker.return_value.detect
        mock_detect.return_value.face_landmarks = []
        
        is_violation, details, quality, _ = analyze_frame(frame)
        
        assert quality == "Good"
        assert is_violation is True
        assert details["status"] == "No Face Detected"

def test_analyze_frame_focused_gaze():
    """Test when head pose is focused (angles <= 20 degrees)."""
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    
    mock_nose_tip = MagicMock()
    mock_nose_tip.x = 0.5
    mock_nose_tip.y = 0.5
    
    mock_landmarks = [MagicMock()] * 500
    mock_landmarks[1] = mock_nose_tip
    
    # Focused matrix: identity matrix (yaw=0, pitch=0)
    mock_matrix = np.eye(4)
    
    with patch("src.domains.interviews.analysis.video.get_landmarker") as mock_get_landmarker:
        mock_detect = mock_get_landmarker.return_value.detect
        mock_detect.return_value.face_landmarks = [mock_landmarks]
        mock_detect.return_value.facial_transformation_matrixes = [mock_matrix]
        
        is_violation, details, quality, _ = analyze_frame(frame)
        
        assert quality == "Good"
        assert is_violation is False
        assert details["status"] == "Focused"
        assert pytest.approx(details["yaw"]) == 0.0
        assert pytest.approx(details["pitch"]) == 0.0

def test_analyze_frame_looking_away_gaze():
    """Test when head pose is turned away (yaw > 20 degrees)."""
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
    
    mock_nose_tip = MagicMock()
    mock_nose_tip.x = 0.5
    mock_nose_tip.y = 0.5
    
    mock_landmarks = [MagicMock()] * 500
    mock_landmarks[1] = mock_nose_tip
    
    # 25 degree rotation around Y-axis (yaw)
    mock_matrix = np.eye(4)
    theta = math.radians(25)
    mock_matrix[0, 0] = math.cos(theta)
    mock_matrix[0, 2] = math.sin(theta)
    mock_matrix[2, 0] = -math.sin(theta)
    mock_matrix[2, 2] = math.cos(theta)
    
    with patch("src.domains.interviews.analysis.video.get_landmarker") as mock_get_landmarker:
        mock_detect = mock_get_landmarker.return_value.detect
        mock_detect.return_value.face_landmarks = [mock_landmarks]
        mock_detect.return_value.facial_transformation_matrixes = [mock_matrix]
        
        is_violation, details, quality, _ = analyze_frame(frame)
        
        assert quality == "Good"
        assert is_violation is True
        assert details["status"] == "Looking Away"
        assert pytest.approx(details["yaw"]) == 25.0
