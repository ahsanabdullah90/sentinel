import asyncio
import json
import os
import sys
from concurrent import futures
import grpc
from . import hunter_pb2
from . import hunter_pb2_grpc
from .scraper_engine import ScraperEngine
from .rate_limiter import TokenBucketRateLimiter

class HunterService(hunter_pb2_grpc.HunterServiceServicer):
    def __init__(self):
        self.engine = ScraperEngine()
        self.limiters = {}

    async def Detect(self, request, context):
        print(f"Detecting: {request.url}")
        # Simplified detection for now
        yield hunter_pb2.DetectResponse(
            event="portal_detected",
            json_payload=json.dumps({"url": request.url, "score": "good"})
        )

    async def Hunt(self, request, context):
        portal_id = request.portal_id
        if portal_id not in self.limiters:
            self.limiters[portal_id] = TokenBucketRateLimiter()

        rate_limiter = self.limiters[portal_id]

        config = {}
        try:
            if request.mock_config_json:
                config = json.loads(request.mock_config_json)
        except:
            pass

        print(f"Starting hunt for {portal_id}")

        # In a real async gRPC, we'd run the engine and yield progress
        # For now, we simulate a small part
        try:
            await self.engine.hunt(portal_id, config, rate_limiter)
            yield hunter_pb2.HuntResponse(
                event="hunt_complete",
                json_payload=json.dumps({"success": True})
            )
        except Exception as e:
            yield hunter_pb2.HuntResponse(
                event="error",
                json_payload=json.dumps({"message": str(e)})
            )

async def serve():
    server = grpc.aio.server()
    hunter_pb2_grpc.add_HunterServiceServicer_to_server(HunterService(), server)
    port = os.getenv("PORT", "50051")
    server.add_insecure_port(f'[::]:{port}')
    print(f"Hunter gRPC server starting on port {port}")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    # Add parent directory to sys.path to allow relative imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    asyncio.run(serve())
