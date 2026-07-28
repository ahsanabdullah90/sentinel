"""Event Module for Worker Sidecar

Provides unified event emission for IPC communication with the Tauri Rust backend.
All events are written as JSON lines to the original stdout (captured at import time
before server.py redirects stdout to stderr).
"""

import json
import sys
import logging
from typing import Any

logger = logging.getLogger("worker.events")

# Capture original stdout before server.py potentially redirects it
ipc_out = sys.stdout


def _emit_ipc(data: dict) -> None:
    """Write a single JSON line to the IPC output stream."""
    try:
        ipc_out.write(json.dumps(data, ensure_ascii=False) + "\n")
        ipc_out.flush()
    except Exception as e:
        logger.error(f"Failed to write IPC message: {e}")


def emit_progress(message: str) -> None:
    """Emit a progress event to the IPC stream."""
    _emit_ipc({"event": "progress", "portalId": "worker", "message": message})


def emit_ready() -> None:
    """Emit a ready signal so the Rust parent knows the server is up."""
    _emit_ipc({"event": "ready"})


def emit_result(result: dict, req_id: str) -> None:
    """Emit a JSON-RPC result response."""
    _emit_ipc({"result": result, "req_id": req_id})


def emit_error_response(message: str, req_id: str) -> None:
    """Emit a JSON-RPC error response."""
    _emit_ipc({"error": {"message": message}, "req_id": req_id})
