FROM python:3.11-slim

# Install system dependencies for Playwright and Chromium
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python packages directly
RUN pip install --no-cache-dir \
    grpcio \
    grpcio-tools \
    "protobuf>=5.26.1" \
    playwright \
    google-generativeai \
    redis \
    grpcio-health-checking

# Install Playwright browsers and system dependencies
RUN playwright install chromium --with-deps

# Copy source code and compiled proto
COPY sidecars/hunter/src_py ./sidecars/hunter/src_py
COPY proto ./proto

# Patch generated proto files to bypass the protobuf runtime version check
RUN sed -i '/ValidateProtobufRuntimeVersion/,/^)/d' proto/*_pb2.py && \
    sed -i 's/from proto import/import/g' proto/*_pb2_grpc.py

ENV PORT=50051
EXPOSE 50051

CMD ["python", "-m", "sidecars.hunter.src_py.server"]
