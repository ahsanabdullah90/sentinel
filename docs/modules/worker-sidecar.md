# Module: Worker Sidecar

## Purpose
The Worker sidecar manages asynchronous background jobs using a Redis-backed queue. It provides a gRPC interface to enqueue jobs and runs a continuous background loop to process them. It is used for tasks like RFP normalization and data enrichment.

## Language & Runtime
- **Language**: Python 3.11
- **Framework**: gRPC (asyncio)
- **Key Libraries**: redis, grpcio, opentelemetry
- **Entry point**: `sidecars/worker/src_py/worker.py`

## Public Interface
### gRPC Service: `WorkerService`
- `EnqueueJob(JobRequest) returns (JobResponse)`: Pushes a job payload onto the Redis `jobs` list.

## Internal Structure
- `worker.py`: Combined gRPC server and background worker loop.
- `process_job`: Logic for validating, normalizing, and hashing job data.
- `run_worker`: Redis `BLPOP` loop for job consumption.

## Dependencies
### Internal
| Module | How consumed |
|--------|-------------|
| Proto Contracts | Python stubs generated from `worker.proto` (located in the same directory) |

### External
| Package | Version | Purpose |
|---------|---------|---------|
| redis | 5.0.4 | Job queue and result storage |
| grpcio | 1.62.1 | gRPC runtime |

## Configuration
| Variable | Required | Default | Crash if missing? |
|----------|----------|---------|-------------------|
| PORT | No | 50053 | No |
| REDIS_URL | Yes | redis://localhost:6379 | No (logs error) |

## Data Flow
- **Enqueue**: gRPC `EnqueueJob` -> Redis `RPUSH` to `jobs`.
- **Process**: Redis `BLPOP` from `jobs` -> `process_job` -> Redis `SET` to `results:<id>`.

## Startup Sequence
1. Telemetry setup.
2. Background worker task (`run_worker`) is spawned via `asyncio.create_task`.
3. gRPC server starts on port 50053.
4. Signal handlers for `SIGTERM`/`SIGINT` are registered for graceful shutdown.
