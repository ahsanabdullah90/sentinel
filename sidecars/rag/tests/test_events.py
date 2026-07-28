"""Tests for the RAG events module."""

import json
import io

from sidecars.rag.src_py import events as evt


def test_emit_ipc_writes_json_to_ipc_out():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt._emit_ipc({"test": "data"})
        output = buf.getvalue().strip()
        assert json.loads(output) == {"test": "data"}
    finally:
        evt.ipc_out = old


def test_emit_progress():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_progress("processing...", "test-portal")
        output = json.loads(buf.getvalue().strip())
        assert output["event"] == "progress"
        assert output["portalId"] == "test-portal"
        assert output["message"] == "processing..."
    finally:
        evt.ipc_out = old


def test_emit_warning():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_warning("something is off")
        output = json.loads(buf.getvalue().strip())
        assert output["event"] == "warning"
        assert output["message"] == "something is off"
    finally:
        evt.ipc_out = old


def test_emit_error():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_error("something went wrong")
        output = json.loads(buf.getvalue().strip())
        assert output["event"] == "error"
        assert output["message"] == "something went wrong"
    finally:
        evt.ipc_out = old


def test_emit_result():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_result({"status": "ok"}, "req-123")
        output = json.loads(buf.getvalue().strip())
        assert output["result"] == {"status": "ok"}
        assert output["req_id"] == "req-123"
    finally:
        evt.ipc_out = old


def test_emit_error_response():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_error_response("failed", "req-456")
        output = json.loads(buf.getvalue().strip())
        assert output["error"]["message"] == "failed"
        assert output["req_id"] == "req-456"
    finally:
        evt.ipc_out = old


def test_ipc_out_is_original_stdout():
    assert evt.ipc_out is not None
    assert hasattr(evt.ipc_out, "write")
    assert hasattr(evt.ipc_out, "flush")
