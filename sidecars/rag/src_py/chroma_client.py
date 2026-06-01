"""Chroma Client Module

Provides an async wrapper around ChromaDB's native persistent client for storing
and querying document embeddings entirely locally.
"""

import asyncio
import os
import logging
import chromadb

logger = logging.getLogger("rag.chroma_client")

DB_PATH = os.environ.get("CHROMA_DATA_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "..", "chroma_data"))

class ChromaClient:
    """Lightweight async wrapper for ChromaDB PersistentClient."""

    def __init__(self):
        # We initialize the client synchronously, but operations will be run in executor
        self.client = chromadb.PersistentClient(path=DB_PATH)
        logger.info(f"Initialized ChromaClient embedded at: {DB_PATH}")

    async def check_health(self) -> bool:
        """Return True if the DB is ready (always true for embedded, but we check heartbeat)."""
        def run_heartbeat():
            try:
                self.client.heartbeat()
                return True
            except Exception as e:
                logger.debug(f"Heartbeat check failed: {e}")
                return False

        return await asyncio.get_running_loop().run_in_executor(None, run_heartbeat)

    async def list_collections(self) -> list:
        """List all collections in ChromaDB."""
        def run_list():
            try:
                return [{"name": c.name} for c in self.client.list_collections()]
            except Exception as e:
                logger.error(f"Chroma list_collections failed: {str(e)}")
                return []

        return await asyncio.get_running_loop().run_in_executor(None, run_list)


    class PythonChromaCollection:
        """Represents a single ChromaDB collection."""

        def __init__(self, collection):
            self.collection = collection
            self.name = collection.name

        async def upsert(self, ids: list, documents: list, metadatas: list):
            """Upsert documents into the collection."""
            def run_upsert():
                try:
                    self.collection.upsert(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas
                    )
                    return True
                except Exception as e:
                    logger.error(f"Chroma upsert failed: {str(e)}")
                    raise

            await asyncio.get_running_loop().run_in_executor(None, run_upsert)

        async def query(self, query_texts: list, n_results: int = 3) -> dict:
            """Query the collection using raw text queries."""
            def run_query():
                try:
                    results = self.collection.query(
                        query_texts=query_texts,
                        n_results=n_results,
                        include=["documents", "metadatas", "distances"]
                    )
                    return results
                except Exception as e:
                    logger.error(f"Chroma query failed: {str(e)}")
                    raise

            return await asyncio.get_running_loop().run_in_executor(None, run_query)

    async def get_or_create_collection(self, name: str) -> PythonChromaCollection:
        """Get or create a collection by *name* and return a handle."""
        def run_get_or_create():
            try:
                col = self.client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"}
                )
                return col
            except Exception as e:
                logger.error(f"Chroma get_or_create_collection failed: {str(e)}")
                raise RuntimeError(f"Chroma DB connection failed: {str(e)}")

        col = await asyncio.get_running_loop().run_in_executor(None, run_get_or_create)
        return self.PythonChromaCollection(col)
