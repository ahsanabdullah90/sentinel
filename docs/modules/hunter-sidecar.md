# Module: Hunter Sidecar

## Purpose
The Hunter sidecar is responsible for discovering and scraping RFP opportunities from various web portals. It uses Playwright for headless browser automation and a recipe-driven architecture with adapters for specific sites. It supports both static HTML parsing and dynamic browser-based scraping.

## Language & Runtime
- **Language**: Python 3.11
- **Framework**: gRPC (asyncio), Playwright
- **Key Libraries**: grpcio, playwright, pydantic, opentelemetry
- **Entry point**: `sidecars/hunter/src_py/server.py`

## Public Interface
### gRPC Service: `HunterService`
- `Detect(DetectRequest) returns (stream DetectResponse)`: Analyzes a URL to determine if it's a valid RFP portal and returns a detection report.
- `Hunt(HuntRequest) returns (stream HuntResponse)`: Performs the actual scraping job for a given portal and streams back discovered opportunities and progress events.

## Internal Structure
- `server.py`: gRPC server implementation and service handlers.
- `scraper_engine.py`: Core scraping logic using Playwright.
- `portal_runner.py`: Orchestrates the hunting process for a specific portal.
- `portal_analyzer.py`: Heuristics for detecting portal types and search inputs.
- `rate_limiter.py`: Token-bucket rate limiter with exponential back-off and CAPTCHA handling.
- `models.py`: Pydantic models for configuration (`PortalConfig`) and data (`RFPOpportunity`).
- `adapters/`: Site-specific logic (e.g., `brightspyre.py`) and a `generic.py` fallback.
- `utils/search_detector.py`: JS-based heuristics for finding search fields.

## Dependencies
### Internal
| Module | How consumed |
|--------|-------------|
| Proto Contracts | Python stubs generated from `hunter.proto` |

### External
| Package | Version | Purpose |
|---------|---------|---------|
| playwright | 1.44.0 | Browser automation |
| grpcio | 1.62.1 | gRPC runtime |
| pydantic | 2.x | Data validation |

## Configuration
| Variable | Required | Default | Crash if missing? |
|----------|----------|---------|-------------------|
| PORT | No | 50051 | No |
| API_KEY | Yes (prod) | sentinel-secret-api-key | No (uses fallback) |
| ENV | No | development | No |
| RUNNING_IN_DOCKER| No | false | No |

## Data Flow
gRPC Request -> `HunterServiceServicer` -> `PortalRunner` -> `ScraperEngine` -> Playwright (Web) -> `RFPOpportunity` -> gRPC Stream (JSON payload).

## Startup Sequence
1. `setup_telemetry` initializes OpenTelemetry.
2. `HunterServiceServicer` is instantiated.
3. gRPC server starts, optionally with `AuthInterceptor` in production.
4. Server binds to port (default 50051) and waits for requests.
