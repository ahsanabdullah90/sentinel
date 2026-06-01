"""Gap Engine JSON-RPC Server Module

Provides Gap Engine endpoints via standard input/output streams.
"""

import asyncio
import logging
import os
import sys
import json
import traceback

# ---------------------------------------------------------------------------
# IPC Hijack & Safety Redirection
# ---------------------------------------------------------------------------
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
logger = logging.getLogger("gap_engine.server")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_analyze_gaps(params: dict, req_id: str):
    rfp_id = params.get("rfp_id")
    if not rfp_id or any(char in rfp_id for char in ["/", "\\", "..", "*", "?", " "]):
        logger.error(f"Malicious or invalid rfp_id received: '{rfp_id}'")
        _emit_ipc({
            "error": {"message": "Invalid rfp_id format"},
            "req_id": req_id
        })
        return

    logger.info(f"JSON-RPC AnalyzeGaps request received for RFP ID: {rfp_id}")

    try:
        # Static mock gap stubs for now
        gaps = [
            {"area": "Security", "description": "Missing details on data encryption at rest."},
            {"area": "Compliance", "description": "FedRAMP level not specified."}
        ]
        
        _emit_ipc({
            "result": {
                "rfp_id": rfp_id,
                "gaps": gaps
            },
            "req_id": req_id
        })
    except Exception as e:
        logger.error(f"Error in JSON-RPC AnalyzeGaps: {str(e)}")
        _emit_ipc({
            "error": {"message": str(e)},
            "req_id": req_id
        })

def _emit_ipc(data: dict):
    try:
        ipc_out.write(json.dumps(data) + "\n")
        ipc_out.flush()
    except Exception as e:
        logger.error(f"Failed to write IPC message: {e}")

# ---------------------------------------------------------------------------
# Main IPC Loop
# ---------------------------------------------------------------------------

async def serve():
    logger.info("Gap Engine JSON-RPC Server started over stdin/stdout.")
    _emit_ipc({"event": "ready"})

    active_tasks = set()
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    try:
        while True:
            line = await reader.readline()
            if not line:
                logger.info("EOF received on stdin. Shutting down.")
                break
                
            line_str = line.decode('utf-8').strip()
            if not line_str:
                continue

            try:
                req = json.loads(line_str)
                method = req.get("method")
                params = req.get("params", {})
                req_id = req.get("id", "")

                if method == "analyze_gaps":
                    task = asyncio.create_task(handle_analyze_gaps(params, req_id))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                else:
                    logger.warning(f"Unknown JSON-RPC method: {method}")
                    _emit_ipc({
                        "error": {"message": f"Unknown method: {method}"},
                        "req_id": req_id
                    })
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON on stdin: {line_str}")
            except Exception as e:
                logger.error(f"Error processing IPC request: {str(e)}\n{traceback.format_exc()}")
                
    except asyncio.CancelledError:
        logger.info("Main IPC loop cancelled.")
    finally:
        for task in active_tasks:
            task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        logger.info("Gap Engine JSON-RPC Server gracefully shutdown.")

if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
