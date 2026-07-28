"""Tests for the Gap Engine events module."""

import json
import io

from sidecars.gap_engine.src_py import events as evt


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
        evt.emit_progress("analyzing...")
        output = json.loads(buf.getvalue().strip())
        assert output["event"] == "progress"
        assert output["portalId"] == "gap_engine"
        assert output["message"] == "analyzing..."
    finally:
        evt.ipc_out = old


def test_emit_gap_report():
    buf = io.StringIO()
    old = evt.ipc_out
    gaps = [{"area": "Security", "description": "Missing encryption"}]
    try:
        evt.ipc_out = buf
        evt.emit_gap_report("rfp-001", gaps)
        output = json.loads(buf.getvalue().strip())
        assert output["event"] == "gap_report_generated"
        assert output["data"]["rfpId"] == "rfp-001"
        assert output["data"]["gaps"] == gaps
    finally:
        evt.ipc_out = old


def test_emit_result():
    buf = io.StringIO()
    old = evt.ipc_out
    try:
        evt.ipc_out = buf
        evt.emit_result({"status": "ok"}, "req-1")
        output = json.loads(buf.getvalue().strip())
        assert output["result"] == {"status": "ok"}
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
