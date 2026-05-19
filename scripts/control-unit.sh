#!/usr/bin/env bash

set -e

echo "Starting Sentinel Control Unit..."

# 1. Start Docker Compose infrastructure
echo "[1/4] Bringing up infrastructure via docker-compose..."
docker compose up -d

echo "[2/4] Waiting for Ollama (Port 11434)..."
until curl -s -f http://127.0.0.1:11434 > /dev/null; do
    echo "  -> Waiting for Ollama..."
    sleep 2
done
echo "  [✓] Ollama is ONLINE"

echo "[3/4] Waiting for ChromaDB (Port 8000)..."
until curl -s -f http://127.0.0.1:8000/api/v2/heartbeat > /dev/null; do
    echo "  -> Waiting for ChromaDB..."
    sleep 2
done
echo "  [✓] ChromaDB is ONLINE"

# Hunter is on 50051, RAG is on 50052
# Since they are gRPC we can just check if port is open using nc
echo "[4/4] Waiting for Sidecars (Ports 50051, 50052)..."
until nc -z 127.0.0.1 50051; do
    echo "  -> Waiting for Hunter Engine..."
    sleep 2
done
echo "  [✓] Hunter Engine is ONLINE"

until nc -z 127.0.0.1 50052; do
    echo "  -> Waiting for RAG Engine..."
    sleep 2
done
echo "  [✓] RAG Engine is ONLINE"

echo "====================================="
echo "ALL SYSTEMS GREEN. SENTINEL IS READY."
echo "====================================="
