FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "protobuf>=5.26.1"

# Copy source code
COPY sidecars/gap-engine/src_py ./sidecars/gap-engine/src_py

CMD ["python", "-m", "sidecars.gap-engine.src_py.gap_engine", "default-rfp"]
