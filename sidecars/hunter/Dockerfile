FROM python:3.11-slim

# Install system dependencies for Playwright and Chromium
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python packages directly
RUN pip install --no-cache-dir \
    grpcio==1.62.2 \
    grpcio-tools==1.62.2 \
    protobuf>=5.26.1,<6.0.0dev \
    playwright \
    google-generativeai \
    redis

# Install Playwright browsers and system dependencies
RUN playwright install chromium --with-deps

# Copy source code and compiled proto
COPY sidecars/hunter/src_py ./sidecars/hunter/src_py
COPY proto ./proto

ENV PORT=50051
EXPOSE 50051

CMD ["python", "-m", "sidecars.hunter.src_py.server"]
