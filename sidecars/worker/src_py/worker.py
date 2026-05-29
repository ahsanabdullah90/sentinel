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
import signal
import hashlib
from typing import Dict, Any, Optional

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage()
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def setup_telemetry(service_name: str):
    """Bootstrap OpenTelemetry Tracing to OTLP collector."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        
        resource = Resource.create(attributes={"service.name": service_name})
        provider = TracerProvider(resource=resource)
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        span_processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(span_processor)
        trace.set_tracer_provider(provider)
        logger.info(f"OpenTelemetry tracing initialized for service: {service_name} pointing to {otlp_endpoint}")
    except Exception as e:
        logger.warning(f"OpenTelemetry tracing could not be initialized (running without distributed tracing): {str(e)}")


class TracingServerInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer("sentinel.grpc")
            method = handler_call_details.method
            with tracer.start_as_current_span(f"gRPC {method}") as span:
                span.set_attribute("rpc.system", "grpc")
                span.set_attribute("rpc.method", method)
                return await continuation(handler_call_details)
        except Exception:
            return await continuation(handler_call_details)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("worker")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False


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
            result = await redis_client.blpop("jobs", timeout=1)
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

    class AuthInterceptor(grpc.aio.ServerInterceptor):
        def __init__(self, expected_token: str):
            self._expected_token = expected_token

        async def intercept_service(self, continuation, handler_call_details):
            if os.environ.get("ENV") == "production":
                metadata = dict(handler_call_details.invocation_metadata)
                token = metadata.get("x-sentinel-token") or metadata.get("authorization")
                if token != self._expected_token:
                    async def abort_call(request, context):
                        await context.abort(
                            grpc.StatusCode.UNAUTHENTICATED,
                            "Missing or invalid Sentinel API token"
                        )
                    return grpc.unary_unary_rpc_method_handler(abort_call)
            return await continuation(handler_call_details)

    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False
    logger.warning("gRPC dependencies not available – running worker-only mode")


async def serve():
    """Start the Worker gRPC server and background worker loop."""
    setup_telemetry("worker-sidecar")
    worker_task = asyncio.create_task(run_worker())
    tasks = [worker_task]
    server = None

    if HAS_GRPC:
        interceptors = [TracingServerInterceptor()]
        if os.environ.get("ENV") == "production":
            api_key = os.environ.get("API_KEY", "sentinel-secret-api-key")
            interceptors.append(AuthInterceptor(api_key))

        server = grpc.aio.server(interceptors=interceptors)
        worker_pb2_grpc.add_WorkerServiceServicer_to_server(
            WorkerServiceServicer(), server
        )
        
        # Add standard gRPC health checks
        from grpc_health.v1 import health, health_pb2, health_pb2_grpc
        health_servicer = health.HealthServicer()
        health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
        health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

        port = os.environ.get("PORT", "50053")
        bind_address = f"0.0.0.0:{port}"
        
        # Secure port binding in production (localhost loopback via Local TCP)
        if os.environ.get("ENV") == "production":
            server_credentials = grpc.local_server_credentials(grpc.LocalConnectionType.LOCAL_TCP)
            server.add_secure_port(bind_address, server_credentials)
            logger.info(f"Worker gRPC Server starting with Secure Local TCP credentials on {bind_address}")
        else:
            server.add_insecure_port(bind_address)
            logger.info(f"Worker gRPC Server starting on bind address: {bind_address} (INSECURE)")

        await server.start()
        tasks.append(asyncio.create_task(server.wait_for_termination()))

    loop = asyncio.get_running_loop()
    async def shutdown():
        logger.info("SIGTERM received, stopping Worker gracefully...")
        # Cancel worker task
        worker_task.cancel()
        if server:
            await server.stop(5)
        logger.info("Worker gracefully stopped.")

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            pass

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    asyncio.run(serve())
