# Module: Scripts

## Purpose
A collection of shell and Python scripts for system setup, maintenance, security auditing, and runtime control.

## Language & Runtime
- **Languages**: Bash, Python
- **Key Scripts**:
  - `setup.sh`: Main installation and environment preparation script.
  - `scripts/control-unit.sh`: Orchestration script called during system bootstrap.
  - `scripts/security-audit.sh`: Automated scanner for secrets and insecure configurations.
  - `scripts/pre-check.sh`: Dependency and environment validation.
  - `scripts/ollama_proxy.py`: Proxy for local Ollama communication.

## Internal Structure
- `scripts/`: Utility scripts for various lifecycle stages.
- `setup.sh`: Root-level entry point for environment setup.

## Configuration
Most scripts read from `.env` or use default values for local development.

## Startup Sequence
`setup.sh` -> `pre-check.sh` -> `docker compose up` -> Tauri app launch.
