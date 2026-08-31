# Jarvis AI Assistant — Master Architecture & AI Agent Onboarding Guide

> **Purpose**: This document provides incoming AI agents with a comprehensive, end-to-end overview of the **Jarvis** project — how the subsystems operate, the agent orchestrator tool loop, safety permissions, hardware governor, REST APIs, and file tree.

---

## 1. Executive Summary

**Jarvis** is a private, lightweight, and fast local AI desktop assistant built specifically for Windows 11. It features a Raycast/Spotlight-style floating glassmorphic interface triggered globally via `Alt+Space` or `Ctrl+Space`.

### Core Capabilities:
1. **Local-First Inference**: Runs on local LLMs via LM Studio (`prism-ml/bonsai-27b`) or Ollama (`hermes3:8b` / `qwen3.5:9b`).
2. **Dynamic Model Routing**: Intelligently detects high-complexity tasks (math proofs, deep system architecture, large code refactors) and routes them to OpenRouter (`meta-llama/llama-3.3-70b-instruct`) while keeping standard tasks local.
3. **Hardware Resource Governor (V2)**: Real-time telemetry monitoring NVIDIA RTX 4060 GPU utilization, VRAM (MB/%), CPU, and RAM via `nvidia-ml-py` (PyNVML) and `psutil`. Queues or rejects incoming tasks when thresholds (e.g. 90% VRAM) are exceeded.
4. **Deterministic $O(1)$ Safety Permissions**: Hardcoded zero-hallucination security table classifying actions into `LOW_RISK`, `CONFIRMATION_REQUIRED`, and `HIGH_RISK`. Potentially dangerous actions return cryptographic SHA-256 tokens (`act_<hash>`) requiring user confirmation before execution.
5. **Model Context Protocol (MCP)**: Implements standard bidirectional JSON-RPC 2.0 stdio client bridge to external tools and servers.
6. **Dynamic Skills Loader**: Extensible markdown-based domain skills (`skills/*.md`) with trigger keyword matching injected into prompts on-demand.
7. **Progressive Short-Term Memory**: SQLite conversation store with two-stage compaction (verbose tool output truncation + LLM turn summarization).

---

## 2. Directory Structure & Key Files

```
JARVIS/
├── run_jarvis.py                   # Master entrypoint / launcher (starts backend & desktop UI)
├── Jarvis.bat                      # Windows batch launcher
├── README.md                       # High-level overview & quickstart
├── PLAN.md                         # Milestone implementation roadmap
├── STAGE_B_AND_GOVERNOR_V2_DIFF_REPORT.md  # Architectural diff and audit report
├── governor_watchlist.json         # Process names monitored by the Resource Governor
│
├── docs/                           # Exhaustive technical documentation
│   ├── ARCHITECTURE.md             # 8-layer subsystem deep dive
│   ├── API_REFERENCE.md            # REST API endpoints & request/response schemas
│   ├── USER_GUIDE.md               # User interaction, hotkeys, custom skills
│   ├── PLAN.md                     # Engineering roadmap & specifications
│   ├── GOVERNOR_V2_STAGE_1_SPEC.md # Telemetry & process watcher spec
│   ├── GOVERNOR_V2_STAGE_3_SPEC.md # Governor V2 stage 3 spec
│   ├── STAGE_A_IMPLEMENTATION_SPEC.md # Stage A implementation spec
│   └── AI_AGENT_CONTEXT.md         # This AI Agent Onboarding Guide
│
├── backend/                        # FastAPI Backend Application
│   ├── app/
│   │   ├── main.py                 # FastAPI application & router mounting
│   │   ├── config.py               # Pydantic Settings & environment variables
│   │   ├── agent/
│   │   │   ├── orchestrator.py     # Multi-turn agent loop & execution engine
│   │   │   ├── model_router.py     # Local vs Heavy model router
│   │   │   ├── permissions.py      # Deterministic O(1) safety permission engine
│   │   │   ├── ollama_client.py    # Local Ollama HTTP API client
│   │   │   ├── lmstudio_client.py  # Local LM Studio OpenAI-compatible client
│   │   │   ├── openrouter_client.py# OpenRouter cloud client for Heavy Mode
│   │   │   ├── validator.py        # Tool argument signature introspection
│   │   │   └── tools/              # Built-in native tools
│   │   │       ├── registry.py     # Tool registry & schema extractor
│   │   │       ├── read_file.py    # Local file reader
│   │   │       ├── write_file.py   # Local file writer (requires approval)
│   │   │       ├── patch_file.py   # Local file patcher
│   │   │       ├── file_search.py  # File & content search
│   │   │       ├── list_directory.py # Directory listing
│   │   │       ├── app_control.py  # Application launcher / window focus
│   │   │       ├── process_control.py # Process management
│   │   │       ├── clipboard_control.py # Clipboard inspection / setting
│   │   │       ├── notify.py       # Windows desktop notifications
│   │   │       ├── web_search.py   # Web search tool
│   │   │       ├── fetch_url.py    # URL fetch & markdown extractor
│   │   │       └── media_control.py# System audio / media control
│   │   ├── governor/
│   │   │   ├── resource_governor.py # PyNVML & psutil telemetry + adaptive queue
│   │   │   └── process_watcher.py  # Background process monitor & throttle
│   │   ├── memory/
│   │   │   ├── manager.py          # SQLite multi-turn conversation manager
│   │   │   └── compactor.py        # Two-stage progressive context compaction
│   │   ├── mcp/
│   │   │   ├── client.py           # JSON-RPC 2.0 stdio client
│   │   │   ├── manager.py          # MCP server lifecycle & tool bridge
│   │   │   └── builtin_servers/    # Default internal MCP tools (uptime, disk)
│   │   ├── skills/
│   │   │   └── loader.py           # Dynamic YAML frontmatter markdown loader
│   │   └── voice/
│   │       ├── wake_word.py        # Keyword spotter ("Jarvis", "Hey Jarvis")
│   │       └── synthesizer.py      # TTS text cleaner & sanitizer
│   ├── requirements.txt            # Python dependencies
│   ├── .env.example                # Configuration template
│   └── tests/                      # Pytest automated test suite
│
├── desktop/                        # Desktop UI Client
│   ├── app.py                      # pywebview frameless Spotlight overlay
│   ├── tray.py                     # pystray Windows system tray service
│   ├── hotkey.py                   # pynput global keyboard hook (Alt+Space)
│   └── ui/                         # Glassmorphic HTML/CSS/JS frontend
│       ├── index.html
│       ├── styles.css
│       └── app.js
│
└── skills/                         # User-defined dynamic skills
    ├── code_review.md              # Code review domain skill
    └── system_diagnostics.md       # Diagnostic tools skill
```

