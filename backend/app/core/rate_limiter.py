"""
Production sliding-window Rate Limiter backed by Redis with thread-safe in-memory fallback.
"""
import asyncio
import time
from collections import deque
from typing import Deque, Dict, Tuple

from app.core.config import settings
from app.core.database import cache


class SlidingWindowRateLimiter:
    """Sliding-window per-key rate limiter with Redis support and local fallback."""

    def __init__(self) -> None:
        self._buckets: Dict[str, Deque[float]] = {}
        self._lock = asyncio.Lock()

    def reset(self) -> None:
        """Clear local in-memory rate limit buckets (useful between isolated tests)."""
        self._buckets.clear()

    async def check(
        self,
        bucket_key: str,
        limit_rpm: int,
        window_seconds: int = 60,
    ) -> Tuple[bool, int, int]:
        """
        Check and consume 1 request token for `bucket_key`.
        Returns (allowed, remaining, reset_seconds).
        """
        if not settings.RATE_LIMIT_ENABLED or limit_rpm <= 0:
            return True, max(1, limit_rpm), window_seconds

        now = time.time()

        # 1. Prefer Redis when available for distributed multi-worker enforcement
        if cache._redis is not None:
            try:
                window_slot = int(now // window_seconds)
                redis_key = f"nexora:rl:{bucket_key}:{window_slot}"
                current_count = await cache._redis.incr(redis_key)
                if current_count == 1:
                    await cache._redis.expire(redis_key, window_seconds + 2)
                remaining = max(0, limit_rpm - int(current_count))
                reset_sec = max(1, window_seconds - int(now % window_seconds))
                if int(current_count) > limit_rpm:
                    return False, 0, reset_sec
                return True, remaining, reset_sec
            except Exception:
                pass

        # 2. Local async lock sliding window fallback
        cutoff = now - window_seconds
        async with self._lock:
            dq = self._buckets.get(bucket_key)
            if dq is None:
                dq = deque()
                self._buckets[bucket_key] = dq

            while dq and dq[0] <= cutoff:
                dq.popleft()

            if len(dq) >= limit_rpm:
                oldest = dq[0]
                reset_sec = max(1, int(window_seconds - (now - oldest)))
                return False, 0, reset_sec

            dq.append(now)
            remaining = max(0, limit_rpm - len(dq))
            return True, remaining, window_seconds


rate_limiter = SlidingWindowRateLimiter()
