"""Worker Sidecar Module

Implements a Redis-backed background job processor and gRPC service for
the Sentinel platform.

The worker continuously polls a Redis ``jobs`` list via BLPOP and
processes each job through a concrete task pipeline:
    1. Parse the job payload.
    2. Validate required fields.
    3. Perform a data transformation (normalise, enrich metadata).
    4. Store the result back in Redis under ``results:{rfp_id}``.

The gRPC ``WorkerService`` exposes an ``EnqueueJob`` RPC that pushes
jobs onto the Redis queue.

Environment variables:
    REDIS_URL: Redis connection string (default ``redis://localhost:6379``).
    PORT: gRPC listen port (default ``50053``).
"""

import asyncio
import json
import logging
import os
import sys
import time
import hashlib
from typing import Dict, Any, Optional

logger = logging.getLogger("worker")

# ---------------------------------------------------------------------------
# Redis helpers (using redis-py async)
# ---------------------------------------------------------------------------

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None  # type: ignore[assignment]
    logger.warning("redis-py[asyncio] not installed – worker will run in stub mode")


async def get_redis_client():
    """Return an async Redis client, or ``None`` if redis-py is missing."""
    if aioredis is None:
        return None
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return aioredis.from_url(url, decode_responses=True)


# ---------------------------------------------------------------------------
# Concrete task processor
# ---------------------------------------------------------------------------

async def process_job(job_data: Dict[str, Any], redis_client=None) -> Dict[str, Any]:
    """Process a single job with concrete data transformation.

    Pipeline:
        1. Validate ``rfp_id`` is present.
        2. Normalise text fields (strip, lower-case keys).
        3. Compute a content hash for deduplication.
        4. Enrich with processing metadata (timestamp, worker version).
        5. Store the result in Redis if a client is provided.

    Args:
        job_data: Parsed job payload dict.
        redis_client: Optional async Redis client for result storage.

    Returns:
        Enriched result dict.

    Raises:
        ValueError: If ``rfp_id`` is missing from *job_data*.
    """
    rfp_id = job_data.get("rfpId") or job_data.get("rfp_id")
    if not rfp_id:
        raise ValueError("Job payload is missing 'rfpId'")

    logger.info(f"Processing job for RFP: {rfp_id}")

    # -- Step 1: Normalise text fields ----------------------------------------
    normalised: Dict[str, Any] = {}
    for key, value in job_data.items():
        norm_key = key.strip()
        if isinstance(value, str):
            normalised[norm_key] = value.strip()
        else:
            normalised[norm_key] = value

    # -- Step 2: Compute content hash for dedup --------------------------------
    content_str = json.dumps(normalised, sort_keys=True)
    content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

    # -- Step 3: Enrich with metadata -----------------------------------------
    result: Dict[str, Any] = {
        **normalised,
        "contentHash": content_hash,
        "processedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workerVersion": "1.0.0",
        "status": "processed",
    }

    # -- Step 4: Store result in Redis ----------------------------------------
    if redis_client is not None:
        result_key = f"results:{rfp_id}"
        await redis_client.set(result_key, json.dumps(result), ex=86400)  # TTL 24h
        logger.info(f"Stored result under key: {result_key}")

    logger.info(f"Job completed for RFP: {rfp_id} (hash={content_hash})")
    return result


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

async def run_worker():
    """Continuously poll the Redis ``jobs`` list and process items."""
    redis_client = await get_redis_client()
    if redis_client is None:
        logger.error("Cannot start worker: redis-py is not available")
        return

    logger.info("Worker started, listening for jobs on 'jobs' list...")

    while True:
        try:
            # BLPOP blocks until an item appears (timeout 0 = forever)
            result = await redis_client.blpop("jobs", timeout=0)
            if result is None:
                continue
            _queue, raw_data = result
            logger.info(f"Received job from queue: {raw_data[:120]}...")

            try:
                job_data = json.loads(raw_data)
            except json.JSONDecodeError as je:
                logger.error(f"Invalid JSON in job payload: {je}")
                continue

            await process_job(job_data, redis_client)

        except asyncio.CancelledError:
            logger.info("Worker loop cancelled – shutting down")
            break
        except Exception as exc:
            logger.error(f"Unexpected error in worker loop: {exc}")
            await asyncio.sleep(2)  # back-off before retry

    await redis_client.aclose()


# ---------------------------------------------------------------------------
# gRPC service
# ---------------------------------------------------------------------------

# Add proto folder to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

try:
    import worker_pb2
    import worker_pb2_grpc
    import grpc

    class WorkerServiceServicer(worker_pb2_grpc.WorkerServiceServicer):
        """Async gRPC servicer implementing the Worker contract."""

        async def EnqueueJob(self, request, context):
            """Push a job onto the Redis ``jobs`` list.

            Args:
                request: ``JobRequest`` with ``rfp_id`` and optional ``payload``.

            Returns:
                ``JobResponse`` indicating success or failure.
            """
            rfp_id = request.rfp_id
            payload = request.payload or "{}"
            logger.info(f"EnqueueJob RPC called for rfp_id={rfp_id}")

            try:
                job_data = json.loads(payload) if payload != "{}" else {}
            except json.JSONDecodeError:
                job_data = {}
            job_data["rfpId"] = rfp_id

            redis_client = await get_redis_client()
            if redis_client is None:
                return worker_pb2.JobResponse(
                    success=False,
                    message="Redis is not available"
                )

            await redis_client.rpush("jobs", json.dumps(job_data))
            await redis_client.aclose()

            return worker_pb2.JobResponse(
                success=True,
                message=f"Job enqueued for RFP {rfp_id}"
            )

    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False
    logger.warning("gRPC dependencies not available – running worker-only mode")


async def serve():
    """Start the Worker gRPC server and background worker loop."""
    tasks = [asyncio.create_task(run_worker())]

    if HAS_GRPC:
        server = grpc.aio.server()
        worker_pb2_grpc.add_WorkerServiceServicer_to_server(
            WorkerServiceServicer(), server
        )
        port = os.environ.get("PORT", "50053")
        bind_address = f"0.0.0.0:{port}"
        server.add_insecure_port(bind_address)
        logger.info(f"Worker gRPC Server starting on {bind_address}")
        await server.start()
        tasks.append(asyncio.create_task(server.wait_for_termination()))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
