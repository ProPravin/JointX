"""
Extraction for the four functional screening tasks (sit-to-stand, squat,
balance, turn), producing the 4 scalar features used in the unified feature
vector (fusion/feature_schema.py):

  sit_to_stand_time, squat_rom, balance_stability, turn_duration

Each test reuses the same IMU/camera capture primitives as the main
gait/IMU pipeline (imu/sensor_manager.py, computer_vision/pose_detection.py)
-- only the reduction logic differs per task. These are prototype-grade
heuristics for a screening tool, not clinical-grade functional assessments.
"""
import math
import statistics

from imu.preprocessing import low_pass_filter, assess_imu_quality
from computer_vision.gait_analysis import compute_knee_angle_series
from computer_vision.preprocessing import moving_average, assess_pose_data_quality

# Movement onset/offset threshold on combined accel magnitude (g above resting
# gravity baseline) used to bound a sit-to-stand repetition set in time.
MOVEMENT_ONSET_THRESHOLD = 0.15


def _accel_magnitude_series(samples):
    return [math.sqrt(s.get("ax", 0) ** 2 + s.get("ay", 0) ** 2 + s.get("az", 0) ** 2) for s in samples]


def _sample_duration_s(samples):
    if len(samples) < 2:
        return 0.0
    t0, t1 = samples[0].get("t"), samples[-1].get("t")
    if t0 is not None and t1 is not None and t1 > t0:
        return (t1 - t0) / 1000.0
    return (len(samples) - 1) * 0.01  # fallback: assume ~100Hz


def extract_sit_to_stand_features(left_samples: list, right_samples: list) -> dict:
    """
    IMU-based sit-to-stand timing: the completion time is bounded by the
    first and last sample where combined accel magnitude departs from the
    resting baseline (~1g), across a fixed-rep-count test window.
    """
    is_ok, message = assess_imu_quality(left_samples, right_samples)
    result = {"data_quality_ok": is_ok, "quality_message": message}
    if not is_ok:
        return result

    accel = low_pass_filter(_accel_magnitude_series(left_samples + right_samples))
    baseline = statistics.median(accel) if accel else 1.0
    active_indices = [i for i, v in enumerate(accel) if abs(v - baseline) > MOVEMENT_ONSET_THRESHOLD]

    if active_indices:
        n = len(left_samples)
        first_i, last_i = active_indices[0] % n, active_indices[-1] % n
        window = left_samples[min(first_i, last_i):max(first_i, last_i) + 1]
        sit_to_stand_time = _sample_duration_s(window) if len(window) > 1 else 0.0
    else:
        sit_to_stand_time = 0.0

    result["sit_to_stand_time"] = round(sit_to_stand_time, 2)
    return result


def extract_squat_features(landmark_frames, visibilities) -> dict:
    """Squat depth/quality via knee-angle range of motion from the camera feed."""
    is_ok, reason, mean_visibility, usable_frames = assess_pose_data_quality(landmark_frames, visibilities)
    result = {"data_quality_ok": is_ok, "quality_message": reason}
    if not is_ok:
        return result

    left_knee = moving_average(compute_knee_angle_series(landmark_frames, "left"))
    right_knee = moving_average(compute_knee_angle_series(landmark_frames, "right"))
    knee_series = left_knee + right_knee
    squat_rom = (max(knee_series) - min(knee_series)) if knee_series else 0.0

    result["squat_rom"] = round(squat_rom, 2)
    return result


def extract_balance_features(left_samples: list, right_samples: list) -> dict:
    """
    Static single/double-leg stance stability: variability (std) of combined
    accel magnitude during a quiet-stance hold. Lower = more stable.
    """
    is_ok, message = assess_imu_quality(left_samples, right_samples)
    result = {"data_quality_ok": is_ok, "quality_message": message}
    if not is_ok:
        return result

    accel = low_pass_filter(_accel_magnitude_series(left_samples + right_samples))
    balance_stability = statistics.pstdev(accel) if len(accel) > 1 else 0.0

    result["balance_stability"] = round(balance_stability, 4)
    return result


def extract_turn_features(left_samples: list, right_samples: list, gz_threshold: float = 20.0) -> dict:
    """
    Turn duration from gyro-Z: the span of time the yaw rate on either sensor
    stays above gz_threshold (deg/s), as in a Timed-Up-and-Go turn segment.
    """
    is_ok, message = assess_imu_quality(left_samples, right_samples)
    result = {"data_quality_ok": is_ok, "quality_message": message}
    if not is_ok:
        return result

    gz_series = low_pass_filter([abs(s.get("gz", 0.0)) for s in left_samples + right_samples])
    active_indices = [i for i, v in enumerate(gz_series) if v > gz_threshold]

    if active_indices:
        n = len(left_samples)
        first_i, last_i = active_indices[0] % n, active_indices[-1] % n
        window = left_samples[min(first_i, last_i):max(first_i, last_i) + 1]
        turn_duration = _sample_duration_s(window) if len(window) > 1 else 0.0
    else:
        turn_duration = 0.0

    result["turn_duration"] = round(turn_duration, 2)
    return result
