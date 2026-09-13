"""
Retry/backoff bookkeeping for the sync queue. Kept separate from
backend/services/sync_service.py (which owns DB reads/writes) so retry
policy can be unit-tested in isolation.
"""

MAX_ATTEMPTS = 5


def should_retry(item: dict) -> bool:
    return item.get("attempts", 0) < MAX_ATTEMPTS


def next_backoff_seconds(attempts: int) -> int:
    """Exponential backoff, capped at 1 hour."""
    return min(3600, 30 * (2 ** max(0, attempts)))
