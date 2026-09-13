from computer_vision.feature_extraction import extract_gait_features
from computer_vision.preprocessing import assess_pose_data_quality


def _make_frame(x=0.5, y=0.5, visibility=0.9):
    return [{"x": x, "y": y + i * 0.001, "z": 0.0, "visibility": visibility} for i in range(33)]


def test_poor_quality_data_flagged():
    frames = [None] * 40
    visibilities = [0.1] * 40
    result = extract_gait_features(frames, visibilities)
    assert result["data_quality_ok"] is False
    assert "Insufficient gait data" in result["quality_message"]


def test_good_quality_produces_features():
    frames = [_make_frame() for _ in range(60)]
    visibilities = [0.9] * 60
    result = extract_gait_features(frames, visibilities)
    assert result["data_quality_ok"] is True
    assert "cadence" in result
    assert "left_right_asymmetry" in result
    assert "stride_time" in result
    assert "stance_swing_ratio" in result
    assert "gait_cycle_variability" in result


def test_assess_pose_data_quality_frame_count():
    ok, reason, vis, frames = assess_pose_data_quality([None] * 5, [0.9] * 5)
    assert ok is False
