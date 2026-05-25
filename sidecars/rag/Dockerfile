FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    grpcio \
    grpcio-tools \
    "protobuf>=5.26.1"

# Copy source code and proto
COPY sidecars/rag/src_py ./sidecars/rag/src_py
COPY proto ./proto

# Patch generated proto files to bypass the protobuf runtime version check
RUN sed -i '/ValidateProtobufRuntimeVersion/,/^)/d' proto/*_pb2.py && \
    sed -i 's/from proto import/import/g' proto/*_pb2_grpc.py

ENV PORT=50052
EXPOSE 50052

CMD ["python", "-m", "sidecars.rag.src_py.server"]
