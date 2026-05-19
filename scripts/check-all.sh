#!/bin/bash
# Comprehensive linting and type checking script for Sentinel

set -e

echo "📋 Running TypeScript type check..."
npm run type-check

echo ""
echo "🎨 Running ESLint..."
npm run lint

echo ""
echo "✨ Checking code formatting with Prettier..."
npm run format:check

echo ""
echo "🧪 Running tests..."
npm run test:all

echo ""
echo "🦀 Running Rust clippy..."
cd src-tauri
cargo clippy --all-targets --all-features -- -D warnings
cargo fmt --all -- --check
cd ..

echo ""
echo "🔒 Running security audit..."
bash scripts/security-audit.sh

echo ""
echo "✅ All checks passed!"
