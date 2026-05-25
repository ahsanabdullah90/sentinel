"""Tests for the Hunter rate_limiter module."""

import asyncio
import os
import time
import pytest

# We import relative to project root; conftest.py adds paths
from sidecars.hunter.src_py.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    """Unit tests for TokenBucketRateLimiter."""

    def test_initial_tokens(self):
        """Limiter should start with full capacity."""
        rl = TokenBucketRateLimiter(capacity=5, refill_rate=15, refill_interval_ms=60000)
        assert rl.tokens == 5.0
        assert rl.capacity == 5
        assert rl.is_paused_for_captcha is False

    def test_refill_no_time_elapsed(self):
        """Calling _refill immediately should not add tokens."""
        rl = TokenBucketRateLimiter(capacity=5)
        rl.tokens = 0.0
        rl._refill()
        assert rl.tokens == 0.0

    def test_refill_after_interval(self):
        """Calling _refill after one full interval should restore tokens."""
        rl = TokenBucketRateLimiter(capacity=5, refill_rate=3, refill_interval_ms=1000)
        rl.tokens = 0.0
        rl.last_refill = time.time() - 1.5  # 1.5 seconds ago (1 full interval)
        rl._refill()
        assert rl.tokens == 3.0  # 1 interval * refill_rate=3

    def test_refill_capped_at_capacity(self):
        """Tokens should never exceed capacity."""
        rl = TokenBucketRateLimiter(capacity=5, refill_rate=100, refill_interval_ms=1000)
        rl.tokens = 4.0
        rl.last_refill = time.time() - 2.0
        rl._refill()
        assert rl.tokens == 5.0

    def test_jitter_range(self):
        """Jitter should fall within the specified range."""
        rl = TokenBucketRateLimiter()
        for _ in range(50):
            jitter = rl._get_jitter(min_ms=1000, max_ms=2000)
            assert 1.0 <= jitter <= 2.0

    def test_on_rate_limit_initial(self):
        """First rate limit should set backoff to base."""
        rl = TokenBucketRateLimiter()
        rl.on_rate_limit()
        assert rl.current_backoff_ms == rl.base_backoff_ms

    def test_on_rate_limit_exponential(self):
        """Subsequent rate limits should double the backoff."""
        rl = TokenBucketRateLimiter()
        rl.on_rate_limit()
        first = rl.current_backoff_ms
        rl.on_rate_limit()
        assert rl.current_backoff_ms == first * 2

    def test_on_rate_limit_max(self):
        """Backoff should not exceed max_backoff_ms."""
        rl = TokenBucketRateLimiter()
        for _ in range(20):
            rl.on_rate_limit()
        assert rl.current_backoff_ms <= rl.max_backoff_ms

    def test_on_captcha_pauses(self):
        """on_captcha should set is_paused_for_captcha."""
        rl = TokenBucketRateLimiter()
        rl.on_captcha("test-portal")
        assert rl.is_paused_for_captcha is True

    def test_resume(self):
        """resume should unset is_paused_for_captcha."""
        rl = TokenBucketRateLimiter()
        rl.on_captcha("test-portal")
        rl.resume()
        assert rl.is_paused_for_captcha is False

    @pytest.mark.asyncio
    async def test_acquire_bypass(self):
        """Acquire should return immediately when dev bypass is set."""
        os.environ["SENTINEL_DEV_BYPASS_RATE_LIMIT"] = "true"
        try:
            rl = TokenBucketRateLimiter(capacity=1)
            rl.tokens = 0.0  # No tokens available
            await rl.acquire()  # Should still succeed due to bypass
        finally:
            os.environ.pop("SENTINEL_DEV_BYPASS_RATE_LIMIT", None)

    @pytest.mark.asyncio
    async def test_acquire_consumes_token(self):
        """Acquire should consume one token."""
        os.environ["SENTINEL_DEV_BYPASS_RATE_LIMIT"] = "true"
        try:
            rl = TokenBucketRateLimiter(capacity=5)
            start_tokens = rl.tokens
            await rl.acquire()
            # With bypass, tokens are NOT consumed
            assert rl.tokens == start_tokens
        finally:
            os.environ.pop("SENTINEL_DEV_BYPASS_RATE_LIMIT", None)
