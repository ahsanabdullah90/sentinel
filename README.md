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

---

## 📦 Quick Start (Windows)

### Prerequisites

| Component | Version | Install |
|---|---|---|
| Node.js | >= 20 | https://nodejs.org |
| Python | >= 3.11 | https://python.org |
| Rust | stable | https://rustup.rs |
| MSVC Build Tools | 2022+ | `winget install Microsoft.VisualStudio.2022.BuildTools` |
| Ollama | latest | https://ollama.com |

### One-Command Setup

```bat
setup.bat
```

This installs all Node.js, Python, and Playwright dependencies.

### Run the App

```bat
run.bat
```

The launcher automatically:
- Starts Ollama if not running
- Verifies all dependencies
- Launches the Tauri development server

---

## 📦 Installation & Setup (Linux)

1. **Prerequisites**
   - **Node >=20**
   - **Rust toolchain** (stable)
   - **System Libraries**:
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

---

## 🧪 Testing

```bash
# Run all sidecar tests (run from each sidecar directory)
cd sidecars/hunter && pytest tests/ -v
cd sidecars/rag && pytest tests/ -v
cd sidecars/worker && pytest tests/ -v
cd sidecars/gap_engine && pytest tests/ -v

# Or run root-level tests
pytest tests/ -v
```

---

## 📂 Project Layout

### Directories

| Directory | Description |
|---|---|
| `sidecars/hunter` | Playwright web scraper for discovering RFPs |
| `sidecars/rag` | Retrieval-Augmented Generation (ChromaDB + Ollama) |
| `sidecars/worker` | Background job processor (SQLite queue) |
| `sidecars/gap_engine` | Compliance gap analysis (Ollama inference) |
| `src` | React + TypeScript frontend codebase |
| `src-tauri` | Rust Tauri application core |
| `tests` | Python integration tests |
| `docs` | Architecture and module documentation |

### Key Files

| File | Description |
|---|---|
| `setup.bat` | Windows one-command setup |
| `run.bat` | Windows app launcher with pre-flight checks |
| `install.sh` | Linux/Unix setup script |
| `.env.example` | Environment variable template |

---

## 📚 Documentation

- `DESIGN.md` — Architecture and design system
- `docs/architecture.md` — Component diagram and module details
- `sidecars/*/README.md` — Per-sidecar documentation

---

_See `package.json` for all available npm scripts._
