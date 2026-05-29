FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    grpcio \
    grpcio-tools \
    "protobuf>=5.26.1" \
    redis \
    grpcio-health-checking

# Copy source code and proto
COPY sidecars/worker/src_py ./sidecars/worker/src_py
COPY proto ./proto

ENV PORT=50053
EXPOSE 50053

CMD ["python", "-m", "sidecars.worker.src_py.worker"]
