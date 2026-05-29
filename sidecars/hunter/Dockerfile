# Multi-stage build for Hunter sidecar
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir \
    grpcio-tools==1.62.1 \
    protobuf==4.25.3

COPY proto/ ./proto/

# Compile the protobuf definitions dynamically inside proto directory to avoid namespace conflicts
WORKDIR /app/proto
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. *.proto

# Production runner image
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy AS runner

WORKDIR /app

# Create secure non-root user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m -s /sbin/nologin appuser

# Copy and install pinned requirements
COPY sidecars/hunter/requirements.txt ./sidecars/hunter/
RUN pip install --no-cache-dir -r sidecars/hunter/requirements.txt

# Setup Playwright environment directories and permissions for non-root user
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p /ms-playwright && chown -R appuser:appuser /ms-playwright

# Install Playwright browser
RUN playwright install chromium

# Copy generated proto files from builder stage
COPY --from=builder --chown=appuser:appuser /app/proto ./proto

# Copy sources with proper ownership
COPY --chown=appuser:appuser sidecars/hunter/src_py ./sidecars/hunter/src_py

# Set PYTHONPATH environment variable to resolve modules cleanly
ENV PYTHONPATH="/app:/app/proto"

# Switch to non-root user
USER appuser

ENV PORT=50051
EXPOSE 50051

CMD ["python", "-m", "sidecars.hunter.src_py.server"]
