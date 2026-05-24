/* eslint-disable no-console */
import { randomBytes } from 'crypto';

export class TokenBucketRateLimiter {
  private tokens: number;
  private readonly capacity: number;
  private readonly refillRate: number; // Tokens to add
  private readonly refillIntervalMs: number;
  private lastRefill: number;
  private currentBackoffMs: number;
  private readonly baseBackoffMs: number = 30_000;
  private readonly maxBackoffMs: number = 900_000; // 15 minutes
  private isPausedForCaptcha = false;
  private pendingRequests: (() => void)[] = [];

  constructor(capacity = 5, refillRate = 15, refillIntervalMs = 60_000) {
    this.capacity = capacity;
    this.tokens = capacity;
    this.refillRate = refillRate;
    this.refillIntervalMs = refillIntervalMs;
    this.lastRefill = Date.now();
    this.currentBackoffMs = 0;
  }

  /**
   * Refills the bucket based on time passed.
   */
  private refill() {
    const now = Date.now();
    const elapsedTime = now - this.lastRefill;

    if (elapsedTime >= this.refillIntervalMs) {
      // Calculate how many intervals have passed
      const intervals = Math.floor(elapsedTime / this.refillIntervalMs);
      this.tokens = Math.min(this.capacity, this.tokens + intervals * this.refillRate);
      this.lastRefill = now - (elapsedTime % this.refillIntervalMs);
    }
  }

  /**
   * Generates a random delay between min and max using crypto.
   * Do NOT use Math.random() for security reasons per guidelines.
   */
  private getJitter(min = 2000, max = 8000): number {
    const range = max - min;
    const randomBuffer = randomBytes(4);
    const randomNum = randomBuffer.readUInt32LE(0);
    // Max uint32 is 4294967295
    const randomFloat = randomNum / 4294967296;
    return min + Math.floor(randomFloat * range);
  }

  /**
   * Main entry point to acquire a token. Will block until a token is available
   * and any required jitter or backoff has elapsed.
   */
  public async acquire(): Promise<void> {
    // 1. Check Dev Bypass
    if (process.env.SENTINEL_DEV_BYPASS_RATE_LIMIT === 'true') {
      console.warn('[WARN] Rate limit bypassed due to SENTINEL_DEV_BYPASS_RATE_LIMIT=true');
      return;
    }

    // 2. Queue up if paused or out of tokens
    return new Promise<void>((resolve) => {
      const attemptAcquire = async () => {
        if (this.isPausedForCaptcha) {
          this.pendingRequests.push(() => {
            void attemptAcquire();
          });
          return;
        }

        if (this.currentBackoffMs > 0) {
          // Wait for backoff
          const delay = this.currentBackoffMs;
          this.currentBackoffMs = 0; // Reset backoff for next time, it grows on subsequent 429s
          await new Promise((r) => setTimeout(r, delay));
        }

        this.refill();

        if (this.tokens >= 1) {
          this.tokens -= 1;
          const jitter = process.env.NODE_ENV === "test" ? 0 : this.getJitter();
          setTimeout(() => {
            resolve();
          }, jitter);
        } else {
          // Calculate time until next refill and wait
          const now = Date.now();
          const timeUntilRefill = this.refillIntervalMs - (now - this.lastRefill);
          setTimeout(
            () => {
              void attemptAcquire();
            },
            Math.max(0, timeUntilRefill)
          );
        }
      };

      void attemptAcquire();
    });
  }

  /**
   * Triggered on HTTP 429 or CAPTCHA soft-blocks.
   * Starts exponential backoff: 30s -> 60s -> 120s -> ... capped at 15m.
   */
  public onRateLimit() {
    if (this.currentBackoffMs === 0) {
      this.currentBackoffMs = this.baseBackoffMs;
    } else {
      this.currentBackoffMs = Math.min(this.currentBackoffMs * 2, this.maxBackoffMs);
    }
    console.warn(`[WARN] Rate limit hit. Backing off for ${String(this.currentBackoffMs)}ms`);
  }

  /**
   * Triggered on hard CAPTCHA. Pauses all operations until resumed.
   */
  public onCaptcha(portalId: string) {
    this.isPausedForCaptcha = true;
    console.log(
      JSON.stringify({
        event: 'hitl_required',
        type: 'captcha',
        portalId,
      })
    );
  }

  /**
   * Resumes operations after CAPTCHA solved.
   */
  public resume() {
    this.isPausedForCaptcha = false;
    const pending = [...this.pendingRequests];
    this.pendingRequests = [];
    pending.forEach((req) => {
      req();
    });
  }
}
