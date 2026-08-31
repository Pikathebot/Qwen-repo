# Project Jarvis (Nexus) — Executive Project Summary

## System Overview
- **Primary Runtime Engine**: Native `llama-server.exe` (llama.cpp) on `http://127.0.0.1:8001`
- **Active Models**:
  - Main: `Qwen3.5-9B Q4_K_M`
  - Fast: `Qwen3.5-4B Q4_K_M`
- **Hardware Optimization**: 100% GPU offloading (`-ngl 99`) and system RAM conservation (`--no-mmap`) tailored for NVIDIA RTX 4060 (8GB VRAM) and 16GB DDR5 system RAM.
- **Backend Architecture**: FastAPI on `http://127.0.0.1:8000` with Server-Sent Events (`/chat/stream`) token streaming.
- **Database & Persistence**: Unified SQLModel ORM + Alembic schema migrations on startup (`data/jarvis_memory.db`).
- **Canonical Desktop Frontend**: Next.js 14 + React + Tailwind CSS in [`desktop-app/`](desktop-app/) with workspace switching and 4-tab RightPanel (`Artifacts`, `Files`, `Context`, `Activity`).
- **Safety & Governance**: PyNVML Hardware Resource Governor (V2) with deterministic $O(1)$ SHA-256 action confirmation tokens.
- **Current Phase**: Phase 1 Cleanup Completed & Verified. Ready for Option 4 (Context Engine & RAG).
