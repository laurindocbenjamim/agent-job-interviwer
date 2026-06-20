import os
import urllib.request
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from typing import Tuple, Dict, Any

# Path to local model file
MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")

def download_model_if_missing() -> None:
    """Downloads face_landmarker.task model from Google storage if missing."""
    if not os.path.exists(MODEL_PATH):
        url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
        try:
            # Download block by block to avoid large memory footprints
            urllib.request.urlretrieve(url, MODEL_PATH)
        except Exception as e:
            raise RuntimeError(f"Failed to download MediaPipe model: {e}")

_landmarker_instance = None

def get_landmarker() -> vision.FaceLandmarker:
    global _landmarker_instance
    if _landmarker_instance is None:
        download_model_if_missing()
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            running_mode=vision.RunningMode.IMAGE
        )
        _landmarker_instance = vision.FaceLandmarker.create_from_options(options)
    return _landmarker_instance

def analyze_frame(frame: np.ndarray) -> Tuple[bool, Dict[str, Any], str]:
    """
    Evaluates video quality and facial posture layout using modern MediaPipe Tasks API.
    
    Args:
        frame: OpenCV BGR image array.
        
    Returns:
        (is_violation, details_dict, video_quality_status)
    """
    # 1. Validate Video Brightness
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    avg_brightness = float(np.mean(gray))
    video_quality = "Good" if avg_brightness > 75.0 else "Too Dark"

    # 2. Convert to RGB for MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    
    # 3. Perform detection
    landmarker = get_landmarker()
    results = landmarker.detect(mp_image)
    
    if not results.face_landmarks:
        details = {
            "status": "No Face Detected",
            "reason": "Face not visible or lighting is too poor",
            "brightness": float(avg_brightness)
        }
        return True, details, video_quality

    landmarks = results.face_landmarks[0]
    
    # Gaze estimation: index 468 (left iris center) vs index 33 (left eye corner)
    # Since landmarks is a list of normalized keypoints:
    left_iris = landmarks[468]
    left_eye_corner = landmarks[33]
    
    # Geometric distance calculation
    horizontal_diff = abs(left_iris.x - left_eye_corner.x)
    
    # Gaze deviation violation threshold
    is_looking_away = horizontal_diff < 0.02 or horizontal_diff > 0.06
    
    details = {
        "gaze_metric": float(horizontal_diff),
        "brightness": float(avg_brightness),
        "status": "Looking Away" if is_looking_away else "Focused"
    }

    return is_looking_away, details, video_quality
