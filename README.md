# Sentinel RFP Agent

A privacy‑first desktop application built with **Tauri**, **React**, **TypeScript**, and **Vite**.

## 🏗️ Architecture

Sentinel uses a multi-service architecture to ensure privacy and isolation:

- **Tauri App**: The desktop frontend and core logic.
- **Hunter Sidecar**: Playwright-based web scraper for discovering RFPs.
- **RAG Sidecar**: Retrieval-Augmented Generation service using ChromaDB and Ollama.
- **Gap Engine**: Analysis tool for compliance gaps.

Services communicate via **gRPC** for performance and type safety.

## 📦 Installation & Setup

1. **Prerequisites**
   - **Node >=20**
   - **Rust toolchain** (stable)
   - **Docker** and **Docker Compose**
   - **System Libraries** (Linux):
     ```bash
     sudo apt-get update
     sudo apt-get install -y libsqlite3-dev protobuf-compiler netcat-openbsd \
       libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev \
       libssl-dev libayatana-appindicator3-dev librsvg2-dev
     ```
   - **Playwright Dependencies**:
     ```bash
     npx playwright install --with-deps
     ```

2. **Clone & install deps**

   ```bash
   git clone <repo-url>
   cd sentinel
   npm ci                     # install front‑end deps
   ```

3. **Run the Infrastructure**
   Start the sidecars and databases using Docker Compose (V2 required):

   ```bash
   docker compose build
   docker compose up
   ```

4. **Run the App**
   Start the Tauri development server:

   ```bash
   npm run tauri dev
   ```

5. **Testing**
   ```bash
   npm run test:all           # run all unit tests
   ```

## 📚 Documentation

- See `docs/master.md` for the full implementation guide.

---

_All commands are defined in `package.json` scripts._
