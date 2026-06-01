# Module: Frontend

## Purpose
The frontend provides the user interface for the Sentinel RFP Agent. It allows users to manage portals, trigger RFP discovery (hunts), view discovered opportunities, manage a local knowledge base, and perform gap analysis on RFPs. It serves as the orchestration layer, interacting with the Rust-based Tauri shell via IPC.

## Language & Runtime
- **Language**: TypeScript (React)
- **Framework**: Vite
- **Key Libraries**: Lucide-React (icons), Framer Motion (animations), Tauri API
- **Entry point**: `src/main.tsx`

## Public Interface
### Pages / Routes (Components)
- **Main Dashboard** (`App.tsx`): Central hub managing state and global layouts.
- **Portals** (`PortalConfigModal.tsx`): Managing website discovery targets.
- **Opportunities** (`OpportunitiesModal.tsx`, `OpportunityDetail.tsx`): Browsing and detailing discovered RFPs.
- **Knowledge Base** (`KnowledgeBaseDashboard.tsx`): Managing RAG documents.
- **Gap Report** (`GapReport.tsx`): Compliance analysis UI.
- **Settings** (`SettingsModal.tsx`): Ollama and system configuration.

### Tauri Commands Called (`invoke`)
- `get_portals`, `save_portal`, `delete_portal`, `toggle_portal_status`
- `get_opportunities`, `start_hunt_session`, `stop_hunt_session`, `finish_active_hunt`
- `get_knowledge_items`, `save_knowledge_item`, `delete_knowledge_item`
- `analyze_rfp_gaps`
- `check_ollama_status`, `get_ollama_models`
- `bootstrap_system` (runs `control-unit.sh`)

## Internal Structure
- `src/components/`: UI components grouped by feature (Drafts, GapReport, KnowledgeBase, Opportunities, PortalConfig, Settings).
- `src/context/AppContext.tsx`: Main state management (using React Context) for the entire application.
- `src/types.ts`: Shared TypeScript interfaces and types.

## Dependencies
### Internal
| Module | How consumed |
|--------|-------------|
| Tauri Shell | Via `@tauri-apps/api/core` `invoke` and `listen` |

### External
| Package | Version | Purpose |
|---------|---------|---------|
| react | ^18 | UI Framework |
| lucide-react | latest | Icons |
| tauri-apps/api | ^2 | IPC with Rust shell |

## Configuration
Read from `AppContext` and passed to Tauri commands.
| Variable | Required | Default | Crash if missing? |
|----------|----------|---------|-------------------|
| Ollama URL | Yes | http://127.0.0.1:11434 | No (handled in UI) |
| Ollama Model | Yes | (empty) | No |

## Data Flow
User Action -> React State Update -> Tauri `invoke` -> Rust Shell -> gRPC Sidecar -> Backing Service (Chroma/Ollama/etc).
Events from Sidecars -> Rust Shell -> Tauri `emit`/`listen` -> React State Update -> UI Render.

## Startup Sequence
1. `main.tsx` renders `App.tsx` within `AppContextProvider`.
2. `AppContext` calls `bootstrap_system` via Tauri command.
3. `bootstrap_system` triggers backend readiness scripts.
4. UI transitions from "booting" to "ready" once bootstrap completes.
