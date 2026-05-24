import asyncio
import time
import os
import json
import logging
from typing import List, Callable

logger = logging.getLogger("hunter.rate_limiter")

class TokenBucketRateLimiter:
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
        now = time.time()
        elapsed_time_ms = (now - self.last_refill) * 1000.0

        if elapsed_time_ms >= self.refill_interval_ms:
            intervals = int(elapsed_time_ms // self.refill_interval_ms)
            self.tokens = min(float(self.capacity), self.tokens + intervals * self.refill_rate)
            self.last_refill = now - ((elapsed_time_ms % self.refill_interval_ms) / 1000.0)

    def _get_jitter(self, min_ms: int = 2000, max_ms: int = 8000) -> float:
        # Secure random jitter using os.urandom per safety guidelines
        range_ms = max_ms - min_ms
        random_bytes = os.urandom(4)
        random_num = int.from_bytes(random_bytes, byteorder="little")
        random_float = random_num / 4294967296.0
        return (min_ms + int(random_float * range_ms)) / 1000.0

    async def acquire(self) -> None:
        # 1. Dev Bypass Check
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
                # Wait until resumed
                await asyncio.sleep(0.5)
                continue

            success = await attempt_acquire()
            if success:
                future.set_result(None)
                if future in self.pending_requests:
                    self.pending_requests.remove(future)
            else:
                # Wait for standard refill interval and check again
                now = time.time()
                elapsed_since_refill = (now - self.last_refill) * 1000.0
                time_until_refill_ms = self.refill_interval_ms - elapsed_since_refill
                sleep_sec = max(0.1, time_until_refill_ms / 1000.0)
                await asyncio.sleep(sleep_sec)

    def on_rate_limit(self):
        if self.current_backoff_ms == 0:
            self.current_backoff_ms = self.base_backoff_ms
        else:
            self.current_backoff_ms = min(self.current_backoff_ms * 2, self.max_backoff_ms)
        logger.warning(f"[WARN] Rate limit hit. Backing off for {self.current_backoff_ms}ms")

    def on_captcha(self, portal_id: str):
        self.is_paused_for_captcha = True
        print(json.dumps({
            "event": "hitl_required",
            "type": "captcha",
            "portalId": portal_id
        }), flush=True)

    def resume(self):
        self.is_paused_for_captcha = False
        logger.info("Rate limiter resumed from CAPTCHA state")
