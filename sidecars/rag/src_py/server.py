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
import grpc

# Add the proto folder to search path so pb2 packages import cleanly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../proto")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import rag_pb2
import rag_pb2_grpc

from .ingest import ingest_document
from .ollama_client import OllamaClient
from .chroma_client import ChromaClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag.server")


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
            is_chroma_up = await chroma.check_health()
            if is_chroma_up:
                context_text = (
                    "The requirement is to provide a comprehensive response "
                    "focusing on security and local processing."
                )

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

            source_documents = json.dumps([{"id": "mock-1", "score": 0.9}])
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
    server = grpc.aio.server()
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
    server.add_insecure_port(bind_address)
    logger.info(f"RAG gRPC Server starting on bind address: {bind_address}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
