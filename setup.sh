#!/usr/bin/env bash
set -e

echo "=== Installing front‑end dependencies ==="
npm ci

echo "=== Installing hunter side‑car ==="
npm run hunter:install

echo "=== Installing RAG side‑car dependencies ==="
cd sidecars/rag && npm install && cd ../..

echo "=== Installing system libraries (Debian/Ubuntu) ==="
sudo apt-get update && sudo apt-get install -y libsqlite3-dev

echo "=== Building side‑cars ==="
cd sidecars/hunter && npm run build
cd ../rag && npm run build
cd ../..

echo "=== Setup complete. You can now run the app: npm run tauri dev ==="
