"""Worker JSON-RPC Server Module

Provides a SQLite-backed background job processor and JSON-RPC service
via standard input/output streams.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import traceback
from typing import Dict, Any

from sidecars.worker.src_py.db import init_db, enqueue_job, pop_job, save_result
from sidecars.worker.src_py.jobs import process_job
from sidecars.worker.src_py.events import _emit_ipc, emit_ready, emit_result, emit_error_response

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
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("worker.server")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False


# ---------------------------------------------------------------------------
# Worker loop — polls SQLite for pending jobs
# ---------------------------------------------------------------------------


async def run_worker():
    """Continuously poll the SQLite queue for pending jobs."""
    logger.info("Worker started, polling SQLite queue...")
    loop = asyncio.get_running_loop()

    while True:
        try:
            job_record = await loop.run_in_executor(None, pop_job)
            if job_record is None:
                await asyncio.sleep(1)
                continue

            job_id = job_record["id"]
            rfp_id = job_record["rfp_id"]
            raw_data = job_record["payload"]

            logger.info(f"Received job {job_id} from queue: {raw_data[:120]}...")

            try:
                job_data = json.loads(raw_data)
                if "rfpId" not in job_data and "rfp_id" not in job_data:
                    job_data["rfpId"] = rfp_id
            except json.JSONDecodeError as je:
                logger.error(f"Invalid JSON in job payload: {je}")
                await loop.run_in_executor(None, save_result, job_id, str(je), "failed")
                continue

            try:
                await process_job(job_id, job_data)
            except Exception as e:
                logger.error(f"Job processing failed: {e}")
                await loop.run_in_executor(None, save_result, job_id, str(e), "failed")

        except asyncio.CancelledError:
            logger.info("Worker loop cancelled – shutting down")
            break
        except Exception as exc:
            logger.error(f"Unexpected error in worker loop: {exc}\n{traceback.format_exc()}")
            await asyncio.sleep(2)


# ---------------------------------------------------------------------------
# JSON-RPC handlers
# ---------------------------------------------------------------------------


async def handle_enqueue_job(params: dict, req_id: str):
    """Enqueue a new job via JSON-RPC."""
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
        await loop.run_in_executor(None, enqueue_job, rfp_id, json.dumps(job_data))
        emit_result(
            {"success": True, "message": f"Job enqueued for RFP {rfp_id}"},
            req_id,
        )
    except Exception as e:
        logger.error(f"SQLite insert failed: {e}")
        emit_error_response(str(e), req_id)


# ---------------------------------------------------------------------------
# Main IPC loop
# ---------------------------------------------------------------------------


async def serve():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, init_db)
    worker_task = asyncio.create_task(run_worker())

    logger.info("Worker JSON-RPC Server started over stdin/stdout.")
    emit_ready()

    active_tasks: set = set()
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

                line_str = line.decode("utf-8").strip()
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
                            "req_id": req_id,
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
        logger.info("Worker JSON-RPC Server gracefully shutdown.")


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
