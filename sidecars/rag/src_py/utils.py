"""Utility Module for RAG Sidecar

Provides shared utilities for Docker loopback resolution and common helpers.
"""

import os
import logging
from urllib.parse import urlparse

logger = logging.getLogger("rag.utils")


def resolve_ollama_url(base_url: str = None) -> str:
    """Resolve the Ollama URL, handling Docker loopback translation.

    When running inside a Docker container, ``localhost`` and ``127.0.0.1``
    refer to the container itself, not the host.  This function translates
    those addresses to ``host.docker.internal`` or the container's gateway IP.

    Args:
        base_url: The configured Ollama URL (default from env or localhost).

    Returns:
        The resolved URL string.
    """
    if base_url is None:
        base_url = os.environ.get(
            "OLLAMA_URL", "http://localhost:11434"
        )

    if os.environ.get("RUNNING_IN_DOCKER") != "true":
        return base_url

    parsed = urlparse(base_url)
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        return base_url

    use_resolved = False
    if parsed.hostname == "host.docker.internal":
        try:
            import socket

            socket.gethostbyname("host.docker.internal")
            use_resolved = True
        except Exception:
            pass

    if not use_resolved:
        gateway_ip = "172.19.0.1"
        try:
            with open("/proc/net/route") as f:
                for line in f:
                    fields = line.strip().split()
                    if len(fields) >= 3 and fields[1] == "00000000":
                        val = fields[2]
                        ip_parts = [
                            str(int(val[i : i + 2], 16))
                            for i in range(6, -1, -2)
                        ]
                        gateway_ip = ".".join(ip_parts)
                        break
        except Exception:
            pass

        netloc = (
            f"{gateway_ip}:{parsed.port}"
            if parsed.port
            else gateway_ip
        )
        return parsed._replace(netloc=netloc).geturl()

    return base_url
