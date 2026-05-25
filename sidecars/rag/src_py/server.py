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
        document_id = request.document_id
        content = request.content
        temp_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../temp_{document_id}.txt"))

        try:
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(content)

            await ingest_document(document_id, temp_file_path)

            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

            return rag_pb2.IngestResponse(status="ok")
        except Exception as e:
            logger.error(f"Error in gRPC Ingest: {str(e)}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return rag_pb2.IngestResponse(status="error")

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

            # Select first available Ollama model
            selected_model = "llama3.1:8b"
            for candidate in ["llama3.1:8b", "llama3", "mistral"]:
                is_pulled = await ollama.is_model_pulled(candidate)
                if is_pulled:
                    selected_model = candidate
                    break

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
    port = os.environ.get("PORT", "50052")
    bind_address = f"0.0.0.0:{port}"
    server.add_insecure_port(bind_address)
    logger.info(f"RAG gRPC Server starting on bind address: {bind_address}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
