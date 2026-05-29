# Module: Gap Engine Sidecar

## Purpose
The Gap Engine sidecar performs compliance and requirement gap analysis on RFP documents. It identifies missing information or potential risks in RFP specifications compared to internal capabilities or compliance standards.

## Language & Runtime
- **Language**: Python 3.11
- **Framework**: gRPC (asyncio)
- **Key Libraries**: grpcio, opentelemetry
- **Entry point**: `sidecars/gap-engine/src_py/server.py`

## Public Interface
### gRPC Service: `GapEngineService`
- `AnalyzeGaps(GapRequest) returns (GapResponse)`: Analyzes an RFP (identified by ID) and returns a list of detected gaps.

## Internal Structure
- `server.py`: gRPC server and `AnalyzeGaps` handler (currently uses mock stubs).
- `gap_engine.py`: Core analysis logic (placeholder implementation).

## Dependencies
### Internal
| Module | How consumed |
|--------|-------------|
| Proto Contracts | Python stubs generated from `gap_engine.proto` |

### External
| Package | Version | Purpose |
|---------|---------|---------|
| grpcio | 1.62.1 | gRPC runtime |

## Configuration
| Variable | Required | Default | Crash if missing? |
|----------|----------|---------|-------------------|
| PORT | No | 50054 | No |

## Data Flow
gRPC Request (`rfp_id`) -> Validation -> `AnalyzeGaps` handler -> Mock/LLM Analysis -> gRPC Response (`GapResponse`).

## Startup Sequence
1. Telemetry and logging initialization.
2. gRPC server setup with tracing and optional auth interceptors.
3. Server starts on port 50054.
