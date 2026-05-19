FROM node:20-alpine AS builder
WORKDIR /app

# Copy package.json of the sidecar from the root context
COPY sidecars/hunter/package.json sidecars/hunter/package-lock.json* ./sidecars/hunter/

# Install dependencies in the sidecar directory
WORKDIR /app/sidecars/hunter
RUN npm install --legacy-peer-deps

# Go back to root to copy source files and shared proto
WORKDIR /app
COPY sidecars/hunter ./sidecars/hunter
COPY proto ./proto

# Build the sidecar
WORKDIR /app/sidecars/hunter
RUN npm run build

# Production stage
FROM node:20-alpine
WORKDIR /app

# Mirror the directory structure so relative paths work!
COPY --from=builder /app/sidecars/hunter/dist ./sidecars/hunter/dist
COPY --from=builder /app/sidecars/hunter/node_modules ./sidecars/hunter/node_modules
COPY --from=builder /app/sidecars/hunter/package.json ./sidecars/hunter/
COPY --from=builder /app/proto ./proto

ENV NODE_ENV=production
EXPOSE 50051
# Run from the mirrored directory
CMD ["node", "sidecars/hunter/dist/server.js"]
