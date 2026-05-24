import asyncio
import time
import random
import os
import json
from typing import List, Callable

class TokenBucketRateLimiter:
    def __init__(self, capacity: int = 5, refill_rate: int = 15, refill_interval_ms: int = 60_000):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate
        self.refill_interval_ms = refill_interval_ms / 1000.0  # Convert to seconds
        self.last_refill = time.time()
        self.current_backoff_s = 0.0
        self.base_backoff_s = 30.0
        self.max_backoff_s = 900.0  # 15 minutes
        self.is_paused_for_captcha = False
        self.pending_requests: List[asyncio.Future] = []
        self._lock = asyncio.Lock()

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        if elapsed >= self.refill_interval_ms:
            intervals = elapsed // self.refill_interval_ms
            new_tokens = intervals * self.refill_rate
            self.tokens = min(float(self.capacity), self.tokens + new_tokens)
            self.last_refill = now - (elapsed % self.refill_interval_ms)

    def _get_jitter(self, min_s: float = 2.0, max_s: float = 8.0) -> float:
        # Use random.SystemRandom for security/crypto-level randomness
        return random.SystemRandom().uniform(min_s, max_s)

    async def acquire(self):
        if os.getenv("SENTINEL_DEV_BYPASS_RATE_LIMIT") == "true":
            return

        async with self._lock:
            while True:
                if self.is_paused_for_captcha:
                    fut = asyncio.get_event_loop().create_future()
                    self.pending_requests.append(fut)
                    await fut
                    continue

                if self.current_backoff_s > 0:
                    delay = self.current_backoff_s
                    self.current_backoff_s = 0.0
                    await asyncio.sleep(delay)

                self._refill()

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    jitter = self._get_jitter()
                    await asyncio.sleep(jitter)
                    return
                else:
                    now = time.time()
                    time_until_refill = self.refill_interval_ms - (now - self.last_refill)
                    await asyncio.sleep(max(0.0, time_until_refill))

    def on_rate_limit(self):
        if self.current_backoff_s == 0:
            self.current_backoff_s = self.base_backoff_s
        else:
            self.current_backoff_s = min(self.current_backoff_s * 2, self.max_backoff_s)
        print(f"[WARN] Rate limit hit. Backing off for {self.current_backoff_s}s")

    def on_captcha(self, portal_id: str):
        self.is_paused_for_captcha = True
        print(json.dumps({
            "event": "hitl_required",
            "type": "captcha",
            "portal_id": portal_id
        }))

    def resume(self):
        self.is_paused_for_captcha = False
        for fut in self.pending_requests:
            if not fut.done():
                fut.set_result(None)
        self.pending_requests = []
