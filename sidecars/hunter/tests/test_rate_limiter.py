import pytest
import os
import time
import asyncio
from src_py.rate_limiter import TokenBucketRateLimiter

@pytest.mark.asyncio
async def test_rate_limiter_bypass():
    os.environ["SENTINEL_DEV_BYPASS_RATE_LIMIT"] = "true"
    limiter = TokenBucketRateLimiter(capacity=1, refill_rate=1, refill_interval_ms=60000)
    limiter.tokens = 0
    start = time.time()
    await limiter.acquire()
    assert time.time() - start < 1.0
    del os.environ["SENTINEL_DEV_BYPASS_RATE_LIMIT"]

@pytest.mark.asyncio
async def test_rate_limiter_backoff():
    limiter = TokenBucketRateLimiter()
    assert limiter.current_backoff_ms == 0
    limiter.on_rate_limit()
    assert limiter.current_backoff_ms == 30000
    limiter.on_rate_limit()
    assert limiter.current_backoff_ms == 60000

@pytest.mark.asyncio
async def test_rate_limiter_captcha(capsys):
    limiter = TokenBucketRateLimiter()
    limiter.on_captcha("test-portal")
    assert limiter.is_paused_for_captcha is True
    out, err = capsys.readouterr()
    assert "hitl_required" in out
    limiter.resume()
    assert limiter.is_paused_for_captcha is False
