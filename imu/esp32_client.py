"""
Communication layer with an ESP32-C3 running dual-MPU6050 firmware.

Expected ESP32 firmware contract (simple JSON-over-HTTP, matching a typical
Arduino/ESP-IDF web-server sketch):

  GET  {ESP32_HOST}/status         -> {"left": "OK"|"ERROR", "right": "OK"|"ERROR"}
  POST {ESP32_HOST}/calibrate      -> {"success": true}
  POST {ESP32_HOST}/start          -> {"success": true}
  POST {ESP32_HOST}/stop           -> {"success": true}
  GET  {ESP32_HOST}/stream?n=200   -> {"left": [{...}], "right": [{...}]}
      each sample: {"t": <ms>, "ax":.., "ay":.., "az":.., "gx":.., "gy":.., "gz":..}

This module does not fabricate hardware behaviour: if ESP32_HOST is unset or
unreachable, callers must fall back to imu/sensor_manager.py's simulation
mode, which is clearly labelled as such throughout the app.
"""
import requests

from config.settings import Config
from backend.utils.logger import get_logger
from backend.utils.error_handler import DeviceUnavailableError

logger = get_logger(__name__)


class ESP32Client:
    def __init__(self, host: str = None, timeout: float = None):
        self.host = (host or Config.ESP32_HOST).rstrip("/")
        self.timeout = timeout or Config.ESP32_TIMEOUT_S

    def _ensure_configured(self):
        if not self.host:
            raise DeviceUnavailableError("ESP32 host not configured (JOINTX_ESP32_HOST)")

    def get_status(self) -> dict:
        self._ensure_configured()
        try:
            r = requests.get(f"{self.host}/status", timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logger.warning("ESP32 status check failed: %s", e)
            raise DeviceUnavailableError("Could not reach ESP32 device")

    def calibrate(self) -> bool:
        self._ensure_configured()
        try:
            r = requests.post(f"{self.host}/calibrate", timeout=self.timeout)
            r.raise_for_status()
            return bool(r.json().get("success"))
        except requests.RequestException as e:
            logger.warning("ESP32 calibration failed: %s", e)
            raise DeviceUnavailableError("IMU calibration failed — device unreachable")

    def start(self) -> bool:
        self._ensure_configured()
        try:
            r = requests.post(f"{self.host}/start", timeout=self.timeout)
            r.raise_for_status()
            return bool(r.json().get("success"))
        except requests.RequestException as e:
            logger.warning("ESP32 start failed: %s", e)
            raise DeviceUnavailableError("Could not start IMU capture")

    def stop(self) -> bool:
        self._ensure_configured()
        try:
            r = requests.post(f"{self.host}/stop", timeout=self.timeout)
            r.raise_for_status()
            return bool(r.json().get("success"))
        except requests.RequestException as e:
            logger.warning("ESP32 stop failed: %s", e)
            raise DeviceUnavailableError("Could not stop IMU capture")

    def read_stream(self, n_samples: int = 200) -> dict:
        self._ensure_configured()
        try:
            r = requests.get(f"{self.host}/stream", params={"n": n_samples}, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logger.warning("ESP32 stream read failed: %s", e)
            raise DeviceUnavailableError("Could not read IMU data")
