"""Hunter gRPC Server Module

Hosts the ``HunterService`` gRPC service on the port specified by the
``PORT`` environment variable (default 50051).
"""

import asyncio
import logging
import os
import sys
import json
import signal
import grpc



import hunter_pb2
import hunter_pb2_grpc

from sidecars.hunter.src_py.portal_analyzer import analyze_portal
from sidecars.hunter.src_py.portal_runner import PortalRunner
from sidecars.hunter.src_py.models import PortalConfig


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
logger = logging.getLogger("hunter.server")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False



class HunterServiceServicer(hunter_pb2_grpc.HunterServiceServicer):
    """Async gRPC servicer implementing the Hunter contract."""

    async def Detect(self, request, context):
        """Analyse the portal at *request.url* and stream back a detection report."""
        logger.info(f"gRPC Detect request received for URL: {request.url}")
        
        # Setup event queue to buffer events generated in sub-tasks
        event_queue = asyncio.Queue()

        async def on_event(event_name: str, payload: dict):
            await event_queue.put((event_name, payload))

        async def run_analysis():
            try:
                report = await analyze_portal(request.url)
                await event_queue.put(("portal_detected", report))
            except Exception as e:
                logger.error(f"Error in analyze_portal: {str(e)}")
                await event_queue.put(("error", {"message": str(e)}))
            finally:
                # Put None to signal completion
                await event_queue.put(None)

        # Spawn the analysis in the background
        analysis_task = asyncio.create_task(run_analysis())

        try:
            while True:
                # Check if client has cancelled the RPC stream
                if context.cancelled():
                    logger.warning("gRPC Detect client disconnected. Cancelling analysis...")
                    analysis_task.cancel()
                    break

                try:
                    # Non-blocking poll with timeout to check context activity frequently
                    item = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    if item is None:
                        break
                    
                    event_name, payload = item
                    yield hunter_pb2.DetectResponse(
                        event=event_name,
                        json_payload=json.dumps(payload),
                        payload_type=hunter_pb2.PayloadType.JSON
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.warning("gRPC Detect RPC cancelled by host. Terminating.")
            analysis_task.cancel()
            raise
        finally:
            await analysis_task

    async def Hunt(self, request, context):
        """Run a scraping job for *request.portal_id* and yield results in real-time."""
        logger.info(f"gRPC Hunt request received for Portal ID: {request.portal_id}")
        portal_id = request.portal_id

        # Setup standard fallback config
        raw_config = {
            "id": portal_id,
            "name": "Target Portal",
            "baseUrl": "https://example.com",
            "authMethod": "public",
            "scraperModule": "generic_search",
            "activeWindowStart": "00:00",
            "activeWindowEnd": "23:59",
            "requestsPerMinute": 15
        }

        # Override defaults if mock_config_json (standard configuration payload) is provided
        if request.mock_config_json:
            try:
                parsed = json.loads(request.mock_config_json)
                if parsed:
                    # Normalize field names to match PortalConfig model requirements
                    if "url" in parsed and parsed["url"]:
                        parsed["baseUrl"] = parsed["url"]
                    if "base_url" in parsed and parsed["base_url"]:
                        parsed["baseUrl"] = parsed["base_url"]
                    
                    if "scraper_module" in parsed and parsed["scraper_module"]:
                        parsed["scraperModule"] = parsed["scraper_module"]
                    elif "rendering_mode" in parsed and parsed["rendering_mode"]:
                        # Map rendering mode (e.g. 'Browser (Playwright)' or 'Static HTML') to generic search
                        parsed["scraperModule"] = "generic_search"
                    
                    raw_config.update(parsed)
            except Exception as pe:
                logger.warning(f"Failed to parse config JSON: {str(pe)}, using fallbacks")

        try:
            # Validate input using Pydantic
            config = PortalConfig.model_validate(raw_config)
        except Exception as ve:
            logger.error(f"Config validation error: {str(ve)}")
            yield hunter_pb2.HuntResponse(
                event="error",
                json_payload=json.dumps({"message": f"Configuration validation failed: {str(ve)}"}),
                payload_type=hunter_pb2.PayloadType.JSON
            )
            return

        # Setup event queue to translate callbacks into streamed yields
        event_queue = asyncio.Queue()

        async def on_event(event_name: str, payload: dict):
            await event_queue.put((event_name, payload))

        async def run_hunt():
            runner = PortalRunner()
            try:
                await runner.run_portal(config, on_event=on_event)
                await event_queue.put(("hunt_complete", {"success": True}))
            except Exception as e:
                logger.error(f"Error executing hunt: {str(e)}")
                await event_queue.put(("error", {"message": str(e)}))
            finally:
                # Signal completion
                await event_queue.put(None)

        # Run hunt in a background task
        hunt_task = asyncio.create_task(run_hunt())

        try:
            while True:
                # Check if client dropped the stream
                if context.cancelled():
                    logger.warning("gRPC Hunt client disconnected. Cancelling hunt...")
                    hunt_task.cancel()
                    break

                try:
                    item = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    if item is None:
                        break

                    event_name, payload = item
                    yield hunter_pb2.HuntResponse(
                        event=event_name,
                        json_payload=json.dumps(payload),
                        payload_type=hunter_pb2.PayloadType.JSON
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.warning("gRPC Hunt RPC cancelled by host. Terminating.")
            hunt_task.cancel()
            raise
        finally:
            await hunt_task


async def serve():
    """Start the Hunter gRPC server."""
    setup_telemetry("hunter-sidecar")
    interceptors = [TracingServerInterceptor()]
    if os.environ.get("ENV") == "production":
        api_key = os.environ.get("API_KEY", "sentinel-secret-api-key")
        interceptors.append(AuthInterceptor(api_key))

    server = grpc.aio.server(interceptors=interceptors)
    hunter_pb2_grpc.add_HunterServiceServicer_to_server(
        HunterServiceServicer(), server
    )
    
    # Add standard gRPC health checks
    from grpc_health.v1 import health, health_pb2, health_pb2_grpc
    health_servicer = health.HealthServicer()
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    port = os.environ.get("PORT", "50051")
    host = "0.0.0.0" if os.environ.get("RUNNING_IN_DOCKER") == "true" else "127.0.0.1"
    bind_address = f"{host}:{port}"
    
    # Secure port binding in production (localhost loopback via Local TCP) unless running inside Docker
    if os.environ.get("ENV") == "production" and os.environ.get("RUNNING_IN_DOCKER") != "true":
        server_credentials = grpc.local_server_credentials(grpc.LocalConnectionType.LOCAL_TCP)
        server.add_secure_port(bind_address, server_credentials)
        logger.info(f"Hunter gRPC Server starting with Secure Local TCP credentials on {bind_address}")
    else:
        server.add_insecure_port(bind_address)
        logger.info(f"Hunter gRPC Server starting on bind address: {bind_address} (INSECURE)")

    loop = asyncio.get_running_loop()
    async def shutdown():
        logger.info("SIGTERM received, stopping Hunter gRPC server gracefully...")
        await server.stop(5)
        logger.info("Hunter gRPC server stopped.")

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            # Handle platform limitations (e.g. Windows)
            pass

    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
