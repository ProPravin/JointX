"""
Orchestrates the camera gait-analysis pipeline for a screening: capture (or
simulate) frames, run pose detection, extract features, persist results.
"""
import math
import random

from config.settings import Config
from database.database import get_cursor
from backend.utils.helpers import to_json
from backend.utils.error_handler import DeviceUnavailableError, DataQualityError
from backend.utils.logger import get_logger
from computer_vision.feature_extraction import extract_gait_features

logger = get_logger(__name__)


def _simulate_landmark_frames(n_frames: int = 90, noisy: bool = False):
    """
    Generates a plausible 33-point landmark sequence approximating a walking
    cycle, purely for demo mode. Always tagged is_demo=True by the caller.
    """
    frames = []
    visibilities = []
    for i in range(n_frames):
        phase = (i / n_frames) * 4 * math.pi
        vis = random.uniform(0.3, 0.6) if noisy else random.uniform(0.75, 0.98)
        landmarks = []
        for idx in range(33):
            sway = 0.01 * math.sin(phase + idx * 0.1)
            landmarks.append(
                {
                    "x": 0.5 + sway,
                    "y": 0.5 + 0.05 * math.sin(phase + idx * 0.05) + idx * 0.01,
                    "z": 0.0,
                    "visibility": vis,
                }
            )
        frames.append(landmarks)
        visibilities.append(vis)
    return frames, visibilities


def run_gait_test(screening_id: int, is_demo: bool = None, noisy_demo: bool = False) -> dict:
    is_demo = Config.DEMO_MODE if is_demo is None else is_demo

    if not is_demo:
        try:
            from computer_vision.pose_detection import PoseDetector, capture_frames

            frames = capture_frames(Config.CAMERA_INDEX, max_frames=150, duration_s=8.0)
            detector = PoseDetector()
            landmark_frames, visibilities = [], []
            for frame in frames:
                points, vis = detector.process_frame(frame)
                landmark_frames.append(points)
                visibilities.append(vis)
            detector.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("Camera pipeline unavailable, falling back to demo: %s", e)
            is_demo = True

    if is_demo:
        landmark_frames, visibilities = _simulate_landmark_frames(noisy=noisy_demo)

    features = extract_gait_features(landmark_frames, visibilities)

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM gait_features WHERE screening_id = ?", (screening_id,))
        cur.execute(
            """INSERT INTO gait_features
               (screening_id, is_demo, data_quality_ok, frames_used, mean_visibility,
                cadence, step_time, stride_time, walking_speed, knee_angle_rom,
                stance_swing_ratio, left_right_asymmetry, gait_cycle_variability, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                screening_id,
                int(is_demo),
                int(features["data_quality_ok"]),
                features.get("frames_used"),
                features.get("mean_visibility"),
                features.get("cadence"),
                features.get("step_time"),
                features.get("stride_time"),
                features.get("walking_speed"),
                features.get("knee_angle_rom"),
                features.get("stance_swing_ratio"),
                features.get("left_right_asymmetry"),
                features.get("gait_cycle_variability"),
                to_json(features),
            ),
        )

    features["is_demo"] = is_demo
    if not features["data_quality_ok"]:
        raise DataQualityError(features.get("quality_message", "Insufficient gait data."))
    return features
