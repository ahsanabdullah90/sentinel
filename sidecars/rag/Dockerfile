FROM node:20-alpine AS builder
WORKDIR /app

# Copy package.json of the sidecar from the root context
COPY sidecars/rag/package.json sidecars/rag/package-lock.json* ./sidecars/rag/

# Install dependencies in the sidecar directory
WORKDIR /app/sidecars/rag
RUN npm install --legacy-peer-deps

# Go back to root to copy source files and shared proto
WORKDIR /app
COPY sidecars/rag ./sidecars/rag
COPY proto ./proto

# Build the sidecar
WORKDIR /app/sidecars/rag
RUN npm run build

# Production stage
FROM node:20-alpine
WORKDIR /app

# Mirror the directory structure so relative paths work!
COPY --from=builder /app/sidecars/rag/dist ./sidecars/rag/dist
COPY --from=builder /app/sidecars/rag/node_modules ./sidecars/rag/node_modules
COPY --from=builder /app/sidecars/rag/package.json ./sidecars/rag/
COPY --from=builder /app/proto ./proto

ENV NODE_ENV=production
EXPOSE 50052
# Run from the mirrored directory
CMD ["node", "sidecars/rag/dist/server.js"]
