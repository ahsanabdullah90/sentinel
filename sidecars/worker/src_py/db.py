"""Database Module for Worker Sidecar

Provides SQLite-backed job queue operations.
All database functions are synchronous (designed to be called
via ``run_in_executor`` from async code).
"""

import json
import logging
import os
import sqlite3
from typing import Dict, Any, Optional

logger = logging.getLogger("worker.db")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _db_path() -> str:
    """Resolve the database file path, respecting the environment variable."""
    return os.environ.get(
        "SENTINEL_DB_PATH",
        os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "worker_jobs.db"
        ),
    )


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def _get_connection() -> sqlite3.Connection:
    """Open a new SQLite connection with sensible defaults."""
    conn = sqlite3.connect(_db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def init_db():
    """Create the jobs table if it doesn't exist, recover stuck jobs, prune old records."""
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfp_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        # Recovery: reset stuck 'processing' jobs to 'pending' on startup
        cur.execute(
            """
            UPDATE jobs SET status = 'pending', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'processing'
        """
        )
        # Retention: prune completed/failed jobs older than 7 days
        cur.execute(
            """
            DELETE FROM jobs
            WHERE status IN ('completed', 'failed')
            AND updated_at < datetime('now', '-7 days')
        """
        )
        conn.commit()
        logger.info(
            f"Initialized SQLite job queue at {_db_path()}"
        )
    except Exception as e:
        logger.error(f"Failed to initialize SQLite job queue: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def enqueue_job(rfp_id: str, payload: str):
    """Insert a new pending job into the queue.

    Args:
        rfp_id: RFP identifier associated with the job.
        payload: JSON string with job data.
    """
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO jobs (rfp_id, payload, status) VALUES (?, ?, 'pending')",
            (rfp_id, payload),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to enqueue job: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def pop_job() -> Optional[Dict[str, Any]]:
    """Atomically pop the oldest pending job and mark it as processing.

    Returns:
        A dict with keys ``id``, ``rfp_id``, ``payload``, or ``None`` if empty.
    """
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute(
            """
            SELECT id, rfp_id, payload FROM jobs
            WHERE status = 'pending'
            ORDER BY id ASC LIMIT 1
        """
        )
        row = cur.fetchone()
        if row:
            job_id = row["id"]
            cur.execute(
                "UPDATE jobs SET status = 'processing', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (job_id,),
            )
            conn.commit()
            return dict(row)
        conn.commit()
        return None
    except sqlite3.OperationalError as e:
        logger.warning(f"Database locked or busy: {e}")
        if conn:
            conn.rollback()
        return None
    except Exception as e:
        logger.error(f"Error in pop_job: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()


def save_result(job_id: int, result: str, status: str):
    """Update a job with its result and final status.

    Args:
        job_id: The job's primary key.
        result: JSON string of the result payload.
        status: Final status (``completed`` or ``failed``).
    """
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE jobs
            SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (status, result, job_id),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to save result for job {job_id}: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()
