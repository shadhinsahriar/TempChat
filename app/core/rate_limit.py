"""In-memory sliding-window rate limiter."""

import asyncio
import time
from collections import defaultdict

from app.core.exceptions import RateLimitExceededError


class SlidingWindowRateLimiter:
    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> None:
        """Enforce sliding window rate limit. Raise RateLimitExceededError if breached."""
        now = time.time()
        window_start = now - window_seconds

        async with self._lock:
            # Purge expired timestamps
            valid_timestamps = [t for t in self._requests[key] if t > window_start]
            if len(valid_timestamps) >= max_requests:
                raise RateLimitExceededError()

            valid_timestamps.append(now)
            self._requests[key] = valid_timestamps


rate_limiter = SlidingWindowRateLimiter()
