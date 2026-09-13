"""
Reduces per-frame pose landmark sequences into the 8 scalar gait features
used downstream in fusion/feature_schema.py:

  cadence, step_time, stride_time, walking_speed, knee_angle_rom,
  stance_swing_ratio, left_right_asymmetry, gait_cycle_variability

Kept separate from pose_detection.py so the same function set can run on
real camera data or demo/simulated landmark sequences (spec section 21:
demo mode must reuse the real pipeline).
"""
import statistics

from computer_vision.gait_analysis import (
    compute_knee_angle_series,
    compute_ankle_vertical_series,
    compute_hip_series,
    detect_step_events,
    detect_toe_off_events,
)
from computer_vision.preprocessing import moving_average, assess_pose_data_quality

# Real-world distance (m) the subject is assumed to cross during a straight
# walk test, used to convert normalized hip displacement into walking_speed.
# None disables the conversion (walking_speed stays None) unless a caller
# supplies a calibrated value.
DEFAULT_WALK_DISTANCE_M = None


def _stride_intervals_s(step_frame_indices, fps):
    """Time (s) between every other step on the same foot -> full gait cycles."""
    if len(step_frame_indices) < 3 or not fps:
        return []
    return [(step_frame_indices[i + 2] - step_frame_indices[i]) / fps for i in range(len(step_frame_indices) - 2)]


def _step_intervals_s(step_frame_indices, fps):
    if len(step_frame_indices) < 2 or not fps:
        return []
    return [(step_frame_indices[i + 1] - step_frame_indices[i]) / fps for i in range(len(step_frame_indices) - 1)]


def extract_gait_features(landmark_frames, visibilities, fps: float = 15.0, walk_distance_m: float = None) -> dict:
    """
    landmark_frames: list of (list-of-33-landmark-dicts or None)
    visibilities: list of per-frame mean visibility scores
    fps: approximate capture frame rate, used to convert frame counts to seconds
    walk_distance_m: known real-world distance covered during the walk test,
        used to compute walking_speed; left None when no scale reference is
        available (walking_speed is then reported as None).

    Returns a dict with data_quality_ok flag plus scalar gait features.
    Raises nothing -- caller (gait_service) decides how to handle a
    data_quality_ok == False result.
    """
    is_ok, reason, mean_visibility, usable_frames = assess_pose_data_quality(
        landmark_frames, visibilities
    )

    result = {
        "data_quality_ok": is_ok,
        "quality_message": reason,
        "mean_visibility": round(mean_visibility, 3),
        "frames_used": usable_frames,
    }

    if not is_ok:
        return result

    left_knee = moving_average(compute_knee_angle_series(landmark_frames, "left"))
    right_knee = moving_average(compute_knee_angle_series(landmark_frames, "right"))
    left_ankle_y = moving_average(compute_ankle_vertical_series(landmark_frames, "left"))
    right_ankle_y = moving_average(compute_ankle_vertical_series(landmark_frames, "right"))
    left_hip_y = moving_average(compute_hip_series(landmark_frames, "left"))
    right_hip_y = moving_average(compute_hip_series(landmark_frames, "right"))

    left_steps = detect_step_events(left_ankle_y)
    right_steps = detect_step_events(right_ankle_y)
    left_toe_offs = detect_toe_off_events(left_ankle_y)
    right_toe_offs = detect_toe_off_events(right_ankle_y)
    total_steps = len(left_steps) + len(right_steps)
    duration_s = usable_frames / fps if fps else 0

    cadence = (total_steps / duration_s * 60.0) if duration_s > 0 else 0.0

    step_intervals = _step_intervals_s(sorted(left_steps + right_steps), fps)
    step_time = statistics.mean(step_intervals) if step_intervals else 0.0

    left_stride_intervals = _stride_intervals_s(left_steps, fps)
    right_stride_intervals = _stride_intervals_s(right_steps, fps)
    all_stride_intervals = left_stride_intervals + right_stride_intervals
    stride_time = statistics.mean(all_stride_intervals) if all_stride_intervals else 0.0

    walk_distance_m = walk_distance_m if walk_distance_m is not None else DEFAULT_WALK_DISTANCE_M
    walking_speed = (walk_distance_m / duration_s) if (walk_distance_m and duration_s > 0) else None

    knee_series = left_knee + right_knee
    knee_angle_rom = (max(knee_series) - min(knee_series)) if knee_series else 0.0

    # Stance/swing ratio: mean(heel-strike -> toe-off) / mean(toe-off -> next heel-strike),
    # per limb, pooled across both limbs. A simplified heuristic for prototype/demo use.
    stance_durations, swing_durations = [], []
    for steps, toe_offs in ((left_steps, left_toe_offs), (right_steps, right_toe_offs)):
        events = sorted([(f, "strike") for f in steps] + [(f, "off") for f in toe_offs])
        for i in range(len(events) - 1):
            (f0, k0), (f1, k1) = events[i], events[i + 1]
            duration = (f1 - f0) / fps if fps else 0
            if k0 == "strike" and k1 == "off":
                stance_durations.append(duration)
            elif k0 == "off" and k1 == "strike":
                swing_durations.append(duration)
    mean_stance = statistics.mean(stance_durations) if stance_durations else 0.0
    mean_swing = statistics.mean(swing_durations) if swing_durations else 0.0
    stance_swing_ratio = (mean_stance / mean_swing) if mean_swing > 0 else 0.0

    # Left-right asymmetry (%): 0 = perfectly symmetric step timing between limbs.
    left_step_time = statistics.mean(_step_intervals_s(left_steps, fps)) if len(left_steps) > 1 else None
    right_step_time = statistics.mean(_step_intervals_s(right_steps, fps)) if len(right_steps) > 1 else None
    if left_step_time and right_step_time:
        denom = (left_step_time + right_step_time) / 2.0
        left_right_asymmetry = abs(left_step_time - right_step_time) / denom * 100.0 if denom else 0.0
    elif left_steps or right_steps:
        denom = max(1, len(left_steps) + len(right_steps))
        left_right_asymmetry = abs(len(left_steps) - len(right_steps)) / denom * 100.0
    else:
        left_right_asymmetry = 0.0

    # Gait-cycle variability (%): coefficient of variation of stride time.
    if len(all_stride_intervals) > 1 and stride_time:
        gait_cycle_variability = statistics.pstdev(all_stride_intervals) / stride_time * 100.0
    else:
        gait_cycle_variability = 0.0

    result.update(
        {
            "cadence": round(cadence, 2),
            "step_time": round(step_time, 3),
            "stride_time": round(stride_time, 3),
            "walking_speed": round(walking_speed, 3) if walking_speed is not None else None,
            "knee_angle_rom": round(knee_angle_rom, 2),
            "stance_swing_ratio": round(stance_swing_ratio, 3),
            "left_right_asymmetry": round(left_right_asymmetry, 2),
            "gait_cycle_variability": round(gait_cycle_variability, 2),
        }
    )
    return result
