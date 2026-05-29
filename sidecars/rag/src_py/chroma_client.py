"""Chroma Client Module

Provides an async HTTP wrapper around ChromaDB's REST API for storing
and querying document embeddings.

The client reads ``CHROMA_URL`` from the environment (default
``http://localhost:8000``) and exposes health-check, collection
management, and upsert/query operations.
"""

import asyncio
import os
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger("rag.chroma_client")


class ChromaClient:
    """Lightweight async ChromaDB client using ``urllib``."""

    def __init__(self):
        self.base_url = os.environ.get("CHROMA_URL", "http://localhost:8000")
        self.auth_token = os.environ.get("CHROMA_AUTH_TOKEN", "")
        logger.info(f"Initialized ChromaClient pointing to: {self.base_url}")

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    async def check_health(self) -> bool:
        """Return ``True`` if the ChromaDB heartbeat endpoint is reachable."""
        def run_heartbeat():
            try:
                url = f"{self.base_url}/api/v1/heartbeat"
                req = urllib.request.Request(url, headers=self._get_headers(), method="GET")
                with urllib.request.urlopen(req, timeout=2.0) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode())
                        return isinstance(data, (dict, float, int))
            except Exception as e:
                logger.debug(f"Heartbeat check failed: {e}")
                return False
            return False

        return await asyncio.get_running_loop().run_in_executor(None, run_heartbeat)

    async def list_collections(self) -> list:
        """List all collections in ChromaDB."""
        def run_list():
            try:
                url = f"{self.base_url}/api/v1/collections"
                req = urllib.request.Request(url, headers=self._get_headers(), method="GET")
                with urllib.request.urlopen(req, timeout=5.0) as response:
                    if response.status == 200:
                        return json.loads(response.read().decode("utf-8"))
            except Exception as e:
                logger.error(f"Chroma list_collections failed: {str(e)}")
                return []
            return []

        return await asyncio.get_running_loop().run_in_executor(None, run_list)


    class PythonChromaCollection:
        """Represents a single ChromaDB collection."""

        def __init__(self, base_url: str, collection_id: str, name: str, auth_token: str = ""):
            self.base_url = base_url
            self.collection_id = collection_id
            self.name = name
            self.auth_token = auth_token

        def _get_headers(self) -> dict:
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            return headers

        async def upsert(self, ids: list, documents: list, metadatas: list):
            """Upsert documents into the collection."""
            def run_upsert():
                url = f"{self.base_url}/api/v1/collections/{self.collection_id}/upsert"
                payload = {
                    "ids": ids,
                    "documents": documents,
                    "metadatas": metadatas
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=self._get_headers(),
                    method="POST"
                )
                try:
                    with urllib.request.urlopen(req, timeout=5.0) as response:
                        return response.status == 200
                except Exception as e:
                    logger.error(f"Chroma upsert failed: {str(e)}")
                    raise

            await asyncio.get_running_loop().run_in_executor(None, run_upsert)

        async def query(self, query_texts: list, n_results: int = 3) -> dict:
            """Query the collection using raw text queries."""
            def run_query():
                url = f"{self.base_url}/api/v1/collections/{self.collection_id}/query"
                payload = {
                    "query_texts": query_texts,
                    "n_results": n_results,
                    "include": ["documents", "metadatas", "distances"]
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=self._get_headers(),
                    method="POST"
                )
                try:
                    with urllib.request.urlopen(req, timeout=5.0) as response:
                        if response.status == 200:
                            return json.loads(response.read().decode("utf-8"))
                except Exception as e:
                    logger.error(f"Chroma query failed: {str(e)}")
                    raise
                return {}

            return await asyncio.get_running_loop().run_in_executor(None, run_query)

    async def get_or_create_collection(self, name: str) -> PythonChromaCollection:
        """Get or create a collection by *name* and return a handle."""
        def run_get_or_create():
            url = f"{self.base_url}/api/v1/collections"
            payload = {
                "name": name,
                "metadata": {"hnsw:space": "cosine"},
                "get_or_create": True
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=self._get_headers(),
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=5.0) as response:
                    if response.status in (200, 201):
                        data = json.loads(response.read().decode("utf-8"))
                        return data["id"]
            except Exception as e:
                logger.error(f"Chroma get_or_create_collection failed: {str(e)}")
                raise RuntimeError(f"Chroma DB connection failed: {str(e)}")

        collection_id = await asyncio.get_running_loop().run_in_executor(None, run_get_or_create)
        return self.PythonChromaCollection(self.base_url, collection_id, name, self.auth_token)
