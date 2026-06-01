# Module: CI/CD

## Purpose
Automates the build, test, and validation processes for the Sentinel RFP Agent using GitHub Actions.

## Language & Runtime
- **Platform**: GitHub Actions
- **Workflow**: `.github/workflows/ci.yml`

## Internal Structure
- **Build Job**: Compiles Rust (Tauri) and builds the frontend (Vite).
- **Test Job**: Runs Vitest (frontend), Pytest (sidecars), and Cargo Test (Rust).
- **Lint Job**: Runs ESLint, Clippy, and Flake8/Black.

## Dependencies
- **Actions**: `actions/checkout`, `actions/setup-node`, `actions-rs/toolchain`, `actions/setup-python`.

## Configuration
Uses GitHub Secrets for any sensitive build environment variables if applicable.
