"""Jobs Module for Worker Sidecar

Provides pure business logic for job processing: input normalization,
content hashing for deduplication, and result formatting.
"""

import hashlib
import json
import logging
import time
from typing import Dict, Any

from sidecars.worker.src_py.db import save_result

logger = logging.getLogger("worker.jobs")


def normalize_job_data(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize job payload keys and values by stripping whitespace.

    Args:
        job_data: Raw job payload dictionary.

    Returns:
        Normalized dictionary with trimmed keys and string values.
    """
    normalized: Dict[str, Any] = {}
    for key, value in job_data.items():
        norm_key = key.strip()
        if isinstance(value, str):
            normalized[norm_key] = value.strip()
        else:
            normalized[norm_key] = value
    return normalized


def compute_content_hash(data: Dict[str, Any]) -> str:
    """Compute a SHA-256 content hash for deduplication.

    Args:
        data: The normalized job data.

    Returns:
        First 16 hex characters of the SHA-256 hash.
    """
    content_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(content_str.encode()).hexdigest()[:16]


def format_result(
    normalized: Dict[str, Any], content_hash: str
) -> Dict[str, Any]:
    """Format the processing result with metadata.

    Args:
        normalized: Normalized job data.
        content_hash: Deduplication hash.

    Returns:
        Result dictionary with processing metadata.
    """
    return {
        **normalized,
        "contentHash": content_hash,
        "processedAt": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        ),
        "workerVersion": "1.0.0",
        "status": "processed",
    }


async def process_job(
    job_id: int, job_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Process a single job: normalize, hash, and persist the result.

    Args:
        job_id: The job's primary key.
        job_data: Parsed job payload.

    Returns:
        The processing result dictionary.

    Raises:
        ValueError: If the payload is missing an ``rfpId`` field.
    """
    rfp_id = job_data.get("rfpId") or job_data.get("rfp_id")
    if not rfp_id:
        raise ValueError("Job payload is missing 'rfpId'")

    logger.info(f"Processing job {job_id} for RFP: {rfp_id}")

    normalized = normalize_job_data(job_data)
    content_hash = compute_content_hash(normalized)
    result = format_result(normalized, content_hash)

    def _persist():
        save_result(job_id, json.dumps(result), "completed")

    import asyncio

    await asyncio.get_running_loop().run_in_executor(None, _persist)
    logger.info(
        f"Job {job_id} completed for RFP: {rfp_id} (hash={content_hash})"
    )
    return result
