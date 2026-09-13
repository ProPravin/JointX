"""
Reduces filtered dual-IMU streams (thigh + shank/lower-leg MPU6050 units)
into the 8 scalar IMU features used in the unified feature vector
(fusion/feature_schema.py):

  acceleration_rms, acceleration_variance, peak_acceleration,
  angular_velocity_rms, peak_angular_velocity, relative_joint_rom,
  movement_smoothness, movement_cycle_duration

`left_samples`/`right_samples` names are kept for compatibility with the
existing two-unit hardware wiring (imu/sensor_manager.py, imu/esp32_client.py);
for a meaningful relative_joint_rom the two MPU6050 units should be mounted
on the thigh and the shank of the same limb rather than on opposite limbs.
"""
import math
import statistics

from imu.preprocessing import low_pass_filter, assess_imu_quality

DEFAULT_DT_S = 0.01  # ~100Hz sampling, used when sample timestamps are absent


def _accel_magnitude_series(samples):
    return [math.sqrt(s.get("ax", 0) ** 2 + s.get("ay", 0) ** 2 + s.get("az", 0) ** 2) for s in samples]


def _gyro_magnitude_series(samples):
    return [math.sqrt(s.get("gx", 0) ** 2 + s.get("gy", 0) ** 2 + s.get("gz", 0) ** 2) for s in samples]


def _sample_dts(samples):
    """Per-sample time deltas in seconds, from each sample's 't' field (ms) if present."""
    dts = []
    for i in range(1, len(samples)):
        t0, t1 = samples[i - 1].get("t"), samples[i].get("t")
        if t0 is not None and t1 is not None and t1 > t0:
            dts.append((t1 - t0) / 1000.0)
        else:
            dts.append(DEFAULT_DT_S)
    return dts


def _integrate_gyro_axis(samples, axis="gy"):
    """Integrates one gyro axis (deg/s) over time into an orientation-angle series (deg)."""
    if len(samples) < 2:
        return []
    dts = _sample_dts(samples)
    angle = 0.0
    series = [angle]
    for i, dt in enumerate(dts, start=1):
        angle += samples[i].get(axis, 0.0) * dt
        series.append(angle)
    return series


def _rms(values):
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else 0.0


def _movement_smoothness(gyro_series, dts):
    """
    Normalized-jerk-based smoothness score in (0, 1], 1.0 = perfectly smooth.
    Lower values indicate jerkier, less-controlled movement.
    """
    if len(gyro_series) < 3 or not dts:
        return 1.0
    jerks = [
        (gyro_series[i + 1] - 2 * gyro_series[i] + gyro_series[i - 1]) / (dts[min(i, len(dts) - 1)] ** 2)
        for i in range(1, len(gyro_series) - 1)
    ]
    mean_abs_jerk = statistics.mean(abs(j) for j in jerks)
    peak = max(abs(v) for v in gyro_series) or 1.0
    duration = sum(dts)
    normalized_jerk = mean_abs_jerk * (duration ** 1.5) / peak if peak else 0.0
    return round(1.0 / (1.0 + normalized_jerk), 3)


def _movement_cycle_duration(signal, dts):
    """
    Estimates the dominant movement-cycle period (s) via autocorrelation of
    the (mean-removed) signal, returning the lag of the first strong peak
    after lag 0.
    """
    n = len(signal)
    if n < 10 or not dts:
        return 0.0
    mean = statistics.mean(signal)
    centered = [v - mean for v in signal]
    energy = sum(v * v for v in centered)
    if energy == 0:
        return 0.0

    max_lag = n // 2
    best_lag, best_corr = None, 0.0
    prev_corr = None
    for lag in range(1, max_lag):
        corr = sum(centered[i] * centered[i + lag] for i in range(n - lag)) / energy
        if prev_corr is not None and prev_corr < corr and (best_lag is None or corr > best_corr):
            if corr > 0.2:  # require a reasonably strong periodic match
                best_lag, best_corr = lag, corr
        prev_corr = corr
        if best_lag is not None and lag > best_lag + 5:
            break

    if best_lag is None:
        return 0.0
    avg_dt = statistics.mean(dts)
    return round(best_lag * avg_dt, 3)


def extract_imu_features(left_samples: list, right_samples: list) -> dict:
    """left_samples/right_samples: thigh-mounted and shank-mounted MPU6050 streams."""
    is_ok, message = assess_imu_quality(left_samples, right_samples)

    result = {
        "data_quality_ok": is_ok,
        "quality_message": message,
        "left_samples": len(left_samples),
        "right_samples": len(right_samples),
    }
    if not is_ok:
        return result

    combined_accel = _accel_magnitude_series(left_samples) + _accel_magnitude_series(right_samples)
    combined_gyro_mag = _gyro_magnitude_series(left_samples) + _gyro_magnitude_series(right_samples)

    filtered_accel = low_pass_filter(combined_accel)
    filtered_gyro = low_pass_filter(combined_gyro_mag)

    acceleration_rms = _rms(filtered_accel)
    acceleration_variance = statistics.pvariance(filtered_accel) if len(filtered_accel) > 1 else 0.0
    peak_acceleration = max(filtered_accel) if filtered_accel else 0.0

    angular_velocity_rms = _rms(filtered_gyro)
    peak_angular_velocity = max(filtered_gyro) if filtered_gyro else 0.0

    thigh_angle = _integrate_gyro_axis(left_samples, axis="gy")
    shank_angle = _integrate_gyro_axis(right_samples, axis="gy")
    n = min(len(thigh_angle), len(shank_angle))
    if n > 1:
        relative_angle = [thigh_angle[i] - shank_angle[i] for i in range(n)]
        relative_joint_rom = max(relative_angle) - min(relative_angle)
    else:
        relative_joint_rom = 0.0

    dts = _sample_dts(left_samples) or [DEFAULT_DT_S]
    movement_smoothness = _movement_smoothness(low_pass_filter(_gyro_magnitude_series(left_samples)), dts)
    movement_cycle_duration = _movement_cycle_duration(filtered_accel, dts)

    result.update(
        {
            "acceleration_rms": round(acceleration_rms, 3),
            "acceleration_variance": round(acceleration_variance, 3),
            "peak_acceleration": round(peak_acceleration, 3),
            "angular_velocity_rms": round(angular_velocity_rms, 3),
            "peak_angular_velocity": round(peak_angular_velocity, 3),
            "relative_joint_rom": round(relative_joint_rom, 2),
            "movement_smoothness": movement_smoothness,
            "movement_cycle_duration": movement_cycle_duration,
        }
    )
    return result
