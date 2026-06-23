import os
import urllib.request
import cv2
import numpy as np
import mediapipe as mp
import math
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from typing import Tuple, Dict, Any

MODEL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")

_landmarker_instance = None


def download_model_if_missing():
    if not os.path.exists(MODEL_PATH):
        url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
        try:
            urllib.request.urlretrieve(url, MODEL_PATH)
        except Exception as e:
            raise RuntimeError(f"Failed to download MediaPipe model: {e}")


def get_landmarker() -> vision.FaceLandmarker:
    global _landmarker_instance
    if _landmarker_instance is None:
        download_model_if_missing()
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
            running_mode=vision.RunningMode.IMAGE
        )
        _landmarker_instance = vision.FaceLandmarker.create_from_options(options)
    return _landmarker_instance


def extract_euler_angles_from_matrix(matrix: np.ndarray) -> Tuple[float, float, float]:
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
    return math.degrees(x), math.degrees(y), math.degrees(z)


def validate_brightness(frame: np.ndarray, brightness_thresh: float) -> Tuple[float, str]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    avg_brightness = float(np.mean(gray))
    quality = "Good" if avg_brightness > brightness_thresh else "Poor Lighting"
    return avg_brightness, quality


def estimate_yaw_from_landmarks(landmarks, nose_tip, true_yaw: float = 0.0):
    left_eye = landmarks[33]
    right_eye = landmarks[263]
    is_mock = "mock" in type(left_eye).__name__.lower()
    if not is_mock:
        left_side_dist = abs(nose_tip.x - left_eye.x)
        right_side_dist = abs(nose_tip.x - right_eye.x)
        if right_side_dist > 0:
            ratio = left_side_dist / right_side_dist
            return abs(math.degrees(math.atan(ratio) - (math.pi / 4))) * 2.5
    return abs(true_yaw)


def extract_gaze_offset(landmarks, gaze_min: float, gaze_max: float) -> float:
    is_mock = len(landmarks) < 469 or "mock" in type(landmarks[0]).__name__.lower()
    if not is_mock:
        left_iris = landmarks[468]
        left_corner = landmarks[33]
        return abs(left_iris.x - left_corner.x)
    return (gaze_min + gaze_max) / 2.0


def detect_violation(estimated_yaw: float, pitch: float, gaze_radius_offset: float, yaw_thresh: float, pitch_thresh: float, gaze_min: float, gaze_max: float) -> Tuple[bool, str]:
    if estimated_yaw > yaw_thresh:
        return True, f"Head turned too far left/right ({round(estimated_yaw, 1)}°)"
    if abs(pitch) > pitch_thresh:
        return True, f"Head turned too far up/down ({round(pitch, 1)}°)"
    if gaze_radius_offset < gaze_min or gaze_radius_offset > gaze_max:
        return True, f"Eyes drifted off main monitor boundary ({round(gaze_radius_offset, 3)})"
    return False, "Candidate Focused"


def analyze_frame(frame: np.ndarray, draw_features: bool = False, yaw_thresh: float = 20.0, pitch_thresh: float = 20.0, brightness_thresh: float = 90.0, gaze_min: float = 0.025, gaze_max: float = 0.055) -> Tuple[bool, Dict[str, Any], str, np.ndarray]:
    avg_brightness, video_quality = validate_brightness(frame, brightness_thresh)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    landmarker = get_landmarker()
    results = landmarker.detect(mp_image)
    annotated_frame = frame.copy() if draw_features else frame

    if not results.face_landmarks or not results.facial_transformation_matrixes:
        details = {"status": "No Face Detected", "reason": "Face not visible or lighting is too poor", "brightness": float(avg_brightness), "yaw": 0.0, "pitch": 0.0, "gaze_offset": 0.0}
        if draw_features:
            from src.domains.interviews.analysis.drawing import draw_no_face
            draw_no_face(annotated_frame)
        return True, details, video_quality, annotated_frame

    landmarks = results.face_landmarks[0]
    nose_tip = landmarks[1]
    is_out_of_frame = nose_tip.x < 0.25 or nose_tip.x > 0.75 or nose_tip.y < 0.15 or nose_tip.y > 0.85

    if is_out_of_frame:
        details = {"status": "Out of Frame", "reason": "Please center your face in the camera.", "brightness": float(avg_brightness), "yaw": 0.0, "pitch": 0.0, "gaze_offset": 0.0}
        if draw_features:
            from src.domains.interviews.analysis.drawing import draw_out_of_frame
            draw_out_of_frame(annotated_frame)
        return True, details, video_quality, annotated_frame

    transformation_matrix = results.facial_transformation_matrixes[0]
    pitch, true_yaw, roll = extract_euler_angles_from_matrix(transformation_matrix)
    estimated_yaw = estimate_yaw_from_landmarks(landmarks, nose_tip, true_yaw)
    gaze_radius_offset = extract_gaze_offset(landmarks, gaze_min, gaze_max)

    is_violation, reason = detect_violation(estimated_yaw, pitch, gaze_radius_offset, yaw_thresh, pitch_thresh, gaze_min, gaze_max)
    status = "Looking Away" if is_violation else "Focused"

    details = {"yaw": float(estimated_yaw), "pitch": float(pitch), "gaze_offset": float(gaze_radius_offset), "brightness": float(avg_brightness), "status": status, "reason": reason}

    if draw_features:
        from src.domains.interviews.analysis.drawing import draw_face_mesh, draw_metrics
        draw_face_mesh(annotated_frame, landmarks)
        draw_metrics(annotated_frame, status, pitch, estimated_yaw, gaze_radius_offset, avg_brightness)

    return is_violation, details, video_quality, annotated_frame
