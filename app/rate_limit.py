"""
Simple in-memory sliding-window rate limiter.

Keyed on arbitrary strings (e.g. "create_round:42") so it is per-agent per-action.
Thread-safe via a single Lock; suitable for a single-process uvicorn deployment.
"""

from collections import defaultdict, deque
from threading import Lock
from time import time

from fastapi import HTTPException

_windows: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def reset() -> None:
    """Clear all rate-limit state. Intended for use in tests."""
    with _lock:
        _windows.clear()


def check_rate_limit(key: str, max_calls: int, window_seconds: int) -> None:
    """Raise HTTP 429 if *key* has been called ≥ max_calls times in the last window_seconds."""
    now = time()
    cutoff = now - window_seconds
    with _lock:
        dq = _windows[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= max_calls:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {max_calls} requests "
                    f"per {window_seconds}s for this action."
                ),
            )
        dq.append(now)
