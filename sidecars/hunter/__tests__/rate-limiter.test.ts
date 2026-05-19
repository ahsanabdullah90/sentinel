import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { TokenBucketRateLimiter } from '../src/rate-limiter.js';

describe('TokenBucketRateLimiter', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('initializes with full capacity', async () => {
    const limiter = new TokenBucketRateLimiter(5, 15, 60000);
    let acquired = false;

    // Acquire without waiting for timers should pass if we don't count jitter
    // We can mock getJitter or just advance timers slightly
    const acquirePromise = limiter.acquire().then(() => (acquired = true));

    // Jitter is between 2000-8000ms
    vi.advanceTimersByTime(8000);
    await acquirePromise;

    expect(acquired).toBe(true);
  });

  it('blocks when capacity is exhausted', async () => {
    const limiter = new TokenBucketRateLimiter(2, 1, 60000); // 2 capacity

    let acquiredCount = 0;
    const acquire1 = limiter.acquire().then(() => acquiredCount++);
    const acquire2 = limiter.acquire().then(() => acquiredCount++);
    const acquire3 = limiter.acquire().then(() => acquiredCount++);

    vi.advanceTimersByTime(8000); // clear jitter
    await Promise.all([acquire1, acquire2]);
    expect(acquiredCount).toBe(2);

    // third should still be waiting
    vi.advanceTimersByTime(10000);
    expect(acquiredCount).toBe(2);

    // after 60s, it refills 1 token
    vi.advanceTimersByTime(60000);
    await acquire3;
    expect(acquiredCount).toBe(3);
  });

  it('backs off exponentially on rate limit', async () => {
    const limiter = new TokenBucketRateLimiter(5, 15, 60000);

    limiter.onRateLimit(); // 30s backoff

    let acquired = false;
    const acquirePromise = limiter.acquire().then(() => (acquired = true));

    vi.advanceTimersByTime(10000);
    expect(acquired).toBe(false);

    vi.advanceTimersByTime(20000); // 30s total
    vi.advanceTimersByTime(8000); // jitter

    await acquirePromise;
    expect(acquired).toBe(true);
  });

  it('pauses entirely on CAPTCHA and resumes', async () => {
    const limiter = new TokenBucketRateLimiter(5, 15, 60000);

    limiter.onCaptcha('test_portal');

    let acquired = false;
    const acquirePromise = limiter.acquire().then(() => (acquired = true));

    vi.advanceTimersByTime(100000); // Lots of time
    expect(acquired).toBe(false); // Still paused

    limiter.resume();
    vi.advanceTimersByTime(8000); // Jitter

    await acquirePromise;
    expect(acquired).toBe(true);
  });
});
