# Module: Infrastructure

## Purpose
This module encompasses the deployment, configuration, and backing services required to run the Sentinel RFP Agent in a containerized environment.

## Language & Runtime
- **Orchestration**: Docker Compose
- **Backing Services**: Ollama (LLM), ChromaDB (Vector DB), Redis (Queue), Jaeger (Tracing).

## Internal Structure
- `docker-compose.yml`: Defines the multi-container application.
- `config/config.yaml`: Shared application configuration (e.g., portal presets).
- `.env.example`: Template for required environment variables.

## Shared Resources
| Resource | Purpose | Used By |
|----------|---------|---------|
| Ollama | LLM Inference | RAG, Hunter |
| ChromaDB | Vector Storage | RAG |
| Redis | Job Queue | Worker |
| Jaeger | Tracing | All modules |
| SQLite | Primary Metadata | Tauri Shell |

## Configuration
Key environment variables defined in `.env.example`:
- `ENV`: development/production toggle.
- `API_KEY`: gRPC authentication token.
- `CHROMA_AUTH_TOKEN`: Security for ChromaDB.
- `REDIS_URL`: Redis connection string with password.
- `DATABASE_URL`: Path to `sentinel.db`.

## Data Flow
Tauri Shell (Host) -> gRPC (Localhost Ports) -> Sidecars (Docker Containers) -> Internal Network -> Backing Services (Docker Containers).

## Startup Sequence
1. `docker compose up` starts backing services and sidecars.
2. Backing services (Chroma, Redis, Ollama, Jaeger) initialize.
3. Sidecars wait for backing services to be healthy (via `depends_on` and `healthcheck`).
4. Tauri application is launched separately and connects to the sidecars via mapped host ports.
