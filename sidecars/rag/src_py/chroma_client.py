import os
import logging
import urllib.request
import urllib.error
import json

logger = logging.getLogger("rag.chroma_client")

class ChromaClient:
    def __init__(self):
        # Read from environment variable passed by Docker-compose, fallback to localhost
        self.base_url = os.environ.get("CHROMA_URL", "http://localhost:8000")
        logger.info(f"Initialized ChromaClient pointing to: {self.base_url}")

    async def check_health(self) -> bool:
        try:
            # Synchronous request in thread executor to prevent blocking async loop
            import asyncio
            def run_heartbeat():
                try:
                    url = f"{self.base_url}/api/v1/heartbeat"
                    with urllib.request.urlopen(url, timeout=2.0) as response:
                        if response.status == 200:
                            data = json.loads(response.read().decode())
                            return isinstance(data, dict) or isinstance(data, float) or isinstance(data, int)
                except Exception:
                    return False
                return False

            return await asyncio.get_running_loop().run_in_executor(None, run_heartbeat)
        except Exception:
            return False

    class PythonChromaCollection:
        def __init__(self, base_url: str, collection_id: str, name: str):
            self.base_url = base_url
            self.collection_id = collection_id
            self.name = name

        async def upsert(self, ids: list, documents: list, metadatas: list):
            import asyncio
            def run_upsert():
                url = f"{self.base_url}/api/v1/collections/{self.collection_id}/upsert"
                payload = {
                    "ids": ids,
                    "documents": documents,
                    "metadatas": metadatas
                }
                headers = {"Content-Type": "application/json"}
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                try:
                    with urllib.request.urlopen(req, timeout=5.0) as response:
                        return response.status == 200
                except Exception as e:
                    logger.error(f"Chroma upsert failed: {str(e)}")
                    raise

            await asyncio.get_running_loop().run_in_executor(None, run_upsert)

    async def get_or_create_collection(self, name: str) -> PythonChromaCollection:
        import asyncio
        def run_get_or_create():
            url = f"{self.base_url}/api/v1/collections"
            # Get or create endpoint
            payload = {
                "name": name,
                "metadata": {"hnsw:space": "cosine"},
                "get_or_create": True
            }
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
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
        return self.PythonChromaCollection(self.base_url, collection_id, name)
