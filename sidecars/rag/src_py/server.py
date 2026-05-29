"""RAG gRPC Server Module

Hosts the ``RagService`` gRPC service on the port specified by the
``PORT`` environment variable (default 50052).

RPCs:
    * ``Ingest`` – accept a document, chunk it, and store embeddings.
    * ``Query``  – retrieve relevant context and generate an answer
      via Ollama.
"""

import asyncio
import logging
import os
import sys
import json
import signal
import grpc



import rag_pb2
import rag_pb2_grpc

from .ingest import ingest_document
from .ollama_client import OllamaClient
from .chroma_client import ChromaClient


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
logger = logging.getLogger("rag.server")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False



class RagServiceServicer(rag_pb2_grpc.RagServiceServicer):
    """Async gRPC servicer implementing the RAG contract."""

    async def Ingest(self, request, context):
        """Ingest *request.content* under *request.document_id*."""
        logger.info(f"gRPC Ingest request received for document: {request.document_id}")
        import tempfile
        document_id = request.document_id
        content = request.content
        
        # Use NamedTemporaryFile to create a secure temporary file
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        temp_file_path = temp_file.name
        
        try:
            temp_file.write(content)
            temp_file.close() # Close to flush and release handle so other processes can read it
            
            await ingest_document(document_id, temp_file_path)
            return rag_pb2.IngestResponse(status="ok")
        except Exception as e:
            logger.error(f"Error in gRPC Ingest: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return rag_pb2.IngestResponse(status="error")
        finally:
            # Guaranteed deletion
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as ex:
                    logger.warning(f"Failed to delete temp file {temp_file_path}: {ex}")

    async def Query(self, request, context):
        """Answer *request.query* using RAG context + Ollama."""
        logger.info(f"gRPC Query request received: {request.query}")
        query = request.query

        try:
            ollama = OllamaClient()
            chroma = ChromaClient()

            context_text = "No specific context available."
            source_docs_list = []
            is_chroma_up = await chroma.check_health()
            if is_chroma_up:
                collections = await chroma.list_collections()
                retrieved_contexts = []
                for col_info in collections:
                    col_name = col_info.get("name", "")
                    if col_name.startswith("rfp_"):
                        try:
                            # Get handle to collection and query
                            collection = await chroma.get_or_create_collection(col_name)
                            query_results = await collection.query(query_texts=[query], n_results=3)
                            
                            # Extract documents, distances, and metadata
                            docs = query_results.get("documents", [[]])[0]
                            ids = query_results.get("ids", [[]])[0]
                            distances = query_results.get("distances", [[]])[0] if "distances" in query_results else [0.5] * len(docs)
                            metadatas = query_results.get("metadatas", [[]])[0] if "metadatas" in query_results else [{}] * len(docs)
                            
                            for doc, doc_id, dist, meta in zip(docs, ids, distances, metadatas):
                                retrieved_contexts.append(doc)
                                source_docs_list.append({
                                    "id": doc_id,
                                    "score": dist,
                                    "source": meta.get("source", "unknown"),
                                    "collection": col_name
                                })
                        except Exception as col_err:
                            logger.error(f"Failed to query collection {col_name}: {col_err}")
                
                if retrieved_contexts:
                    context_text = "\n\n".join(retrieved_contexts)

            prompt = f"Based on the following context, answer the query.\nContext: {context_text}\nQuery: {query}"

            # Select first available Ollama model dynamically
            pulled_models = await ollama.get_pulled_models()
            if not pulled_models:
                raise Exception("No pulled models found in Ollama. Please run 'ollama pull qwen2.5-coder' or select a pulled model in Settings first.")

            selected_model = "llama3.1:8b"
            found_model = False
            
            preferred_candidates = ["qwen2.5-coder", "gemma", "deepseek", "phi3", "llama3.1:8b", "llama3", "mistral"]
            for pref in preferred_candidates:
                matched = [m for m in pulled_models if pref in m.lower() or m == pref]
                if matched:
                    selected_model = matched[0]
                    found_model = True
                    break
            
            if not found_model and pulled_models:
                selected_model = pulled_models[0]


            logger.info(f"Generating Ollama answer using model: {selected_model}")
            answer = await ollama.generate(
                model=selected_model,
                prompt=prompt,
                system_context="You are an expert proposal assistant."
            )

            source_documents = json.dumps(source_docs_list if source_docs_list else [{"id": "empty", "score": 1.0}])
            return rag_pb2.QueryResponse(
                answer=answer,
                source_documents=source_documents
            )
        except Exception as e:
            logger.error(f"Error in gRPC Query: {str(e)}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return rag_pb2.QueryResponse(answer="", source_documents="[]")


async def serve():
    """Start the RAG gRPC server."""
    setup_telemetry("rag-sidecar")
    interceptors = [TracingServerInterceptor()]
    if os.environ.get("ENV") == "production":
        api_key = os.environ.get("API_KEY", "sentinel-secret-api-key")
        interceptors.append(AuthInterceptor(api_key))

    server = grpc.aio.server(interceptors=interceptors)
    rag_pb2_grpc.add_RagServiceServicer_to_server(
        RagServiceServicer(), server
    )
    
    # Add standard gRPC health checks
    from grpc_health.v1 import health, health_pb2, health_pb2_grpc
    health_servicer = health.HealthServicer()
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    port = os.environ.get("PORT", "50052")
    bind_address = f"0.0.0.0:{port}"
    
    # Secure port binding in production (localhost loopback via Local TCP) unless running inside Docker
    if os.environ.get("ENV") == "production" and os.environ.get("RUNNING_IN_DOCKER") != "true":
        server_credentials = grpc.local_server_credentials(grpc.LocalConnectionType.LOCAL_TCP)
        server.add_secure_port(bind_address, server_credentials)
        logger.info(f"RAG gRPC Server starting with Secure Local TCP credentials on {bind_address}")
    else:
        server.add_insecure_port(bind_address)
        logger.info(f"RAG gRPC Server starting on bind address: {bind_address} (INSECURE)")

    loop = asyncio.get_running_loop()
    async def shutdown():
        logger.info("SIGTERM received, stopping RAG gRPC server gracefully...")
        await server.stop(5)
        logger.info("RAG gRPC server stopped.")

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            pass

    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
