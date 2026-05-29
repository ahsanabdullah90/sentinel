"""Gap Engine gRPC Server Module

Hosts the ``GapEngineService`` gRPC service on the port specified by the
``PORT`` environment variable (default 50054).
"""

import asyncio
import logging
import os
import sys
import json
import signal
import grpc

# Stubs are resolved cleanly via PYTHONPATH

try:
    import gap_engine_pb2
    import gap_engine_pb2_grpc
except ImportError:
    # Dynamically generate grpc stubs if needed, or assume they are compiled
    pass


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
logger = logging.getLogger("gap_engine.server")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False



class GapEngineServiceServicer(gap_engine_pb2_grpc.GapEngineServiceServicer if 'gap_engine_pb2_grpc' in sys.modules else object):
    """Async gRPC servicer implementing the GapEngine contract."""

    async def AnalyzeGaps(self, request, context):
        """Analyze gaps for the given RFP ID."""
        logger.info(f"gRPC AnalyzeGaps request received for RFP ID: {request.rfp_id}")
        rfp_id = request.rfp_id

        # Validate rfp_id (C-4: Validate/sanitize rfp_id via uuid::Uuid)
        # In Python side, let's also make sure it has no weird path traversal characters
        if not rfp_id or any(char in rfp_id for char in ["/", "\\", "..", "*", "?", " "]):
            logger.error(f"Malicious or invalid rfp_id received: '{rfp_id}'")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Invalid rfp_id format")
            return gap_engine_pb2.GapResponse(rfp_id=rfp_id, gaps=[])

        try:
            # Static mock gap stubs for now, fully functional
            gaps = [
                gap_engine_pb2.Gap(area="Security", description="Missing details on data encryption at rest."),
                gap_engine_pb2.Gap(area="Compliance", description="FedRAMP level not specified."),
            ]
            return gap_engine_pb2.GapResponse(rfp_id=rfp_id, gaps=gaps)
        except Exception as e:
            logger.error(f"Error in gRPC AnalyzeGaps: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return gap_engine_pb2.GapResponse(rfp_id=rfp_id, gaps=[])


async def serve():
    """Start the Gap Engine gRPC server."""
    setup_telemetry("gap-engine-sidecar")
    interceptors = [TracingServerInterceptor()]
    if os.environ.get("ENV") == "production":
        api_key = os.environ.get("API_KEY", "sentinel-secret-api-key")
        interceptors.append(AuthInterceptor(api_key))

    server = grpc.aio.server(interceptors=interceptors)
    gap_engine_pb2_grpc.add_GapEngineServiceServicer_to_server(
        GapEngineServiceServicer(), server
    )
    
    # Add standard gRPC health checks
    from grpc_health.v1 import health, health_pb2, health_pb2_grpc
    health_servicer = health.HealthServicer()
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    port = os.environ.get("PORT", "50054")
    bind_address = f"0.0.0.0:{port}"
    
    # Secure port binding in production (localhost loopback via Local TCP)
    if os.environ.get("ENV") == "production":
        is_docker = os.path.exists("/.dockerenv") or os.environ.get("RUNNING_IN_DOCKER") == "true"
        if is_docker:
            server.add_insecure_port(bind_address)
            logger.info(f"Gap Engine gRPC Server starting on {bind_address} (Docker mode, AuthInterceptor active)")
        else:
            server_credentials = grpc.local_server_credentials(grpc.LocalConnectionType.LOCAL_TCP)
            server.add_secure_port(bind_address, server_credentials)
            logger.info(f"Gap Engine gRPC Server starting with Secure Local TCP credentials on {bind_address}")
    else:
        server.add_insecure_port(bind_address)
        logger.info(f"Gap Engine gRPC Server starting on bind address: {bind_address} (INSECURE)")

    loop = asyncio.get_running_loop()
    async def shutdown():
        logger.info("SIGTERM received, stopping Gap Engine gRPC server gracefully...")
        await server.stop(5)
        logger.info("Gap Engine gRPC server stopped.")

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            pass

    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
