"""Rate Limiter Module

Implements a token-bucket rate limiter with secure jitter, exponential
back-off, and CAPTCHA pause support.

Attributes:
    capacity: Maximum number of tokens in the bucket (default 5).
    refill_rate: Tokens added per interval (default 15 per minute).
    refill_interval_ms: Interval in milliseconds (default 60000).

Used by the Hunter sidecar to throttle requests to external portals and
avoid triggering anti-bot protections.
"""

import asyncio
import time
import os
import json
import logging
from typing import List, Callable

logger = logging.getLogger("hunter.rate_limiter")


class TokenBucketRateLimiter:
    """Async token-bucket rate limiter with jitter and back-off.

    Args:
        capacity: Max burst size.
        refill_rate: Tokens restored per refill interval.
        refill_interval_ms: Refill window in milliseconds.
    """

    def __init__(self, capacity: int = 5, refill_rate: int = 15, refill_interval_ms: int = 60000):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate
        self.refill_interval_ms = refill_interval_ms
        self.last_refill = time.time()
        self.current_backoff_ms = 0
        self.base_backoff_ms = 30000
        self.max_backoff_ms = 900000  # 15 minutes
        self.is_paused_for_captcha = False
        self.pending_requests: List[asyncio.Future] = []
        self._lock = asyncio.Lock()

    def _refill(self):
        """Refill tokens based on elapsed time since last refill."""
        now = time.time()
        elapsed_time_ms = (now - self.last_refill) * 1000.0

        if elapsed_time_ms >= self.refill_interval_ms:
            intervals = int(elapsed_time_ms // self.refill_interval_ms)
            self.tokens = min(float(self.capacity), self.tokens + intervals * self.refill_rate)
            self.last_refill = now - ((elapsed_time_ms % self.refill_interval_ms) / 1000.0)

    def _get_jitter(self, min_ms: int = 2000, max_ms: int = 8000) -> float:
        """Return a cryptographically-seeded random delay in seconds.

        Args:
            min_ms: Minimum jitter in milliseconds.
            max_ms: Maximum jitter in milliseconds.

        Returns:
            Jitter delay in seconds.
        """
        range_ms = max_ms - min_ms
        random_bytes = os.urandom(4)
        random_num = int.from_bytes(random_bytes, byteorder="little")
        random_float = random_num / 4294967296.0
        return (min_ms + int(random_float * range_ms)) / 1000.0

    async def acquire(self) -> None:
        """Acquire a token, blocking until one is available.

        Respects the ``SENTINEL_DEV_BYPASS_RATE_LIMIT`` env-var for
        development/testing.
        """
        if os.environ.get("SENTINEL_DEV_BYPASS_RATE_LIMIT") == "true":
            logger.warning("[WARN] Rate limit bypassed due to SENTINEL_DEV_BYPASS_RATE_LIMIT=true")
            return

        future = asyncio.get_running_loop().create_future()
        self.pending_requests.append(future)

        async def attempt_acquire():
            async with self._lock:
                if self.is_paused_for_captcha:
                    return False

                if self.current_backoff_ms > 0:
                    delay_sec = self.current_backoff_ms / 1000.0
                    self.current_backoff_ms = 0
                    await asyncio.sleep(delay_sec)

                self._refill()

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    jitter_sec = self._get_jitter()
                    await asyncio.sleep(jitter_sec)
                    return True
                else:
                    return False

        while not future.done():
            if self.is_paused_for_captcha:
                await asyncio.sleep(0.5)
                continue

            success = await attempt_acquire()
            if success:
                future.set_result(None)
                if future in self.pending_requests:
                    self.pending_requests.remove(future)
            else:
                now = time.time()
                elapsed_since_refill = (now - self.last_refill) * 1000.0
                time_until_refill_ms = self.refill_interval_ms - elapsed_since_refill
                sleep_sec = max(0.1, time_until_refill_ms / 1000.0)
                await asyncio.sleep(sleep_sec)

    def on_rate_limit(self):
        """Signal that an HTTP 429 was received; apply exponential back-off."""
        if self.current_backoff_ms == 0:
            self.current_backoff_ms = self.base_backoff_ms
        else:
            self.current_backoff_ms = min(self.current_backoff_ms * 2, self.max_backoff_ms)
        logger.warning(f"[WARN] Rate limit hit. Backing off for {self.current_backoff_ms}ms")

    def on_captcha(self, portal_id: str):
        """Pause all requests and emit an HITL event for CAPTCHA resolution."""
        self.is_paused_for_captcha = True
        print(json.dumps({
            "event": "hitl_required",
            "type": "captcha",
            "portalId": portal_id
        }), flush=True)

    def resume(self):
        """Resume request processing after CAPTCHA is solved."""
        self.is_paused_for_captcha = False
        logger.info("Rate limiter resumed from CAPTCHA state")
