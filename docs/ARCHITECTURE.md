# Jarvis Assistant — System Architecture

This document provides a comprehensive technical overview of the Jarvis Local AI Assistant architecture across all backend and frontend subsystem layers.

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DESKTOP CLIENT                                    │
│   • Canonical Next.js / React Desktop UI (desktop-app/)                     │
│   • Project Workspace Switcher | 4-Tab RightPanel | Attachment Composer     │
│   • Fallback PyWebView Desktop UI (desktop/ui) via --legacy-ui              │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ SSE Streaming (POST /chat/stream)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                            FASTAPI BACKEND SERVICE                          │
│                                                                             │
│  ┌─────────────────────────┐  ┌────────────────────────┐  ┌──────────────┐  │
│  │    Resource Governor    │  │   Safety Permissions   │  │ Model Router │  │
│  │ (GPU/VRAM/CPU Telemetry)│  │ (Deterministic O(1) Gating) (Normal/Heavy) │  │
│  └────────────┬────────────┘  └───────────┬────────────┘  └──────┬───────┘  │
│               │                           │                      │          │
│  ┌────────────▼───────────────────────────▼──────────────────────▼───────┐  │
│  │                           Agent Orchestrator                          │  │
│  │   • Multi-Turn Tool Loop                 • Context Compaction         │  │
│  │   • Attachment Context Injection         • MCP Stdio Client Bridge    │  │
│  │   • Dynamic Skills Loader                • Native llama.cpp Provider  │  │
│  └────────────┬──────────────────────────────────────────────────┬───────┘  │
│               │                                                  │          │
│  ┌────────────▼────────────┐                       ┌─────────────▼───────┐  │
│  │    SQLModel Database    │                       │  llama-server.exe   │  │
│  │ (Projects, Sessions,    │                       │  (Qwen3.5-9B / 4B)  │  │
│  │  Attachments, Artifacts)│                       │  -ngl 99 --no-mmap  │  │
│  └─────────────────────────┘                       └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Subsystems

### 1. Primary Inference Runtime & llama.cpp (`backend/app/agent/runtime_process_manager.py`)
- **Native `llama-server.exe` Execution**: Manages child process lifecycle on `http://127.0.0.1:8001`.
- **Hardware-Tailored Flags**: Launches with `-ngl 99` for 100% GPU VRAM offload and `--no-mmap` to conserve 16GB system RAM on the RTX 4060.
- **Process-Based VRAM Eviction**: Calling `RuntimeProcessManager.stop()` terminates the server process cleanly, freeing 100% GPU memory on demand.
- **Supported Models**:
  - **Main Model**: `Qwen3.5-9B-Q4_K_M.gguf`
  - **Fast Model**: `Qwen3.5-4B-Q4_K_M.gguf`

### 2. Agent Orchestrator & Native Tool Loop (`backend/app/agent/orchestrator.py`)
- **Multi-Turn Execution**: Evaluates user prompts, tool calls, and completions asynchronously.
- **Attachment Context Injection**: Automatically extracts text/code from session attachments and injects formatted snippets into the turn prompt context.
- **Tool Validation**: Uses `inspect.signature` to validate LLM tool call arguments against function schemas, preventing hallucinations.

### 3. Safety Permission Layer (`backend/app/agent/permissions.py`)
- **Deterministic Hardcoded Evaluation**: Zero-overhead $O(1)$ rule table mapping operations to risk tiers:
  - `LOW_RISK`: Automatically executed without user confirmation (`read_file`, `web_search`, `fetch_url`).
  - `CONFIRMATION_REQUIRED`: Blocks execution and returns approval tokens (`write_file`, `patch_file`, `app_control`).
  - `HIGH_RISK`: Always requires confirmation (`delete_file`, destructive shell commands like `rm -rf`, `Format-Volume`).
- **Canonical Action Token Hashing**: Generates unique SHA-256 tokens (`act_<hash>`) for each blocked action, preventing replay attacks or hallucinated approvals.

### 4. Hardware Resource Governor (`backend/app/governor/`)
- **Real-Time Telemetry**: Uses `nvidia-ml-py` (PyNVML) to poll NVIDIA RTX 4060 GPU utilization, VRAM usage (MB and percentage), and temperature (°C), along with `psutil` for host CPU/RAM.
- **Adaptive Queueing & Overload Protection**: If hardware thresholds are exceeded, requests enter an adaptive waiting queue (`wait_until_healthy`). If the system remains overloaded beyond the timeout, HTTP 429 is returned to protect local hardware stability.

### 5. Unified Relational Database (`backend/app/database/`, `backend/app/memory/`)
- **SQLModel ORM & Alembic Migrations**: Single unified SQLite store (`data/jarvis_memory.db`) with automated startup schema migrations.
- **Entities**:
  - `Project`: Workspaces with custom instructions and local folder paths.
  - `Session` & `Message`: Multi-turn chat history with session filtering.
  - `Attachment`: User-uploaded files tracked with metadata and disk paths.
  - `Artifact` & `ArtifactVersion`: AI-generated durable outputs with version tracking.
  - `ToolCall` & `ToolResult`: Structured tool invocation history.
- **Context Compactor (`compactor.py`)**: Two-stage progressive compaction (tool output truncation + LLM turn summarization).

### 6. Project Workspaces & Section 7 Filesystem (`backend/app/routers/projects.py`)
- **Storage Layout**: Enforces directory isolation under `${WORKSPACE_PATH}/projects/{project_id}/`:
  - `files/`: User-uploaded attachments.
  - `knowledge/`: Project knowledge documents.
  - `artifacts/`: AI-generated code, markdown, and reports.
  - `memory/`: Project-specific notes and preferences.
  - `indexes/`: Vector and search indices.

### 7. Canonical Desktop Frontend (`desktop-app/`)
- **Technology**: React 14 + Next.js + Tailwind CSS + TypeScript.
- **Key Features**:
  - **Sidebar**: Workspace/Project switcher dropdown, session list, and new chat trigger.
  - **RightPanel**: 4-tab panel (`Artifacts`, `Files`, `Context`, `Activity`).
  - **Composer**: Attachment upload button with preview chips and action confirmation buttons.
  - **Streaming**: Server-Sent Events client (`sse-client.ts`) parsing live token streams from `/chat/stream`.

### 8. Voice & Wake-Word Engine (`backend/app/voice/`)
- **Wake-Word Detector**: Regex keyword spotter listening for `"Jarvis"`, `"Hey Jarvis"`, and variants.
- **Chatterbox TTS**: Text-to-speech audio synthesis with real-time playback control and speech sanitization.
