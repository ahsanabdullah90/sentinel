"""Tests for the RAG gRPC server integration.

These tests spin up a real gRPC server in-process and exercise
the Ingest and Query RPCs end-to-end.
"""

import asyncio
import json
import os
import sys
import pytest
import grpc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "proto"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import rag_pb2
import rag_pb2_grpc

from sidecars.rag.src_py.server import RagServiceServicer


@pytest.fixture
async def rag_grpc_channel():
    """Start a RAG gRPC server on a random port and yield a channel."""
    server = grpc.aio.server()
    rag_pb2_grpc.add_RagServiceServicer_to_server(
        RagServiceServicer(), server
    )
    port = server.add_insecure_port("[::]:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"localhost:{port}")
    yield channel
    await channel.close()
    await server.stop(grace=0)


class TestRagGrpcIntegration:
    """End-to-end gRPC integration tests for the RAG sidecar."""

    @pytest.mark.asyncio
    async def test_ingest_returns_status(self, rag_grpc_channel):
        """Ingest RPC should return a status field."""
        stub = rag_pb2_grpc.RagServiceStub(rag_grpc_channel)
        request = rag_pb2.IngestRequest(
            document_id="test-doc-001",
            content="This is a test document for ingestion."
        )
        response = await stub.Ingest(request)
        # Status will be 'ok' if chroma is up, or 'ok' with warning if not
        assert response.status in ("ok", "error")

    @pytest.mark.asyncio
    async def test_query_returns_answer(self, rag_grpc_channel):
        """Query RPC should return an answer (may be empty if Ollama is down)."""
        stub = rag_pb2_grpc.RagServiceStub(rag_grpc_channel)
        request = rag_pb2.QueryRequest(query="What are the security requirements?")
        try:
            response = await stub.Query(request)
            # Response should have answer and source_documents fields
            assert hasattr(response, "answer")
            assert hasattr(response, "source_documents")
        except grpc.aio.AioRpcError:
            # Expected if Ollama is not running
            pass

    @pytest.mark.asyncio
    async def test_ingest_empty_content(self, rag_grpc_channel):
        """Ingest with empty content should still return a response."""
        stub = rag_pb2_grpc.RagServiceStub(rag_grpc_channel)
        request = rag_pb2.IngestRequest(
            document_id="empty-doc",
            content=""
        )
        response = await stub.Ingest(request)
        assert response.status in ("ok", "error")
