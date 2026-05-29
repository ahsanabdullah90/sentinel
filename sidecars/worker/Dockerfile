# Multi-stage build for Worker sidecar
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir \
    grpcio-tools==1.62.1 \
    protobuf==4.25.3

COPY proto/ ./proto/

# Compile the protobuf definitions dynamically to match compiler exactly
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/*.proto

# Production runner image
FROM python:3.11-slim AS runner

WORKDIR /app

# Create secure non-root user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m -s /sbin/nologin appuser

# Copy and install pinned requirements
COPY sidecars/worker/requirements.txt ./sidecars/worker/
RUN pip install --no-cache-dir -r sidecars/worker/requirements.txt

# Copy generated proto files from builder stage
COPY --from=builder --chown=appuser:appuser /app/proto ./proto

# Copy sources with proper ownership
COPY --chown=appuser:appuser sidecars/worker/src_py ./sidecars/worker/src_py

# Set PYTHONPATH environment variable to resolve modules cleanly
ENV PYTHONPATH="/app:/app/proto"

USER appuser

ENV PORT=50053
EXPOSE 50053

CMD ["python", "-m", "sidecars.worker.src_py.worker"]
