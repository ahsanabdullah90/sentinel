"""Chroma Client Module

Provides an async wrapper around ChromaDB's native persistent client for storing
and querying document embeddings entirely locally.
"""

import asyncio
import os
import logging
from typing import List, Dict, Optional

import chromadb

from sidecars.shared.llm_client import GoogleEmbeddingFunction

logger = logging.getLogger("rag.chroma_client")

DB_PATH = os.environ.get(
    "CHROMA_DATA_PATH",
    os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "chroma_data"
    ),
)


class ChromaClient:
    """Lightweight async wrapper for ChromaDB PersistentClient.

    The underlying chromadb client is lazily initialized on first use
    via ``_ensure_client``.
    """

    def __init__(self, google_api_key: str = ""):
        self._client: Optional[chromadb.PersistentClient] = None
        self.google_api_key = google_api_key or os.environ.get("GOOGLE_API_KEY", "")
        self._use_google_embeddings = bool(
            (os.environ.get("LLM_PROVIDER", "google") == "google") and self.google_api_key
        )

    def _ensure_client(self) -> chromadb.PersistentClient:
        """Initialize the embedded ChromaDB client if not already done."""
        if self._client is None:
            self._client = chromadb.PersistentClient(path=DB_PATH)
            logger.info(
                f"Initialized ChromaClient embedded at: {DB_PATH}"
            )
        return self._client

    async def check_health(self) -> bool:
        """Return True if the DB is ready (always true for embedded)."""
        def run_heartbeat():
            try:
                self._ensure_client().heartbeat()
                return True
            except Exception as e:
                logger.error(f"Heartbeat check failed: {e}")
                return False

        return await asyncio.get_running_loop().run_in_executor(
            None, run_heartbeat
        )

    async def list_collections(self) -> List[Dict[str, str]]:
        """List all collections in ChromaDB."""
        def run_list():
            try:
                client = self._ensure_client()
                return [
                    {"name": c.name} for c in client.list_collections()
                ]
            except Exception as e:
                logger.error(
                    f"Chroma list_collections failed: {str(e)}"
                )
                raise RuntimeError(
                    f"Failed to list ChromaDB collections: {str(e)}"
                )

        return await asyncio.get_running_loop().run_in_executor(
            None, run_list
        )

    async def get_or_create_collection(
        self, name: str
    ) -> "PythonChromaCollection":
        """Get or create a collection by *name* and return a handle."""
        def run_get_or_create():
            try:
                client = self._ensure_client()
                kwargs = {"metadata": {"hnsw:space": "cosine"}}
                if self._use_google_embeddings:
                    kwargs["embedding_function"] = GoogleEmbeddingFunction(self.google_api_key)
                col = client.get_or_create_collection(name=name, **kwargs)
                return col
            except Exception as e:
                logger.error(
                    f"Chroma get_or_create_collection failed: {str(e)}"
                )
                raise RuntimeError(
                    f"Chroma DB connection failed: {str(e)}"
                )

        col = await asyncio.get_running_loop().run_in_executor(
            None, run_get_or_create
        )
        return self.PythonChromaCollection(col)

    class PythonChromaCollection:
        """Represents a single ChromaDB collection."""

        def __init__(self, collection):
            self.collection = collection
            self.name = collection.name

        async def upsert(
            self,
            ids: list,
            documents: list,
            metadatas: list,
        ):
            """Upsert documents into the collection."""
            def run_upsert():
                try:
                    self.collection.upsert(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas,
                    )
                except Exception as e:
                    logger.error(f"Chroma upsert failed: {str(e)}")
                    raise RuntimeError(
                        f"Chroma upsert execution failed: {str(e)}"
                    )

            await asyncio.get_running_loop().run_in_executor(
                None, run_upsert
            )

        async def query(
            self, query_texts: list, n_results: int = 3
        ) -> dict:
            """Query the collection using raw text queries."""
            def run_query():
                try:
                    results = self.collection.query(
                        query_texts=query_texts,
                        n_results=n_results,
                        include=["documents", "metadatas", "distances"],
                    )
                    return results
                except Exception as e:
                    logger.error(f"Chroma query failed: {str(e)}")
                    raise RuntimeError(
                        f"Chroma query execution failed: {str(e)}"
                    )

            return await asyncio.get_running_loop().run_in_executor(
                None, run_query
            )
