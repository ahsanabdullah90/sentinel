# Multi-stage build for Gap Engine
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

# Create a secure, non-root user and group
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m -s /sbin/nologin appuser

# Copy and install pinned requirements
COPY sidecars/gap-engine/requirements.txt ./sidecars/gap-engine/
RUN pip install --no-cache-dir -r sidecars/gap-engine/requirements.txt

# Copy generated proto files from builder stage
COPY --from=builder --chown=appuser:appuser /app/proto ./proto

# Copy sources with proper ownership
COPY --chown=appuser:appuser sidecars/gap-engine/src_py ./sidecars/gap-engine/src_py

# Set PYTHONPATH environment variable to resolve modules cleanly
ENV PYTHONPATH="/app:/app/proto"

# Switch to non-root user
USER appuser

ENV PORT=50054
EXPOSE 50054

CMD ["python", "-m", "sidecars.gap-engine.src_py.server"]
