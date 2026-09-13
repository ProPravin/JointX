"""Signal cleanup for pose landmark sequences before gait analysis."""
from config.model_config import MIN_POSE_LANDMARK_VISIBILITY, MIN_POSE_FRAMES


def moving_average(series, window=3):
    if len(series) < window:
        return series[:]
    out = []
    for i in range(len(series)):
        lo = max(0, i - window // 2)
        hi = min(len(series), i + window // 2 + 1)
        out.append(sum(series[lo:hi]) / (hi - lo))
    return out


def assess_pose_data_quality(landmark_frames, visibilities):
    """
    Returns (is_ok: bool, reason: str, mean_visibility: float, usable_frames: int)
    Mirrors spec section 7: if quality is poor, no risk result should be
    produced from this data.
    """
    usable_frames = sum(1 for f in landmark_frames if f is not None)
    mean_visibility = sum(visibilities) / len(visibilities) if visibilities else 0.0

    if usable_frames < MIN_POSE_FRAMES:
        return False, "Insufficient gait data. Please reposition the patient and repeat the test.", mean_visibility, usable_frames
    if mean_visibility < MIN_POSE_LANDMARK_VISIBILITY:
        return False, "Insufficient gait data. Please reposition the patient and repeat the test.", mean_visibility, usable_frames
    return True, "OK", mean_visibility, usable_frames
