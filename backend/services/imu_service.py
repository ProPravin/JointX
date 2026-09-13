"""Orchestrates IMU calibration, capture, and feature extraction for a screening."""
from database.database import get_cursor
from backend.utils.helpers import to_json
from backend.utils.error_handler import DataQualityError
from imu.sensor_manager import IMUSensorManager
from imu.calibration import compute_bias, apply_bias
from imu.feature_extraction import extract_imu_features

_manager = IMUSensorManager()


def get_device_status() -> dict:
    return _manager.get_status()


def calibrate_imu() -> dict:
    return _manager.calibrate()


def start_imu() -> dict:
    return _manager.start()


def stop_imu() -> dict:
    return _manager.stop()


def run_imu_movement_test(screening_id: int, n_samples: int = 200) -> dict:
    # Brief still capture used purely to derive a zero-offset bias.
    still = _manager.read_movement_test(n_samples=20)
    left_bias = compute_bias(still["left"])
    right_bias = compute_bias(still["right"])

    stream = _manager.read_movement_test(n_samples=n_samples)
    left = apply_bias(stream["left"], left_bias)
    right = apply_bias(stream["right"], right_bias)

    features = extract_imu_features(left, right)
    is_demo = stream["is_demo"]

    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM imu_features WHERE screening_id = ?", (screening_id,))
        cur.execute(
            """INSERT INTO imu_features
               (screening_id, is_demo, data_quality_ok, left_samples, right_samples,
                acceleration_rms, acceleration_variance, peak_acceleration,
                angular_velocity_rms, peak_angular_velocity, relative_joint_rom,
                movement_smoothness, movement_cycle_duration, raw_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                screening_id,
                int(is_demo),
                int(features["data_quality_ok"]),
                features.get("left_samples"),
                features.get("right_samples"),
                features.get("acceleration_rms"),
                features.get("acceleration_variance"),
                features.get("peak_acceleration"),
                features.get("angular_velocity_rms"),
                features.get("peak_angular_velocity"),
                features.get("relative_joint_rom"),
                features.get("movement_smoothness"),
                features.get("movement_cycle_duration"),
                to_json(features),
            ),
        )

    features["is_demo"] = is_demo
    if not features["data_quality_ok"]:
        raise DataQualityError(features.get("quality_message", "Insufficient IMU data."))
    return features
