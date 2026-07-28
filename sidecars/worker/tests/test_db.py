"""Tests for the Worker database module."""

import os
import json
import tempfile

import pytest

from sidecars.worker.src_py.db import (
    init_db,
    enqueue_job,
    pop_job,
    save_result,
    _get_connection,
)


@pytest.fixture
def temp_db():
    """Provide an isolated temporary database for each test."""
    old_path = os.environ.get("SENTINEL_DB_PATH")
    tmp_dir = tempfile.mkdtemp()
    tmp_db = os.path.join(tmp_dir, "test_worker.db")
    os.environ["SENTINEL_DB_PATH"] = tmp_db
    try:
        yield tmp_db
    finally:
        if old_path is not None:
            os.environ["SENTINEL_DB_PATH"] = old_path
        elif "SENTINEL_DB_PATH" in os.environ:
            del os.environ["SENTINEL_DB_PATH"]
        if os.path.exists(tmp_db):
            os.unlink(tmp_db)
        os.rmdir(tmp_dir)


class TestDBInit:
    def test_init_creates_table(self, temp_db):
        init_db()
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        assert cur.fetchone() is not None
        conn.close()


class TestEnqueueJob:
    def test_enqueues_pending_job(self, temp_db):
        init_db()
        enqueue_job("rfp-001", '{"title": "Test"}')
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status FROM jobs WHERE rfp_id = 'rfp-001'")
        row = cur.fetchone()
        assert row[0] == "pending"
        conn.close()

    def test_multiple_jobs(self, temp_db):
        init_db()
        enqueue_job("rfp-001", "{}")
        enqueue_job("rfp-002", "{}")
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM jobs")
        assert cur.fetchone()[0] == 2
        conn.close()


class TestPopJob:
    def test_pop_returns_oldest_pending(self, temp_db):
        init_db()
        enqueue_job("rfp-001", '{"a": 1}')
        enqueue_job("rfp-002", '{"b": 2}')
        job = pop_job()
        assert job is not None
        assert job["rfp_id"] == "rfp-001"

    def test_pop_mark_processing(self, temp_db):
        init_db()
        enqueue_job("rfp-001", '{"a": 1}')
        pop_job()
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status FROM jobs WHERE rfp_id = 'rfp-001'")
        assert cur.fetchone()[0] == "processing"
        conn.close()

    def test_pop_empty_returns_none(self, temp_db):
        init_db()
        assert pop_job() is None

    def test_pop_only_returns_pending(self, temp_db):
        init_db()
        enqueue_job("rfp-001", "{}")
        pop_job()
        assert pop_job() is None


class TestSaveResult:
    def test_saves_result_and_status(self, temp_db):
        init_db()
        enqueue_job("rfp-001", "{}")
        job = pop_job()
        save_result(job["id"], '{"result": "ok"}', "completed")
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status, result FROM jobs WHERE id = ?", (job["id"],))
        row = cur.fetchone()
        assert row[0] == "completed"
        assert json.loads(row[1]) == {"result": "ok"}
        conn.close()
