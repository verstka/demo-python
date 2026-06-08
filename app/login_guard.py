"""In-memory brute-force protection for CMS login (per user email).

IP-based limiting is handled by nginx (see staff/nginx.conf).
"""

from __future__ import annotations

import time

from app.config import Settings

_failures: dict[str, list[float]] = {}


def reset_login_failures() -> None:
    """Clear in-memory counters (for tests)."""
    _failures.clear()


def _prune(timestamps: list[float], window_seconds: int, now: float) -> list[float]:
    cutoff = now - window_seconds
    return [t for t in timestamps if t >= cutoff]


def _failure_count(user_email: str, window_seconds: int, now: float) -> int:
    timestamps = _prune(_failures.get(user_email, []), window_seconds, now)
    _failures[user_email] = timestamps
    return len(timestamps)


def is_user_login_blocked(settings: Settings, user_email: str) -> bool:
    now = time.time()
    count = _failure_count(user_email, settings.cms_login_window_seconds, now)
    return count >= settings.cms_login_max_failures


def record_user_login_failure(settings: Settings, user_email: str) -> None:
    now = time.time()
    window = settings.cms_login_window_seconds
    timestamps = _prune(_failures.get(user_email, []), window, now)
    timestamps.append(now)
    _failures[user_email] = timestamps


def clear_user_login_failures(user_email: str) -> None:
    _failures.pop(user_email, None)
