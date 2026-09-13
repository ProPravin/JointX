"""
Orchestrates the four functional screening tasks (sit-to-stand, squat,
balance, turn) and persists their features into functional_features, one
row per screening, filled in incrementally as each task is completed.
"""
import math
import random

from config.settings import Config
from database.database import get_cursor
from backend.utils.helpers import to_json, from_json
from backend.utils.error_handler import DataQualityError
from backend.utils.logger import get_logger
from imu.sensor_manager import IMUSensorManager
from imu.calibration import compute_bias, apply_bias
from functional.feature_extraction import (
    extract_sit_to_stand_features,
    extract_squat_features,
    extract_balance_features,
    extract_turn_features,
)

logger = get_logger(__name__)

_manager = IMUSensorManager()


def _simulate_squat_frames(n_frames: int = 60):
    """A plausible knee-flexion cycle (standing -> squat -> standing) for demo mode."""
    frames, visibilities = [], []
    for i in range(n_frames):
        phase = (i / n_frames) * 2 * math.pi
        knee_bend = 0.15 * (1 - math.cos(phase))  # 0 at start/end, peak mid-squat
        vis = random.uniform(0.8, 0.98)
        landmarks = []
        for idx in range(33):
            landmarks.append({"x": 0.5, "y": 0.5 + knee_bend * (idx / 33), "z": 0.0, "visibility": vis})
        frames.append(landmarks)
        visibilities.append(vis)
    return frames, visibilities


def _get_or_init_row(screening_id: int, is_demo: bool) -> dict:
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM functional_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO functional_features (screening_id, is_demo) VALUES (?, ?)",
                (screening_id, int(is_demo)),
            )
            cur.execute("SELECT * FROM functional_features WHERE screening_id = ?", (screening_id,))
            row = cur.fetchone()
    return dict(row)


def _merge_raw_json(existing_raw_json, task_key, features):
    combined = from_json(existing_raw_json, default={}) or {}
    combined[task_key] = features
    return to_json(combined)


def run_sit_to_stand_test(screening_id: int, n_samples: int = 300) -> dict:
    still = _manager.read_movement_test(n_samples=20)
    left_bias, right_bias = compute_bias(still["left"]), compute_bias(still["right"])
    stream = _manager.read_movement_test(n_samples=n_samples)
    left = apply_bias(stream["left"], left_bias)
    right = apply_bias(stream["right"], right_bias)

    features = extract_sit_to_stand_features(left, right)
    row = _get_or_init_row(screening_id, stream["is_demo"])

    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE functional_features SET sit_to_stand_ok = ?, sit_to_stand_time = ?,
               raw_json = ?, updated_at = datetime('now') WHERE screening_id = ?""",
            (
                int(features["data_quality_ok"]),
                features.get("sit_to_stand_time"),
                _merge_raw_json(row.get("raw_json"), "sit_to_stand", features),
                screening_id,
            ),
        )

    features["is_demo"] = stream["is_demo"]
    if not features["data_quality_ok"]:
        raise DataQualityError(features.get("quality_message", "Insufficient sit-to-stand data."))
    return features


def run_squat_test(screening_id: int, is_demo: bool = None) -> dict:
    is_demo = Config.DEMO_MODE if is_demo is None else is_demo

    if not is_demo:
        try:
            from computer_vision.pose_detection import PoseDetector, capture_frames

            frames = capture_frames(Config.CAMERA_INDEX, max_frames=90, duration_s=6.0)
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
        landmark_frames, visibilities = _simulate_squat_frames()

    features = extract_squat_features(landmark_frames, visibilities)
    row = _get_or_init_row(screening_id, is_demo)

    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE functional_features SET squat_ok = ?, squat_rom = ?,
               raw_json = ?, updated_at = datetime('now') WHERE screening_id = ?""",
            (
                int(features["data_quality_ok"]),
                features.get("squat_rom"),
                _merge_raw_json(row.get("raw_json"), "squat", features),
                screening_id,
            ),
        )

    features["is_demo"] = is_demo
    if not features["data_quality_ok"]:
        raise DataQualityError(features.get("quality_message", "Insufficient squat data."))
    return features


def run_balance_test(screening_id: int, n_samples: int = 300) -> dict:
    still = _manager.read_movement_test(n_samples=20)
    left_bias, right_bias = compute_bias(still["left"]), compute_bias(still["right"])
    stream = _manager.read_movement_test(n_samples=n_samples)
    left = apply_bias(stream["left"], left_bias)
    right = apply_bias(stream["right"], right_bias)

    features = extract_balance_features(left, right)
    row = _get_or_init_row(screening_id, stream["is_demo"])

    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE functional_features SET balance_ok = ?, balance_stability = ?,
               raw_json = ?, updated_at = datetime('now') WHERE screening_id = ?""",
            (
                int(features["data_quality_ok"]),
                features.get("balance_stability"),
                _merge_raw_json(row.get("raw_json"), "balance", features),
                screening_id,
            ),
        )

    features["is_demo"] = stream["is_demo"]
    if not features["data_quality_ok"]:
        raise DataQualityError(features.get("quality_message", "Insufficient balance data."))
    return features


def run_turn_test(screening_id: int, n_samples: int = 150) -> dict:
    still = _manager.read_movement_test(n_samples=20)
    left_bias, right_bias = compute_bias(still["left"]), compute_bias(still["right"])
    stream = _manager.read_movement_test(n_samples=n_samples)
    left = apply_bias(stream["left"], left_bias)
    right = apply_bias(stream["right"], right_bias)

    features = extract_turn_features(left, right)
    row = _get_or_init_row(screening_id, stream["is_demo"])

    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE functional_features SET turn_ok = ?, turn_duration = ?,
               raw_json = ?, updated_at = datetime('now') WHERE screening_id = ?""",
            (
                int(features["data_quality_ok"]),
                features.get("turn_duration"),
                _merge_raw_json(row.get("raw_json"), "turn", features),
                screening_id,
            ),
        )

    features["is_demo"] = stream["is_demo"]
    if not features["data_quality_ok"]:
        raise DataQualityError(features.get("quality_message", "Insufficient turn data."))
    return features


def get_functional_features(screening_id: int) -> dict:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM functional_features WHERE screening_id = ?", (screening_id,))
        row = cur.fetchone()
    return dict(row) if row else None