---

## 3. Subsystem Architecture & Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DESKTOP CLIENT & TRAY                             │
│   • Spotlight Overlay (pywebview)        • Windows System Tray (pystray)    │
│   • Global Hotkeys (Alt+Space / Ctrl+Space) • Voice / Wake-Word ("Jarvis")  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP JSON-RPC (POST /api/chat)
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
│  │   • Dynamic Skills Loader                • MCP Stdio Client Bridge    │  │
│  └────────────┬──────────────────────────────────────────────────┬───────┘  │
│               │                                                  │          │
│  ┌────────────▼────────────┐                       ┌─────────────▼───────┐  │
│  │      SQLite Memory      │                       │     Tool Registry   │  │
│  │  (Sessions & Messages)  │                       │   • read_file       │  │
│  │                         │                       │   • write_file      │  │
│  │                         │                       │   • MCP Tools       │  │
│  └─────────────────────────┘                       └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### End-to-End Workflow:
1. **Invocation**: User triggers overlay via `Alt+Space` or says `"Hey Jarvis"`.
2. **API Dispatch**: UI sends `POST /api/chat` with user query and session ID.
3. **Telemetry Check**: `ResourceGovernor.wait_until_healthy()` verifies hardware safety (<90% VRAM, <85% GPU Core, <90% CPU).
4. **Model Selection**: `ModelRouter` checks if heavy reasoning is required.
5. **Context Assembly**: `MemoryManager` fetches history, dynamically injects matched skills from `skills/*.md`, and compacts if over 16,000 tokens.
6. **Tool Loop & Safety**: `Orchestrator` invokes model. If model requests tool execution, `PermissionManager` validates the operation:
   - `LOW_RISK` tools run immediately.
   - `CONFIRMATION_REQUIRED` / `HIGH_RISK` tools pause and issue a SHA-256 action token `act_<hash>`.
7. **Response & Persistence**: Turns are saved to SQLite and rendered in the UI.

---

## 4. Key Developer Commands

- **Run Full App**: `python run_jarvis.py`
- **Run Backend Standalone**: `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload`
- **Run Test Suite**:
  ```powershell
  $env:PYTHONPATH="d:/JARVIS/backend;d:/JARVIS"
  pytest backend/tests -v
  ```
