#!/usr/bin/env bash

set -e

echo "Starting Sentinel Control Unit..."

# Detect if Ollama is running natively on the host
OLLAMA_NATIVE=false
if curl -s -f http://127.0.0.1:11434 > /dev/null; then
    echo "  [✓] Detected Ollama running NATIVELY on the host."
    OLLAMA_NATIVE=true
    export OLLAMA_URL=http://host.docker.internal:11434
    export OLLAMA_PORT_MAP=11435:11434  # Bind containerized Ollama to 11435 to avoid port collision
else
    echo "  [-] Ollama not detected on host. Will use containerized Ollama."
    export OLLAMA_URL=http://ollama:11434
    export OLLAMA_PORT_MAP=11434:11434
fi

# 1. Start Docker Compose infrastructure
echo "[1/4] Bringing up infrastructure via docker-compose..."
docker compose up -d

echo "[2/4] Waiting for Ollama..."
if [ "$OLLAMA_NATIVE" = "true" ]; then
    echo "  [✓] Ollama is ONLINE (Native Host)"
else
    until curl -s -f http://127.0.0.1:11434 > /dev/null; do
        echo "  -> Waiting for containerized Ollama..."
        sleep 2
    done
    echo "  [✓] Ollama is ONLINE (Containerized)"
fi

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
