# Sentinel RFP Agent

A privacy‑first desktop application built with **Tauri**, **React**, **TypeScript**, and **Vite**.

## 🏗️ Architecture

Sentinel uses a multi-service architecture entirely embedded locally for maximum privacy and performance. No Docker or network ports required.

- **Tauri App**: The desktop frontend and core logic.
- **Hunter Sidecar**: Playwright-based web scraper for discovering RFPs.
- **RAG Sidecar**: Retrieval-Augmented Generation service using embedded ChromaDB.
- **Gap Engine**: Analysis tool for compliance gaps.
- **Worker Sidecar**: Background job processor backed by a local SQLite queue.

Services communicate via high-performance **JSON-RPC over standard input/output streams** directly managed by the Tauri host.

## 📦 Installation & Setup

1. **Prerequisites**
   - **Node >=20**
   - **Rust toolchain** (stable)
   - **System Libraries** (Linux):
     ```bash
     sudo apt-get update
     sudo apt-get install -y libsqlite3-dev protobuf-compiler \
       libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev \
       libssl-dev libayatana-appindicator3-dev librsvg2-dev
     ```

2. **Clone & Install**

   ```bash
   git clone <repo-url>
   cd sentinel
   ./install.sh               # Install frontend, system, and sidecar deps
   ```

3. **Run the App**
   Start the Tauri development server:

   ```bash
   npm run tauri dev
   ```

4. **Testing**
   ```bash
   npm run test:all           # run all unit tests
   ```

## 📚 Documentation

- See `DESIGN.md` for architectural details.

---

_All commands are defined in `package.json` scripts._
