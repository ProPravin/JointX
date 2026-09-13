from imu.feature_extraction import extract_imu_features
from imu.calibration import compute_bias, apply_bias
from imu.sensor_manager import IMUSensorManager


def _sample(ax=0.1, gx=10):
    return {"t": 0, "ax": ax, "ay": 0.0, "az": 9.8, "gx": gx, "gy": 0.0, "gz": 0.0}


def test_insufficient_imu_data_flagged():
    left = [_sample() for _ in range(5)]
    right = [_sample() for _ in range(5)]
    result = extract_imu_features(left, right)
    assert result["data_quality_ok"] is False


def test_sufficient_imu_data_produces_features():
    left = [_sample(ax=0.1 * i % 1, gx=10 + i) for i in range(60)]
    right = [_sample(ax=0.1 * i % 1, gx=10 + i) for i in range(60)]
    result = extract_imu_features(left, right)
    assert result["data_quality_ok"] is True
    assert "acceleration_rms" in result
    assert "angular_velocity_rms" in result
    assert "relative_joint_rom" in result
    assert "movement_smoothness" in result
    assert "movement_cycle_duration" in result


def test_calibration_bias_applied():
    still = [_sample(ax=1.0, gx=5.0) for _ in range(10)]
    bias = compute_bias(still)
    corrected = apply_bias(still, bias)
    assert abs(corrected[0]["ax"]) < 1e-9
    assert abs(corrected[0]["gx"]) < 1e-9


def test_sensor_manager_demo_mode_returns_data():
    manager = IMUSensorManager(force_demo=True)
    status = manager.get_status()
    assert status["is_demo"] is True
    stream = manager.read_movement_test(n_samples=50)
    assert stream["is_demo"] is True
    assert len(stream["left"]) == 50
    assert len(stream["right"]) == 50
