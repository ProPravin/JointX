"""
Turns a sequence of per-frame pose landmarks into gait-cycle-level signals
(knee angle over time, hip/ankle vertical position, step timing) that
feature_extraction.py then reduces to scalar features.

MediaPipe Pose landmark indices used here (BlazePose 33-point model):
  23/24 = left/right hip, 25/26 = left/right knee, 27/28 = left/right ankle
"""
import math

L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28


def _angle(a, b, c):
    """Angle at point b formed by points a-b-c, in degrees."""
    ab = (a["x"] - b["x"], a["y"] - b["y"])
    cb = (c["x"] - b["x"], c["y"] - b["y"])
    dot = ab[0] * cb[0] + ab[1] * cb[1]
    mag_ab = math.hypot(*ab)
    mag_cb = math.hypot(*cb)
    if mag_ab == 0 or mag_cb == 0:
        return None
    cos_angle = max(-1.0, min(1.0, dot / (mag_ab * mag_cb)))
    return math.degrees(math.acos(cos_angle))


def compute_knee_angle_series(landmark_frames, side="left"):
    hip_i, knee_i, ankle_i = (L_HIP, L_KNEE, L_ANKLE) if side == "left" else (R_HIP, R_KNEE, R_ANKLE)
    series = []
    for frame in landmark_frames:
        if frame is None or len(frame) <= max(hip_i, knee_i, ankle_i):
            continue
        angle = _angle(frame[hip_i], frame[knee_i], frame[ankle_i])
        if angle is not None:
            series.append(angle)
    return series


def compute_ankle_vertical_series(landmark_frames, side="left"):
    ankle_i = L_ANKLE if side == "left" else R_ANKLE
    return [
        f[ankle_i]["y"] for f in landmark_frames
        if f is not None and len(f) > ankle_i
    ]


def detect_step_events(ankle_y_series, min_prominence=0.02):
    """
    Very lightweight local-minima detector on ankle vertical position, used
    as a proxy for heel-strike/step events in a short gait clip. This is a
    simplified heuristic suitable for prototype/demo screening, not a
    clinical-grade gait-event detector.
    """
    events = []
    for i in range(1, len(ankle_y_series) - 1):
        if (
            ankle_y_series[i] < ankle_y_series[i - 1]
            and ankle_y_series[i] < ankle_y_series[i + 1]
            and (ankle_y_series[i - 1] - ankle_y_series[i]) > min_prominence
        ):
            events.append(i)
    return events


def detect_toe_off_events(ankle_y_series, min_prominence=0.02):
    """
    Local-maxima detector on ankle vertical position, used as a proxy for
    toe-off events -- paired with detect_step_events (heel-strikes) to
    approximate stance/swing phase split within a gait cycle.
    """
    events = []
    for i in range(1, len(ankle_y_series) - 1):
        if (
            ankle_y_series[i] > ankle_y_series[i - 1]
            and ankle_y_series[i] > ankle_y_series[i + 1]
            and (ankle_y_series[i] - ankle_y_series[i - 1]) > min_prominence
        ):
            events.append(i)
    return events


def compute_hip_series(landmark_frames, side="left"):
    hip_i = L_HIP if side == "left" else R_HIP
    return [
        f[hip_i]["y"] for f in landmark_frames
        if f is not None and len(f) > hip_i
    ]
