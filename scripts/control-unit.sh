#!/usr/bin/env bash

set -e

echo "Starting Sentinel Control Unit..."

# Respect user-configured host Ollama port, fallback to default 11434
OLLAMA_PORT=${OLLAMA_PORT:-11434}

# Kill any existing host proxy to prevent bind conflicts
pkill -f "python3 scripts/ollama_proxy.py" || true

# Detect if Ollama is running natively on the host
OLLAMA_NATIVE=false
if curl -s -f http://127.0.0.1:$OLLAMA_PORT > /dev/null; then
    echo "  [✓] Detected Ollama running NATIVELY on the host (port $OLLAMA_PORT)."
    OLLAMA_NATIVE=true
    export OLLAMA_URL=http://host.docker.internal:$OLLAMA_PORT
    export COMPOSE_PROFILES=""  # Do NOT spin up containerized Ollama (keep profile inactive)
else
    echo "  [-] Ollama not detected on port $OLLAMA_PORT. Will use containerized Ollama."
    export OLLAMA_URL=http://ollama:11434
    export COMPOSE_PROFILES="container-ollama"  # Spin up containerized Ollama
fi

# 1. Start Docker Compose infrastructure
echo "[1/4] Bringing up infrastructure via docker-compose..."
docker compose up -d

# Start transparent host proxy if native Ollama is detected to bypass loopback binding restriction
if [ "$OLLAMA_NATIVE" = "true" ]; then
    echo "  [→] Resolving Docker bridge gateway IP..."
    GATEWAY_IP=$(docker network inspect sentinel_sentinel-net -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}' 2>/dev/null || echo "172.19.0.1")
    echo "  [✓] Gateway IP resolved to: $GATEWAY_IP"
    echo "  [→] Starting transparent host-bound Ollama proxy on $GATEWAY_IP:$OLLAMA_PORT..."
    python3 scripts/ollama_proxy.py "$GATEWAY_IP" "$OLLAMA_PORT" "127.0.0.1" "$OLLAMA_PORT" > /tmp/sentinel_ollama_proxy.log 2>&1 &
    echo "  [✓] Host-bound Ollama proxy is running in background (PID: $!). Logs at /tmp/sentinel_ollama_proxy.log"
fi

echo "[2/4] Waiting for Ollama..."
if [ "$OLLAMA_NATIVE" = "true" ]; then
    echo "  [✓] Ollama is ONLINE (Native Host on port $OLLAMA_PORT)"
else
    until curl -s -f http://127.0.0.1:11434 > /dev/null; do
        echo "  -> Waiting for containerized Ollama..."
        sleep 2
    done
    echo "  [✓] Ollama is ONLINE (Containerized)"
fi

echo "[3/4] Waiting for ChromaDB (sentinel-chromadb-1)..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' sentinel-chromadb-1 2>/dev/null)" = "healthy" ]; do
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
