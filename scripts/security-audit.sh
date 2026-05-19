#!/bin/bash
# Security audit script for Sentinel
# Runs both npm and cargo security audits

set -e

echo "🔍 Running npm security audit..."
npm audit --depth 3 --production=false || true

echo ""
echo "🔍 Running cargo security audit for Rust dependencies..."
cd src-tauri
cargo audit --deny warnings || true
cd ..

echo ""
echo "✅ Security audit complete!"
