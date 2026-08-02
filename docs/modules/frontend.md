# Module: Frontend

## Purpose
The frontend provides the user interface for the Sentinel RFP Agent. It allows users to manage portal configurations, trigger scraping hunts, browse opportunities, manage knowledge documents, review proposal drafts, and view compliance gap analysis. It serves as the visual orchestration layer, interacting with the Rust-based Tauri shell via native IPC.

## Language & Runtime
- **Language**: TypeScript (React)
- **Framework**: Vite
- **Key Libraries**:
  - `@tauri-apps/api/core`: Standard Tauri IPC bridge (invoking commands, subscribing to event emitters).
  - `lucide-react`: Modern SVG icon pack.
  - `framer-motion`: Smooth UI micro-animations and page transitions.
- **Entry point**: `src/main.tsx`

## Public Interface
### Views / Components
- **Main Dashboard** (`App.tsx`): Manages global dashboard layouts and states. Feed rows show priority / applied / dismissed badges.
- **Portal Configurations** (`PortalConfigModal.tsx`): Managing target website feeds and testing IPC connections.
- **Opportunities** (`OpportunitiesModal.tsx`, `OpportunityDetail.tsx`): Browsing and detailing crawled RFPs. The modal groups opportunities under **Not Applied**, **Applied**, and **Dismissed** headings, with per-card priority selection, an "Apply" form (date / reference / notes), and a "Dismiss" action. Expired not-applied opportunities auto-move to Dismissed with a `deadline expired` note on open. Manual addition supports both a **Paste Link** mode (auto-fetches title / organization / deadline / description via `fetch_opportunity_from_url`) and a full **Manual Entry** form; portal selection is optional. The detail view supports inline editing of core fields.
- **Knowledge Base** (`KnowledgeBaseDashboard.tsx`): Managing vector store document indices.
- **Gap Report** (`GapReport.tsx`): Multi-dimensional compliance gap and risk matrix reports with try-catch safety guards.
- **Settings** (`SettingsModal.tsx`): Configuring the AI provider — **Google Gemini** (API key + model) or **Ollama (Local)** (URL + model). On boot the app auto-detects Ollama; if absent it falls back to Google and prompts the user to connect a provider before running hunts.

### Tauri Commands Called (`invoke`)
- `get_portals`, `save_portal`, `delete_portal`, `toggle_portal_status`, `finish_active_hunt`
- `get_opportunities_list`, `get_opportunity_detail`, `update_opportunity_status`, `delete_opportunity`, `create_opportunity`
- `update_opportunity_priority`, `apply_opportunity`, `dismiss_opportunity`, `expire_not_applied`
- `fetch_opportunity_from_url`, `edit_opportunity_fields`
- `get_attachments`, `save_attachment`, `delete_attachment`, `update_attachment_text`, `open_attachment`
- `get_proposal_drafts`, `save_proposal_draft`, `update_proposal_draft`, `delete_proposal_draft`
- `get_knowledge_base`, `save_knowledge_item`, `delete_knowledge_item`
- `start_hunt_session`, `stop_hunt_session`, `detect_portal`
- `analyze_gaps`, `generate_chat_response`, `generate_vision_description`, `ingest_document`, `generate_draft`
- `check_llm_provider`, `get_llm_models`

## State & Data Flow
1. **Trigger**: Component executes an asynchronous Tauri command using `invoke`.
2. **IPC execution**: The command returns a Promise. The UI wraps it in `try-catch` blocks to handle any errors elegantly without blocking the renderer thread.
3. **Reactive Listeners**: Real-time status updates (like scraping progress or LLM generation tokens) are received via the Tauri `listen()` API. Subscriptions are automatically disposed of during unmounting.
