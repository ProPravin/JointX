"""
Actual network transmission for store-and-forward sync. Isolated from the
backend service layer so it can be swapped out (e.g. for a real government
health-system API integration) without touching queue/DB logic.

No real government API integration is implemented here (spec section 26) --
this posts to a configurable generic endpoint (JOINTX_SYNC_ENDPOINT) as a
placeholder for wherever this deployment ultimately needs to send data.
"""
import requests

from config.settings import Config
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def push_batch(item: dict):
    """Returns (success: bool, error_message_or_None)."""
    if not Config.SYNC_ENDPOINT:
        return False, "Sync endpoint not configured"

    headers = {"Content-Type": "application/json"}
    if Config.SYNC_API_KEY:
        headers["Authorization"] = f"Bearer {Config.SYNC_API_KEY}"

    try:
        resp = requests.post(
            Config.SYNC_ENDPOINT,
            data=item["payload_json"],
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return True, None
    except requests.RequestException as e:
        logger.warning("Sync push failed for queue item %s: %s", item.get("id"), e)
        return False, str(e)
