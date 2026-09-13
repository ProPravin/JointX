"""
Unified interface the rest of the app talks to for IMU acquisition:
START IMU / STOP IMU / READ IMU STATUS / RECEIVE SENSOR DATA / CALIBRATE.

Wraps imu/esp32_client.py for real hardware, and falls back to a clearly
labelled simulator (is_demo=True) when JOINTX_DEMO_MODE is on or the ESP32
is unreachable. Both paths return data in the exact same shape so
imu/feature_extraction.py never needs to know which one ran (spec section 21).
"""
import math
import random
import time

from config.settings import Config
from imu.esp32_client import ESP32Client
from backend.utils.error_handler import DeviceUnavailableError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _simulate_stream(n_samples: int, seed_offset: float = 0.0, noisy: bool = False):
    """
    Generates a plausible-looking accel/gyro stream for a lower-limb during
    walking: a roughly periodic signal with some noise. This is NOT real
    sensor data and is always tagged is_demo=True by the caller.
    """
    samples = []
    for i in range(n_samples):
        t = i * 10  # ms, ~100Hz
        phase = (i / n_samples) * 4 * math.pi + seed_offset
        noise = random.uniform(-0.3, 0.3) if not noisy else random.uniform(-1.0, 1.0)
        samples.append(
            {
                "t": t,
                "ax": round(0.8 * math.sin(phase) + noise, 3),
                "ay": round(0.3 * math.cos(phase) + noise, 3),
                "az": round(9.8 + 0.2 * math.sin(phase * 2) + noise, 3),
                "gx": round(40 * math.sin(phase) + noise * 5, 2),
                "gy": round(15 * math.cos(phase * 1.5) + noise * 3, 2),
                "gz": round(10 * math.sin(phase * 0.5) + noise * 2, 2),
            }
        )
    return samples


class IMUSensorManager:
    def __init__(self, force_demo: bool = None):
        self.force_demo = Config.DEMO_MODE if force_demo is None else force_demo
        self.client = ESP32Client()

    def get_status(self) -> dict:
        if not self.force_demo:
            try:
                status = self.client.get_status()
                return {"is_demo": False, "left": status.get("left", "UNKNOWN"),
                        "right": status.get("right", "UNKNOWN")}
            except DeviceUnavailableError as e:
                logger.info("Falling back to simulated IMU status: %s", e.message)
        return {"is_demo": True, "left": "SIMULATED", "right": "SIMULATED"}

    def calibrate(self) -> dict:
        if not self.force_demo:
            try:
                ok = self.client.calibrate()
                return {"is_demo": False, "success": ok}
            except DeviceUnavailableError as e:
                logger.info("Falling back to simulated IMU calibration: %s", e.message)
        time.sleep(0.2)  # simulate calibration delay
        return {"is_demo": True, "success": True}

    def start(self) -> dict:
        if not self.force_demo:
            try:
                ok = self.client.start()
                return {"is_demo": False, "success": ok}
            except DeviceUnavailableError as e:
                logger.info("Falling back to simulated IMU start: %s", e.message)
        return {"is_demo": True, "success": True}

    def stop(self) -> dict:
        if not self.force_demo:
            try:
                ok = self.client.stop()
                return {"is_demo": False, "success": ok}
            except DeviceUnavailableError as e:
                logger.info("Falling back to simulated IMU stop: %s", e.message)
        return {"is_demo": True, "success": True}

    def read_movement_test(self, n_samples: int = 200) -> dict:
        """Returns {'is_demo': bool, 'left': [...samples...], 'right': [...samples...]}"""
        if not self.force_demo:
            try:
                data = self.client.read_stream(n_samples)
                return {"is_demo": False, "left": data.get("left", []), "right": data.get("right", [])}
            except DeviceUnavailableError as e:
                logger.info("Falling back to simulated IMU stream: %s", e.message)

        return {
            "is_demo": True,
            "left": _simulate_stream(n_samples, seed_offset=0.0),
            "right": _simulate_stream(n_samples, seed_offset=math.pi),  # opposite phase = normal gait
        }
