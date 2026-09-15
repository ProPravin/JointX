"""Simple connectivity check used to decide whether to attempt a sync."""
import socket
from urllib.parse import urlparse

from config.settings import Config


def is_online(timeout_s: float = 1.5) -> bool:
    if not Config.SYNC_ENDPOINT:
        return False
    try:
        parsed = urlparse(Config.SYNC_ENDPOINT)
        host = parsed.hostname
        # Actually use the endpoint's own port/scheme rather than assuming
        # HTTPS/443 -- a central server on plain HTTP (e.g. central_server/app.py
        # during local testing) or a non-default port was always reported
        # "offline" before this fix, since a bare-443 probe against it fails
        # even though the endpoint is perfectly reachable.
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        socket.setdefaulttimeout(timeout_s)
        socket.gethostbyname(host)
        s = socket.create_connection((host, port), timeout=timeout_s)
        s.close()
        return True
    except Exception:  # noqa: BLE001
        return False
