import os
import urllib.request
import cv2
import numpy as np
import mediapipe as mp
import math
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
            output_facial_transformation_matrixes=True,  # Crucial for Head Pose (Yaw/Pitch)
            running_mode=vision.RunningMode.IMAGE
        )
        _landmarker_instance = vision.FaceLandmarker.create_from_options(options)
    return _landmarker_instance

def extract_euler_angles_from_matrix(matrix: np.ndarray) -> Tuple[float, float, float]:
    """Extracts yaw, pitch, and roll in degrees from a 4x4 transformation matrix."""
    # The 3x3 rotation matrix is the top-left portion
    rmat = matrix[:3, :3]
    sy = math.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])
    singular = sy < 1e-6

    if not singular:
        x = math.atan2(rmat[2, 1], rmat[2, 2])
        y = math.atan2(-rmat[2, 0], sy)
        z = math.atan2(rmat[1, 0], rmat[0, 0])
    else:
        x = math.atan2(-rmat[1, 2], rmat[1, 1])
        y = math.atan2(-rmat[2, 0], sy)
        z = 0

    # Convert to degrees
    pitch = math.degrees(x)
    yaw = math.degrees(y)
    roll = math.degrees(z)
    
    return pitch, yaw, roll

def analyze_frame(frame: np.ndarray) -> Tuple[bool, Dict[str, Any], str]:
    """
    Evaluates video quality and facial posture layout using modern MediaPipe Tasks API.
    """
    # 1. Validate Video Brightness
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    avg_brightness = float(np.mean(gray))
    video_quality = "Good" if avg_brightness > 90.0 else "Poor Lighting"

    # 2. Convert to RGB for MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    
    # 3. Perform detection
    landmarker = get_landmarker()
    results = landmarker.detect(mp_image)
    
    if not results.face_landmarks or not results.facial_transformation_matrixes:
        details = {
            "status": "No Face Detected",
            "reason": "Face not visible or lighting is too poor",
            "brightness": float(avg_brightness)
        }
        return True, details, video_quality

    landmarks = results.face_landmarks[0]
    
    # Check if face is centered and fully in frame using nose tip (index 1)
    nose_tip = landmarks[1]
    is_out_of_frame = nose_tip.x < 0.25 or nose_tip.x > 0.75 or nose_tip.y < 0.15 or nose_tip.y > 0.85
    
    if is_out_of_frame:
        details = {
            "status": "Out of Frame",
            "reason": "Please center your face in the camera.",
            "brightness": float(avg_brightness)
        }
        return True, details, video_quality
    
    # Extract true 3D Head Pose Angles
    transformation_matrix = results.facial_transformation_matrixes[0]
    pitch, yaw, roll = extract_euler_angles_from_matrix(transformation_matrix)
    
    # Thresholds: If the head turns more than 20 degrees left/right or up/down
    is_looking_away = abs(yaw) > 20.0 or abs(pitch) > 20.0
    
    details = {
        "yaw": float(yaw),
        "pitch": float(pitch),
        "brightness": float(avg_brightness),
        "status": "Looking Away" if is_looking_away else "Focused"
    }

    return is_looking_away, details, video_quality
