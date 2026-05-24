import asyncio
import logging
import os
import sys
import json
import grpc

# Add the proto folder to search path so pb2 packages import cleanly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../proto")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import hunter_pb2
import hunter_pb2_grpc

from .portal_analyzer import analyze_portal
from .portal_runner import PortalRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hunter.server")

class HunterServiceServicer(hunter_pb2_grpc.HunterServiceServicer):
    async def Detect(self, request, context):
        logger.info(f"gRPC Detect request received for URL: {request.url}")
        try:
            report = await analyze_portal(request.url)
            yield hunter_pb2.DetectResponse(
                event="portal_detected",
                json_payload=json.dumps(report)
            )
        except Exception as e:
            logger.error(f"Error in gRPC Detect: {str(e)}")
            yield hunter_pb2.DetectResponse(
                event="error",
                json_payload=json.dumps({"message": str(e)})
            )

    async def Hunt(self, request, context):
        logger.info(f"gRPC Hunt request received for Portal ID: {request.portal_id}")
        portal_id = request.portal_id
        
        # Parse or default config
        mock_config = {
            "id": portal_id,
            "name": "Mock Portal",
            "baseUrl": "https://example.com",
            "authMethod": "public",
            "scraperModule": "static_html",
            "activeWindowStart": "00:00",
            "activeWindowEnd": "23:59",
            "requestsPerMinute": 15
        }
        
        if request.mock_config_json:
            try:
                parsed = json.loads(request.mock_config_json)
                if parsed:
                    mock_config.update(parsed)
            except Exception as pe:
                logger.warning(f"Failed to parse mock_config_json: {str(pe)}, using defaults")

        runner = PortalRunner()
        try:
            await runner.run_portal(mock_config)
            yield hunter_pb2.HuntResponse(
                event="hunt_complete",
                json_payload=json.dumps({"success": True})
            )
        except Exception as e:
            logger.error(f"Error in gRPC Hunt: {str(e)}")
            yield hunter_pb2.HuntResponse(
                event="error",
                json_payload=json.dumps({"message": str(e)})
            )

async def serve():
    server = grpc.aio.server()
    hunter_pb2_grpc.add_HunterServiceServicer_to_server(
        HunterServiceServicer(), server
    )
    port = os.environ.get("PORT", "50051")
    bind_address = f"0.0.0.0:{port}"
    server.add_insecure_port(bind_address)
    logger.info(f"Hunter gRPC Server starting on bind address: {bind_address}")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
