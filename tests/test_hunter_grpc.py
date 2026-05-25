"""Tests for the Hunter gRPC server integration.

These tests spin up a real gRPC server in-process and exercise the
Detect and Hunt RPCs end-to-end.
"""

import asyncio
import json
import os
import sys
import pytest
import grpc

# Paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "proto"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hunter_pb2
import hunter_pb2_grpc

from sidecars.hunter.src_py.server import HunterServiceServicer


@pytest.fixture
async def hunter_grpc_channel():
    """Start a Hunter gRPC server on a random port and yield a channel."""
    server = grpc.aio.server()
    hunter_pb2_grpc.add_HunterServiceServicer_to_server(
        HunterServiceServicer(), server
    )
    port = server.add_insecure_port("[::]:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"localhost:{port}")
    yield channel
    await channel.close()
    await server.stop(grace=0)


class TestHunterGrpcIntegration:
    """End-to-end gRPC integration tests for the Hunter sidecar."""

    @pytest.mark.asyncio
    async def test_detect_returns_response(self, hunter_grpc_channel):
        """Detect RPC should return at least one response."""
        stub = hunter_pb2_grpc.HunterServiceStub(hunter_grpc_channel)
        request = hunter_pb2.DetectRequest(url="https://example.com")
        responses = []
        async for resp in stub.Detect(request):
            responses.append(resp)
        assert len(responses) >= 1

    @pytest.mark.asyncio
    async def test_detect_event_type(self, hunter_grpc_channel):
        """Detect RPC should return an event field."""
        stub = hunter_pb2_grpc.HunterServiceStub(hunter_grpc_channel)
        request = hunter_pb2.DetectRequest(url="https://example.com")
        async for resp in stub.Detect(request):
            assert resp.event in ("portal_detected", "error")
            break

    @pytest.mark.asyncio
    async def test_hunt_returns_response(self, hunter_grpc_channel):
        """Hunt RPC should return at least one response."""
        os.environ["SENTINEL_DEV_BYPASS_RATE_LIMIT"] = "true"
        try:
            stub = hunter_pb2_grpc.HunterServiceStub(hunter_grpc_channel)
            request = hunter_pb2.HuntRequest(portal_id="test-portal")
            responses = []
            async for resp in stub.Hunt(request):
                responses.append(resp)
            assert len(responses) >= 1
        finally:
            os.environ.pop("SENTINEL_DEV_BYPASS_RATE_LIMIT", None)

    @pytest.mark.asyncio
    async def test_hunt_with_config_json(self, hunter_grpc_channel):
        """Hunt RPC should accept mock_config_json."""
        os.environ["SENTINEL_DEV_BYPASS_RATE_LIMIT"] = "true"
        try:
            stub = hunter_pb2_grpc.HunterServiceStub(hunter_grpc_channel)
            config = json.dumps({
                "baseUrl": "https://example.com",
                "scraperModule": "static_html",
                "requestsPerMinute": 5
            })
            request = hunter_pb2.HuntRequest(
                portal_id="test-portal-2",
                mock_config_json=config
            )
            responses = []
            async for resp in stub.Hunt(request):
                responses.append(resp)
            assert len(responses) >= 1
        finally:
            os.environ.pop("SENTINEL_DEV_BYPASS_RATE_LIMIT", None)
