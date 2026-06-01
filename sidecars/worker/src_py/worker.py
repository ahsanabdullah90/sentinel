"""Worker JSON-RPC Module

Implements a SQLite-backed background job processor and JSON-RPC service
via standard input/output streams.
"""

import asyncio
import json
import logging
import os
import sys
import time
import signal
import hashlib
import traceback
import sqlite3
from typing import Dict, Any, Optional

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
logger = logging.getLogger("worker")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get("SENTINEL_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "..", "worker_jobs.db"))

def init_db():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfp_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Startup recovery: reset stuck 'processing' jobs to 'pending'
        cur.execute("""
            UPDATE jobs SET status = 'pending', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'processing'
        """)
        conn.commit()
        logger.info(f"Initialized SQLite job queue at {DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize SQLite job queue: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def enqueue_job_db(rfp_id: str, payload: str):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO jobs (rfp_id, payload, status)
            VALUES (?, ?, 'pending')
        """, (rfp_id, payload))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to enqueue job: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def pop_job_db() -> Optional[Dict[str, Any]]:
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        
        cur.execute("""
            SELECT id, rfp_id, payload FROM jobs
            WHERE status = 'pending'
            ORDER BY id ASC LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            job_id = row["id"]
            cur.execute("UPDATE jobs SET status = 'processing', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
            conn.commit()
            return dict(row)
        
        conn.commit()
        return None
    except sqlite3.OperationalError as e:
        logger.warning(f"sqlite3 OperationalError in pop_job_db: {e}")
        if conn:
            conn.rollback()
        return None
    except Exception as e:
        logger.error(f"Error in pop_job_db: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def save_result_db(job_id: int, result: str, status: str):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cur = conn.cursor()
        cur.execute("""
            UPDATE jobs
            SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, result, job_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to save result for job {job_id}: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

# ---------------------------------------------------------------------------
# Concrete task processor
# ---------------------------------------------------------------------------

async def process_job(job_id: int, job_data: Dict[str, Any]) -> Dict[str, Any]:
    rfp_id = job_data.get("rfpId") or job_data.get("rfp_id")
    if not rfp_id:
        raise ValueError("Job payload is missing 'rfpId'")

    logger.info(f"Processing job for RFP: {rfp_id}")

    normalised: Dict[str, Any] = {}
    for key, value in job_data.items():
        norm_key = key.strip()
        if isinstance(value, str):
            normalised[norm_key] = value.strip()
        else:
            normalised[norm_key] = value

    content_str = json.dumps(normalised, sort_keys=True)
    content_hash = hashlib.sha256(content_str.encode()).hexdigest()[:16]

    result: Dict[str, Any] = {
        **normalised,
        "contentHash": content_hash,
        "processedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workerVersion": "1.0.0",
        "status": "processed",
    }

    # Save to SQLite
    def _save():
        save_result_db(job_id, json.dumps(result), 'completed')
        
    await asyncio.get_running_loop().run_in_executor(None, _save)
    logger.info(f"Job {job_id} completed for RFP: {rfp_id} (hash={content_hash})")
    return result

# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

async def run_worker():
    logger.info("Worker started, polling SQLite queue...")
    
    loop = asyncio.get_running_loop()
    
    while True:
        try:
            job_record = await loop.run_in_executor(None, pop_job_db)
            
            if job_record is None:
                await asyncio.sleep(1) # Backoff when empty
                continue
                
            job_id = job_record["id"]
            rfp_id = job_record["rfp_id"]
            raw_data = job_record["payload"]
            
            logger.info(f"Received job {job_id} from queue: {raw_data[:120]}...")

            try:
                job_data = json.loads(raw_data)
                # ensure rfpId
                if "rfpId" not in job_data and "rfp_id" not in job_data:
                    job_data["rfpId"] = rfp_id
            except json.JSONDecodeError as je:
                logger.error(f"Invalid JSON in job payload: {je}")
                await loop.run_in_executor(None, save_result_db, job_id, str(je), 'failed')
                continue

            try:
                await process_job(job_id, job_data)
            except Exception as e:
                logger.error(f"Job processing failed: {e}")
                await loop.run_in_executor(None, save_result_db, job_id, str(e), 'failed')

        except asyncio.CancelledError:
            logger.info("Worker loop cancelled – shutting down")
            break
        except Exception as exc:
            logger.error(f"Unexpected error in worker loop: {exc}\n{traceback.format_exc()}")
            await asyncio.sleep(2)

# ---------------------------------------------------------------------------
# JSON-RPC service
# ---------------------------------------------------------------------------

def _emit_ipc(data: dict):
    try:
        ipc_out.write(json.dumps(data) + "\n")
        ipc_out.flush()
    except Exception as e:
        logger.error(f"Failed to write IPC message: {e}")

async def handle_enqueue_job(params: dict, req_id: str):
    rfp_id = params.get("rfp_id")
    payload = params.get("payload", "{}")
    logger.info(f"JSON-RPC EnqueueJob called for rfp_id={rfp_id}")

    try:
        job_data = json.loads(payload) if payload != "{}" else {}
    except json.JSONDecodeError:
        job_data = {}
        
    if rfp_id:
        job_data["rfpId"] = rfp_id

    loop = asyncio.get_running_loop()

    try:
        await loop.run_in_executor(None, enqueue_job_db, rfp_id, json.dumps(job_data))
        _emit_ipc({
            "result": {
                "success": True,
                "message": f"Job enqueued for RFP {rfp_id}"
            },
            "req_id": req_id
        })
    except Exception as e:
        logger.error(f"SQLite insert failed: {e}")
        _emit_ipc({
            "error": {"message": str(e)},
            "req_id": req_id
        })

async def serve():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, init_db)
    worker_task = asyncio.create_task(run_worker())
    
    logger.info("Worker JSON-RPC Server started over stdin/stdout.")
    _emit_ipc({"event": "ready"})

    active_tasks = set()
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    async def json_rpc_loop():
        try:
            while True:
                line = await reader.readline()
                if not line:
                    logger.info("EOF received on stdin. Shutting down RPC loop.")
                    break
                    
                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue

                try:
                    req = json.loads(line_str)
                    method = req.get("method")
                    params = req.get("params", {})
                    req_id = req.get("id", "")

                    if method == "enqueue_job":
                        task = asyncio.create_task(handle_enqueue_job(params, req_id))
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
            pass

    rpc_task = asyncio.create_task(json_rpc_loop())

    async def shutdown():
        logger.info("SIGTERM received, stopping Worker gracefully...")
        worker_task.cancel()
        rpc_task.cancel()
        logger.info("Worker gracefully stopped.")

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except NotImplementedError:
            pass

    try:
        await asyncio.gather(worker_task, rpc_task)
    except asyncio.CancelledError:
        pass
    finally:
        for task in active_tasks:
            task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)

if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
