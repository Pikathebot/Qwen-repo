# Jarvis Assistant — System Master Plan & Architecture Roadmap

**Stack:** FastAPI + native `llama-server.exe` (Qwen3.5-9B / Qwen3.5-4B) + Next.js/React Desktop Client + OpenRouter (Heavy Mode)  
**Target Machine:** Windows 11, Intel i7-14700HX (20 threads), NVIDIA RTX 4060 Laptop GPU (8GB VRAM), 16GB DDR5 RAM  
**Repository:** `d:/JARVIS`  

---

## 0. Project Vision & Core Principles

Jarvis is a private, lightning-fast, hardware-governed AI assistant for Windows 11. Designed specifically for local RTX 4060 GPU offload, it provides native llama.cpp execution, process-based VRAM eviction, deterministic $O(1)$ safety permissions, project workspace switching, durable artifacts versioning, and real-time SSE streaming.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          JARVIS UNIFIED AGENT GATEWAY                       │
│                                                                             │
│  ┌───────────────────────────────┐     ┌─────────────────────────────────┐  │
│  │   Canonical Next.js Desktop   │     │  Legacy UI Fallback (pywebview) │  │
│  │   (Next.js 14 + Tailwind)     │     │  (--legacy-ui flag)             │  │
│  └───────────────┬───────────────┘     └────────────────┬────────────────┘  │
│                  │                                      │                   │
│                  └───────────────────┬──────────────────┘                   │
│                                      ▼                                      │
│                        FastAPI Orchestrator & Router                        │
│                 (Hardware Resource Governor + Safety Gating)                │
│                                      │                                      │
│  ┌───────────────────────────────────┴───────────────────────────────────┐  │
│  │                     Expanded Tools & Engine Ecosystem                 │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────┐  ┌────────────────────────────────────┐  │  │
│  │  │   Web & Research Engine │  │     File & Workspace Engine        │  │  │
│  │  │   • DuckDuckGo Search   │  │     • read_file / write_file       │  │  │
│  │  │   • Fast HTML Scraper   │  │     • patch_file                   │  │  │
│  │  │   • URL Fetch & Parse   │  │     • Project Files & Attachments  │  │  │
│  │  └─────────────────────────┘  └────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────┐  ┌────────────────────────────────────┐  │  │
│  │  │  Windows OS Power Tools │  │   SQLModel Relational Store        │  │  │
│  │  │   • App Launcher/Focus  │  │     • Projects (Section 7 folders) │  │  │
│  │  │   • Media & Volume Ctrl │  │     • Sessions & Messages          │  │  │
│  │  │   • Active Clipboard    │  │     • Attachments & Artifacts      │  │  │
│  │  │   • Process Management  │  │     • Artifact Versions            │  │  │
│  │  └─────────────────────────┘  └────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────┐  ┌────────────────────────────────────┐  │  │
│  │  │ Voice & TTS Engine      │  │     Hardware Resource Governor     │  │  │
│  │  │   • Wake-Word Detection │  │     • PyNVML VRAM/GPU Telemetry    │  │  │
│  │  │   • Chatterbox TTS      │  │     • Adaptive Request Queue       │  │  │
│  │  └─────────────────────────┘  │     • Auto-throttle Under Load     │  │  │
│  │                               └────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. System Architecture Truth

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Primary Inference Runtime** | **native `llama-server.exe` (llama.cpp)** | Maximum inference throughput on port 8001; 100% GPU offload (`-ngl 99`) and `--no-mmap` to conserve 16GB system RAM. |
| **Primary LLM Models** | **Qwen3.5-9B Q4_K_M (Main) / Qwen3.5-4B Q4_K_M (Fast)** | High intelligence, strong coding, native tool calling, fits comfortably in 8GB VRAM. |
| **Heavy Reasoning Fallback** | **OpenRouter (Cloud)** | Used for ultra-complex multi-file architectural reasoning when requested or auto-routed. |
| **Backend API** | **FastAPI + SSE (`/chat/stream`)** | High-performance asynchronous endpoint emitting token streams, tool events, and structured metadata. |
| **Database & Migrations** | **SQLModel + Alembic** | Single unified database layer (`data/jarvis_memory.db`) with automatic migrations on startup. |
| **Frontend UI** | **Next.js 14 + React + Tailwind CSS + Tauri (`desktop-app/`)** | Modern desktop UI with project workspace switcher, 4-tab RightPanel, and attachment upload. |
| **VRAM Management** | **Process-based eviction via `RuntimeProcessManager.stop()`** | Cleanly frees 100% GPU memory on demand without lingering zombie processes. |

---

## 2. Implemented Milestones (Status: Complete)

- [x] **Phase 0 — FastAPI Core & SSE Streaming**: Real-time `/chat/stream` SSE generator and `/chat` endpoints.
- [x] **Phase 1 — Native Tool Calling**: Inspect-based signature introspection, tool registration, and parameter validation.
- [x] **Phase 2 — Deterministic Safety Permissions**: $O(1)$ hardcoded security tiering (`LOW_RISK`, `CONFIRMATION_REQUIRED`, `HIGH_RISK`) with SHA256 action tokens.
- [x] **Phase 3 — Hardware Resource Governor (V2)**: PyNVML GPU/VRAM telemetry + `psutil` CPU/RAM monitoring with automatic load throttling.
- [x] **Phase 4 — Model Router & Runtime Process Manager**: Local llama.cpp process manager with `-ngl 99 --no-mmap` execution flags.
- [x] **Phase 5 — Database Unification (SQLModel + Alembic)**: Unified schema across projects, sessions, messages, attachments, and artifacts.
- [x] **Phase 6 — Project Workspaces & Section 7 Filesystem**: Directory hierarchy under `workspace/projects/{project_id}/` (`files/`, `knowledge/`, `artifacts/`, `memory/`, `indexes/`).
- [x] **Phase 7 — Artifacts, Attachments & Context Injection**: Versioned artifact storage, secure attachment uploads, and automatic LLM context turn injection.
- [x] **Phase 8 — Next.js Desktop Application**: Canonical desktop client in `desktop-app/` with workspace switcher and 4-tab RightPanel.

---

## 3. Next Milestone: Option 4 — Context Engine & RAG

- **Document Chunking & Storage**: Ingest project files and local folder knowledge into `DocumentChunk` records.
- **Local Embeddings**: Fast local embeddings engine for semantic search over project knowledge bases.
- **Hybrid Retrieval**: Combine exact BM25/FTS keyword search with vector similarity retrieval.
- **Context Assembly**: Dynamically retrieve and score relevant chunks during orchestrator prompt building.
