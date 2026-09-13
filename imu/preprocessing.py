"""Noise filtering and data-quality checks for raw IMU sample streams."""
from config.model_config import MIN_IMU_SAMPLES


def low_pass_filter(values: list, alpha: float = 0.3) -> list:
    """Simple exponential moving average low-pass filter."""
    if not values:
        return []
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def detect_missing_data(samples: list, expected_min: int = MIN_IMU_SAMPLES) -> bool:
    """Returns True if data is missing/insufficient."""
    return len(samples) < expected_min


def assess_imu_quality(left_samples: list, right_samples: list):
    missing = detect_missing_data(left_samples) or detect_missing_data(right_samples)
    if missing:
        return False, "Insufficient IMU data. Please check sensor placement and repeat the test."
    return True, "OK"
