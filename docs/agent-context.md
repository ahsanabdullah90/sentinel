# Sentinel RFP Agent - Project Status & Agent Context

## 🎯 Purpose of this Document

This file serves as the definitive onboarding guide and context provider for any future AI agent, developer, or system deploying this application on a new machine (Linux, Windows, macOS). It details the architectural state, dependencies, setup instructions, and the current progress of the Sentinel RFP Agent project.

---

## 🏗️ Architectural Overview

Sentinel is a privacy-first, desktop application designed for automated Discovery and Drafting of RFPs. It uses a **multi-service architecture** to isolate responsibilities:

1. **Frontend (Tauri + React + Vite + TypeScript)**:
   - Provides the desktop GUI.
   - State managed via React Context (AppContext in `src/context/AppContext.tsx`).
   - Communicates with sidecars via gRPC and Rust IPC.
   - Built with TailwindCSS and custom Glassmorphic components.

2. **Backend (Rust - Tauri Core)**:
   - Manages desktop windowing and local filesystem permissions.
   - Contains SQLite database integration using `sqlx` and `tauri-plugin-sql`.
   - Initializes OpenTelemetry tracing.

3. **Sidecar: Hunter (Python)**:
   - Uses **Playwright (Python)** to scrape and navigate RFP portals.
   - Strict local-only dynamic adapter architecture with custom adapter registries.
   - Strict rate-limiting enforced to respect target servers.
   - Communicates with the core app via gRPC (`port 50051`).

4. **Sidecar: RAG (Node.js)**:
   - Handles Retrieval-Augmented Generation for processing RFP documents.
   - Connects to **Ollama** (for local LLMs) and **ChromaDB** (for vector storage).
   - Communicates via gRPC (`port 50052`).

5. **Sidecar: Worker Pool (Node.js)**:
   - Uses **Redis** queue (`ioredis`) for background task execution (e.g., long-running scrapes).

6. **Sidecar: Gap Engine (Node.js)**:
   - Performs gap analysis between RFP requirements and internal compliance/capabilities.

---

## 🛠️ System Requirements & Dependencies

To deploy and run this project, the host machine must have the following dependencies installed:

### 1. Core Runtime Dependencies

- **Node.js**: `v20.x` or higher (required for Vite frontend and Node sidecars).
- **NPM**: `v10.x` or higher.
- **Rust Toolchain**: `stable` (required to compile the Tauri backend). Cargo should be available in the PATH.

### 2. Native Dependencies

- **Linux (Debian/Ubuntu)**:
  - `libsqlite3-dev` (for SQLite headers used by sqlx).
  - `protobuf-compiler` (for `tonic-build` to compile gRPC `.proto` files).
  - `netcat-openbsd` or `netcat` (for Control Unit health checks).
  - WebKit2GTK packages (required by Tauri): `libwebkit2gtk-4.1-dev`, `build-essential`, `curl`, `wget`, `file`, `libxdo-dev`, `libssl-dev`, `libayatana-appindicator3-dev`, `librsvg2-dev`.
  - Playwright OS Dependencies (for Hunter sidecar browser): `npx playwright install --with-deps`.
- **Windows**:
  - Visual Studio C++ Build Tools.
  - WebView2 Runtime (usually pre-installed on Windows 11).
- **macOS**:
  - Xcode Command Line Tools (`xcode-select --install`).

### 3. Infrastructure Dependencies (Docker)

The architecture heavily relies on Docker for containerized services.

- **Docker Engine**: Installed and running.
- **Docker Compose**: **Plugin installed (`docker compose` V2 required)**. Do not use the legacy `docker-compose` (Python v1) as it is incompatible with newer Docker engines and will fail with `KeyError: 'ContainerConfig'`.

**Note on Installation**: If your package manager cannot find `docker-compose-plugin`, you can install it manually:

```bash
mkdir -p ~/.docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.26.1/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose
# To make it available for sudo:
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo cp ~/.docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
```

The `docker-compose.yml` orchestrates:

- **Ollama**: Local LLM execution.
- **ChromaDB**: Vector database.
- **Redis**: Job queue for the worker pool.
- **RAG**: Node.js sidecar for LLM processing (Port 50052).

---

## 🚀 Setup & Execution Instructions

If you are an agent taking over this project on a new machine, execute these steps sequentially:

1. **Install Root and Sidecar Dependencies:**
   Navigate to the project root and install all Node modules:

   ```bash
   npm ci
   # Setup Python dependencies for Hunter sidecar
   cd sidecars/hunter
   pip install grpcio grpcio-tools playwright pydantic httpx
   playwright install chromium
   # Setup other Node sidecars
   cd ../rag && npm install
   cd ../worker && npm install
   cd ../dispatcher && npm install
   cd ../gap-engine && npm install
   ```

   _(Note: The Hunter sidecar's `npm install` will also download Playwright browser binaries)._

2. **Start the Infrastructure:**
   Ensure Docker daemon is running, then execute:

   ```bash
   # Use sudo on Linux if the user is not in the docker group
   # Build the images first (crucial for sidecars to access root proto folder)
   docker compose build

   # Start the containers
   docker compose up
   ```

3. **Compile and Run the Application:**
   Return to the project root and start the Tauri development server:

   ```bash
   npm run tauri dev
   ```

4. **Testing:**
   The project uses `vitest`. To run all integration and unit tests:
   ```bash
   npm run test:all
   ```

---

## 📍 Current Project State (As of Last Update)

### ✅ Completed Milestones

- **Core App Shell**: Setup with Vite, React, and Tauri v2.
- **IPC & Security**: Rust backend implemented with secure IPC boundaries. CSP hardened (no external AI endpoints allowed, strict local focus).
- **gRPC Integration**: Complete across Rust, Hunter, and RAG. `proto/` directory holds the definitions.
- **UI Components**: Portal Configuration Modal, Glassmorphic Chat Window, and Gap Report generated and integrated into `App.tsx`.
- **Observability**: OpenTelemetry initialized in Rust and Node. Prometheus exporter endpoints configured for sidecars (`9464` and `9465`).
- **Worker Pool Architecture**: Scaffolded with Redis, a dispatcher script, and a background worker.
- **CI/CD**: GitHub Actions workflow defined in `.github/workflows/ci.yml`.

### 🚧 Pending/Upcoming Work

- **End-to-End Verification**: Complete testing of the full data flow from UI -> Rust -> gRPC -> Hunter/RAG -> DB.
- **Production Build & Release**: Run `npm run tauri build` and generate installers for respective OS targets.
- **Gap Engine Logic**: The Gap Engine sidecar currently holds a stub implementation that needs to be connected to the actual LLM logic.
- **Playwright Scraping Logic**: Hunter currently has a mock execution; needs the actual logic for targeting specific RFP portals mapped out.

## 🔑 Key Files to Understand

- `src-tauri/src/lib.rs` & `ipc.rs`: Rust backend logic and IPC handlers.
- `src-tauri/tauri.conf.json`: App configuration, security CSP, and auto-updater endpoints.
- `sidecars/*/src/server.ts` (Node.js) or `sidecars/hunter/src_py/server.py` (Python): Entry points for the gRPC sidecars.
- `docker-compose.yml`: Infrastructure topology.
- `config/schema.ts` & `config/config.yaml`: Centralized configuration setup.
