"""
Thin wrapper around MediaPipe Pose + OpenCV camera capture.

Designed to fail gracefully: if OpenCV/MediaPipe are not installed, or no
camera is attached (common on a dev laptop or during a hackathon demo), the
caller (gait_service) falls back to demo/simulation mode rather than
crashing the app. See spec sections 7 and 20-21.
"""
from backend.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import cv2
    import mediapipe as mp

    CV_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on environment
    CV_AVAILABLE = False
    logger.warning("OpenCV/MediaPipe not available — camera pipeline disabled, demo mode only")


class PoseDetector:
    """Wraps mp.solutions.pose for per-frame landmark extraction."""

    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        if not CV_AVAILABLE:
            raise RuntimeError("MediaPipe/OpenCV not installed in this environment")
        self._mp_pose = mp.solutions.pose
        self.pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def process_frame(self, frame_bgr):
        """Returns (landmarks_list_or_None, mean_visibility)."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self.pose.process(rgb)
        if not result.pose_landmarks:
            return None, 0.0
        landmarks = result.pose_landmarks.landmark
        mean_visibility = sum(lm.visibility for lm in landmarks) / len(landmarks)
        points = [
            {"x": lm.x, "y": lm.y, "z": lm.z, "visibility": lm.visibility}
            for lm in landmarks
        ]
        return points, mean_visibility

    def close(self):
        self.pose.close()


def capture_frames(camera_index: int, max_frames: int, duration_s: float = 8.0):
    """
    Capture frames from a local camera for `duration_s` seconds (up to
    max_frames). Returns a list of BGR frames. Raises RuntimeError if the
    camera cannot be opened -- caller should catch this and offer demo mode.
    """
    if not CV_AVAILABLE:
        raise RuntimeError("OpenCV not installed")

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {camera_index}")

    import time

    frames = []
    start = time.time()
    try:
        while time.time() - start < duration_s and len(frames) < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
    finally:
        cap.release()
    return frames
