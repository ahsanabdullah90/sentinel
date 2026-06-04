"""Hunter JSON-RPC Server Module

Provides scraping endpoints via standard input/output streams.
"""

import asyncio
import logging
import os
import sys
import json
import traceback
import threading

from sidecars.hunter.src_py.portal_analyzer import analyze_portal
from sidecars.hunter.src_py.portal_runner import PortalRunner
from sidecars.hunter.src_py.models import PortalConfig

# ---------------------------------------------------------------------------
# IPC Hijack & Safety Redirection
# ---------------------------------------------------------------------------
# We capture the original stdout for pure JSON-RPC IPC.
# We redirect sys.stdout to sys.stderr so that stray print() statements
# do not corrupt the JSON stream.
ipc_out = sys.stdout
sys.stdout = sys.stderr

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

handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("hunter.server")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_detect(params: dict, req_id: str):
    url = params.get("url")
    if not url:
        await _emit_ipc({"event": "error", "json_payload": '{"message": "Missing url"}', "req_id": req_id})
        return

    logger.info(f"JSON-RPC Detect request received for URL: {url}")
    try:
        report = await analyze_portal(url)
        await _emit_ipc({
            "event": "portal_detected",
            "json_payload": json.dumps(report),
            "payload_type": 0,
            "req_id": req_id
        })
    except Exception as e:
        logger.error(f"Error in analyze_portal: {str(e)}")
        _emit_ipc({
            "event": "error",
            "json_payload": json.dumps({"message": str(e)}),
            "payload_type": 0,
            "req_id": req_id
        })
    finally:
        await _emit_ipc({"event": "detect_complete", "req_id": req_id})

async def handle_hunt(params: dict, req_id: str):
    portal_id = params.get("portal_id", "")
    mock_config_json = params.get("mock_config_json", "{}")
    logger.info(f"JSON-RPC Hunt request received for Portal ID: {portal_id}")

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

    try:
        parsed = json.loads(mock_config_json)
        if parsed:
            if "url" in parsed and parsed["url"]:
                parsed["baseUrl"] = parsed["url"]
            if "base_url" in parsed and parsed["base_url"]:
                parsed["baseUrl"] = parsed["base_url"]
            if "scraper_module" in parsed and parsed["scraper_module"]:
                parsed["scraperModule"] = parsed["scraper_module"]
            elif "rendering_mode" in parsed and parsed["rendering_mode"]:
                parsed["scraperModule"] = "generic_search"
            raw_config.update(parsed)
    except Exception as pe:
        logger.warning(f"Failed to parse config JSON: {str(pe)}, using fallbacks")

    try:
        config = PortalConfig.model_validate(raw_config)
    except Exception as ve:
        logger.error(f"Config validation error: {str(ve)}")
        _emit_ipc({
            "event": "error",
            "json_payload": json.dumps({"message": f"Configuration validation failed: {str(ve)}"}),
            "payload_type": 0,
            "req_id": req_id
        })
        _emit_ipc({"event": "hunt_complete", "req_id": req_id})
        return

    async def on_event(event_name: str, payload: dict):
        await _emit_ipc({
            "event": event_name,
            "json_payload": json.dumps(payload),
            "payload_type": 0,
            "req_id": req_id
        })

    runner = PortalRunner()
    try:
        await runner.run_portal(config, on_event=on_event)
        await _emit_ipc({
            "event": "hunt_complete",
            "json_payload": json.dumps({"success": True}),
            "payload_type": 0,
            "req_id": req_id
        })
    except Exception as e:
        logger.error(f"Error executing hunt: {str(e)}")
        await _emit_ipc({
            "event": "error",
            "json_payload": json.dumps({"message": str(e)}),
            "payload_type": 0,
            "req_id": req_id
        })
        await _emit_ipc({"event": "hunt_complete", "req_id": req_id})

async def _emit_ipc(data: dict):
    """Writes a single JSON line to the IPC output stream without blocking the event loop."""
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: (
            ipc_out.write(json.dumps(data) + "\n"),
            ipc_out.flush()
        ))
    except Exception as e:
        logger.error(f"Failed to write IPC message: {e}")

# ---------------------------------------------------------------------------
# Main IPC Loop
# ---------------------------------------------------------------------------

async def serve():
    logger.info("Hunter JSON-RPC Server started over stdin/stdout.")
    
    # Send a ready signal so the Rust parent knows we're up
    await _emit_ipc({"event": "ready"})

    # Setup a background task group to handle concurrent requests
    active_tasks = set()

    def stdin_reader(q, loop_ref):
        for stdin_line in sys.stdin:
            loop_ref.call_soon_threadsafe(q.put_nowait, stdin_line)
        loop_ref.call_soon_threadsafe(q.put_nowait, None)

    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    
    t = threading.Thread(target=stdin_reader, args=(queue, loop), daemon=True)
    t.start()

    try:
        while True:
            line = await queue.get()
            if line is None:
                logger.info("EOF received on stdin. Shutting down.")
                break
                
            line_str = line.strip()
            if not line_str:
                continue

            try:
                req = json.loads(line_str)
                method = req.get("method")
                params = req.get("params", {})
                req_id = req.get("id", "")

                if method == "detect":
                    task = asyncio.create_task(handle_detect(params, req_id))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                elif method == "hunt":
                    task = asyncio.create_task(handle_hunt(params, req_id))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                else:
                    logger.warning(f"Unknown JSON-RPC method: {method}")
                    await _emit_ipc({
                        "event": "error",
                        "json_payload": json.dumps({"message": f"Unknown method: {method}"}),
                        "payload_type": 0,
                        "req_id": req_id
                    })
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON on stdin: {line_str}")
            except Exception as e:
                logger.error(f"Error processing IPC request: {str(e)}\n{traceback.format_exc()}")
                
    except asyncio.CancelledError:
        logger.info("Main IPC loop cancelled.")
    finally:
        # Cancel all active tasks
        for task in active_tasks:
            task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        logger.info("Hunter JSON-RPC Server gracefully shutdown.")

if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
