import asyncio
import os
import json
import redis.asyncio as redis
from .scraper_engine import ScraperEngine
from .rate_limiter import TokenBucketRateLimiter

async def worker():
    r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    engine = ScraperEngine()
    limiters = {}

    print("Hunter worker started, waiting for jobs...")
    while True:
        try:
            # BLPOP blocks until a job is available in the 'hunter_jobs' queue
            job = await r.blpop("hunter_jobs", timeout=0)
            if job:
                _, payload_str = job
                payload = json.loads(payload_str)
                portal_id = payload.get("portal_id")
                config = payload.get("config", {})

                if portal_id not in limiters:
                    limiters[portal_id] = TokenBucketRateLimiter()

                print(f"Processing job for portal: {portal_id}")
                await engine.hunt(portal_id, config, limiters[portal_id])
        except Exception as e:
            print(f"Worker error: {e}")
            await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(worker())
