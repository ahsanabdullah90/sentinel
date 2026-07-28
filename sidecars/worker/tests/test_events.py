"""Tests for the Worker events module."""

import json
import io

from sidecars.worker.src_py import events as evt


def test_emit_ipc_writes_json():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt._emit_ipc({"test": "data"})
        assert json.loads(buf.getvalue().strip()) == {"test": "data"}
    finally:
        evt.ipc_out = old


def test_emit_progress():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_progress("working...")
        output = json.loads(buf.getvalue().strip())
        assert output["event"] == "progress"
        assert output["portalId"] == "worker"
        assert output["message"] == "working..."
    finally:
        evt.ipc_out = old


def test_emit_ready():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_ready()
        assert json.loads(buf.getvalue().strip()) == {"event": "ready"}
    finally:
        evt.ipc_out = old


def test_emit_result():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_result({"success": True}, "req-1")
        output = json.loads(buf.getvalue().strip())
        assert output["result"] == {"success": True}
        assert output["req_id"] == "req-1"
    finally:
        evt.ipc_out = old


def test_emit_error_response():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_error_response("oops", "req-2")
        output = json.loads(buf.getvalue().strip())
        assert output["error"]["message"] == "oops"
        assert output["req_id"] == "req-2"
    finally:
        evt.ipc_out = old
