"""
Calibration helpers for MPU6050 sensors: computing zero-offset bias from a
short still-standing capture, and applying that offset to subsequent
readings. Works identically on real or simulated streams.
"""
import statistics


def compute_bias(still_samples: list) -> dict:
    """
    still_samples: list of {'ax','ay','az','gx','gy','gz', ...}
    Returns per-axis mean values captured while the limb was stationary,
    which callers subtract from subsequent readings as a zero-offset.
    """
    if not still_samples:
        return {k: 0.0 for k in ("ax", "ay", "az", "gx", "gy", "gz")}

    bias = {}
    for axis in ("ax", "ay", "az", "gx", "gy", "gz"):
        values = [s[axis] for s in still_samples if axis in s]
        bias[axis] = statistics.mean(values) if values else 0.0
    # Gravity should remain on az; only zero the gyro drift and ax/ay tilt.
    bias["az"] = 0.0
    return bias


def apply_bias(samples: list, bias: dict) -> list:
    corrected = []
    for s in samples:
        c = dict(s)
        for axis in ("ax", "ay", "az", "gx", "gy", "gz"):
            if axis in c:
                c[axis] = c[axis] - bias.get(axis, 0.0)
        corrected.append(c)
    return corrected
