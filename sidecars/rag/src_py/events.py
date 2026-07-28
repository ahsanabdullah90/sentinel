"""Event Module for RAG Sidecar

Provides unified event emission for IPC communication with the Tauri Rust backend.
All events are written as JSON lines to the original stdout (captured at import time
before server.py redirects stdout to stderr).
"""

import json
import sys
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("rag.events")

# Capture original stdout before server.py potentially redirects it
# This ensures IPC messages always go to the correct stream
ipc_out = sys.stdout


def _emit_ipc(data: dict) -> None:
    """Write a single JSON line to the IPC output stream.

    Args:
        data: Dictionary to serialize as JSON.
    """
    try:
        ipc_out.write(json.dumps(data, ensure_ascii=False) + "\n")
        ipc_out.flush()
    except Exception as e:
        logger.error(f"Failed to write IPC message: {e}")


def emit_progress(message: str, portal_id: str = "rag") -> None:
    """Emit a progress event to the IPC stream.

    Args:
        message: Human-readable progress description.
        portal_id: Identifier for the service (default 'rag').
    """
    _emit_ipc({
        "event": "progress",
        "portalId": portal_id,
        "message": message
    })


def emit_warning(message: str) -> None:
    """Emit a warning event to the IPC stream."""
    _emit_ipc({"event": "warning", "message": message})


def emit_error(message: str) -> None:
    """Emit an error event to the IPC stream."""
    _emit_ipc({"event": "error", "message": message})


def emit_result(result: dict, req_id: str) -> None:
    """Emit a JSON-RPC result response.

    Args:
        result: The result payload.
        req_id: Request identifier from the original JSON-RPC call.
    """
    _emit_ipc({"result": result, "req_id": req_id})


def emit_error_response(message: str, req_id: str) -> None:
    """Emit a JSON-RPC error response.

    Args:
        message: Human-readable error description.
        req_id: Request identifier from the original JSON-RPC call.
    """
    _emit_ipc({"error": {"message": message}, "req_id": req_id})
