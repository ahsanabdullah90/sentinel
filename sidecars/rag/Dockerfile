FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    grpcio==1.62.2 \
    grpcio-tools==1.62.2 \
    protobuf>=5.26.1,<6.0.0dev

# Copy source code and proto
COPY sidecars/rag/src_py ./sidecars/rag/src_py
COPY proto ./proto

ENV PORT=50052
EXPOSE 50052

CMD ["python", "-m", "sidecars.rag.src_py.server"]
