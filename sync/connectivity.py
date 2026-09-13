"""Simple connectivity check used to decide whether to attempt a sync."""
import socket

from config.settings import Config


def is_online(timeout_s: float = 1.5) -> bool:
    if not Config.SYNC_ENDPOINT:
        return False
    try:
        host = (
            Config.SYNC_ENDPOINT.split("://", 1)[-1].split("/", 1)[0].split(":")[0]
        )
        socket.setdefaulttimeout(timeout_s)
        socket.gethostbyname(host)
        s = socket.create_connection((host, 443), timeout=timeout_s)
        s.close()
        return True
    except Exception:  # noqa: BLE001
        return False
