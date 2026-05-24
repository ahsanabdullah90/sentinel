import asyncio
import json
import os
import sys
import grpc
import chromadb
import ollama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from . import rag_pb2
from . import rag_pb2_grpc
from .document_parser import DocumentParser

class RagService(rag_pb2_grpc.RagServiceServicer):
    def __init__(self):
        self.parser = DocumentParser()
        # Connect to containerized ChromaDB
        host = os.getenv("CHROMA_HOST", "localhost")
        port = int(os.getenv("CHROMA_PORT", "8000"))
        print(f"Connecting to ChromaDB at {host}:{port}")
        self.chroma = chromadb.HttpClient(host=host, port=port)
        self.collection = self.chroma.get_or_create_collection("sentinel_knowledge")

        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        print(f"Connecting to Ollama at {ollama_url}")
        self.ollama_client = ollama.AsyncClient(host=ollama_url)

        # requested: chunks of ~500 tokens with 10% overlap
        # since token counting varies, we use character-based approximation (4 chars per token)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000, # ~500 tokens
            chunk_overlap=200 # 10%
        )

    async def Ingest(self, request, context):
        print(f"Ingesting document: {request.document_id}")

        # High-fidelity document parsing happens before this or content is passed directly
        # If content is empty but it's a file path, we'd parse here.
        # For the gRPC request, we assume content is already extracted text.

        chunks = self.splitter.split_text(request.content)

        for i, chunk in enumerate(chunks):
            try:
                response = await self.ollama_client.embeddings(model="nomic-embed-text", prompt=chunk)
                embedding = response['embedding']

                self.collection.add(
                    ids=[f"{request.document_id}_{i}"],
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[{"source": request.document_id}]
                )
            except Exception as e:
                print(f"Embedding error for chunk {i}: {e}")

        return rag_pb2.IngestResponse(status="ok")

    async def Query(self, request, context):
        print(f"Querying: {request.query}")
        try:
            query_response = await self.ollama_client.embeddings(model="nomic-embed-text", prompt=request.query)
            query_embedding = query_response['embedding']

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=3
            )

            context_text = "\n".join(results['documents'][0])
            return rag_pb2.QueryResponse(
                answer=f"Relevant information found: {context_text}",
                source_documents=json.dumps(results['metadatas'][0])
            )
        except Exception as e:
            print(f"Query error: {e}")
            return rag_pb2.QueryResponse(answer=f"Error: {str(e)}", source_documents="[]")

async def serve():
    server = grpc.aio.server()
    rag_pb2_grpc.add_RagServiceServicer_to_server(RagService(), server)
    port = os.getenv("PORT", "50052")
    server.add_insecure_port(f'[::]:{port}')
    print(f"RAG gRPC server starting on port {port}")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    # Ensure package-relative imports work
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    asyncio.run(serve())
