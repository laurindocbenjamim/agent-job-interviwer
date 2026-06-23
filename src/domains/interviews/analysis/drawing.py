import cv2
from mediapipe.tasks.python.vision import drawing_utils, drawing_styles
from mediapipe.tasks.python.vision.face_landmarker import FaceLandmarksConnections

def draw_face_mesh(annotated_frame, landmarks):
    drawing_utils.draw_landmarks(
        image=annotated_frame,
        landmark_list=landmarks,
        connections=FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION,
        landmark_drawing_spec=None,
        connection_drawing_spec=drawing_styles.get_default_face_mesh_tesselation_style()
    )
    drawing_utils.draw_landmarks(
        image=annotated_frame,
        landmark_list=landmarks,
        connections=FaceLandmarksConnections.FACE_LANDMARKS_CONTOURS,
        landmark_drawing_spec=None,
        connection_drawing_spec=drawing_styles.get_default_face_mesh_contours_style()
    )


def draw_metrics(annotated_frame, status, pitch, estimated_yaw, gaze_radius_offset, avg_brightness):
    color = (0, 0, 255) if status == "Looking Away" else (0, 255, 0)
    cv2.putText(annotated_frame, f"Status: {status}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.putText(annotated_frame, f"Pitch: {pitch:.1f}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(annotated_frame, f"Yaw: {estimated_yaw:.1f}", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(annotated_frame, f"Gaze Offset: {gaze_radius_offset:.3f}", (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(annotated_frame, f"Brightness: {avg_brightness:.1f}", (20, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)


def draw_no_face(annotated_frame):
    cv2.putText(annotated_frame, "NO FACE DETECTED", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)


def draw_out_of_frame(annotated_frame):
    cv2.putText(annotated_frame, "OUT OF FRAME", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 2)
