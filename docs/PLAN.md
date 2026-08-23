# Jarvis Assistant — System Master Plan & Autonomous Evolution

**Stack:** FastAPI + LM Studio (`prism-ml/bonsai-27b` default) + Ollama (`hermes3:8b` rollback target) + OpenRouter (Heavy Mode & Vision fallback) + `faster-whisper` Local STT  
**Target Machine:** Windows 11, Intel i7-14700HX (20 threads), NVIDIA RTX 4060 Laptop GPU (8GB VRAM), 16GB DDR5 RAM  
**Repository:** `d:/JARVIS`  

---

## 0. Project Vision & Architecture Comparison

Jarvis is a private, lightning-fast, hardware-governed AI assistant for Windows. Jarvis is evolving into an autonomous, proactive, multi-channel personal assistant comparable to **OpenClaw** (formerly Warelay / Moltbot), **Open Interpreter**, and **Claude Computer Use**, while preserving its local privacy, deterministic safety permissions, and RTX 4060 GPU governor.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          JARVIS UNIFIED AGENT GATEWAY                       │
│                                                                             │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────┐  │
│  │ Local Floating Overlay│  │  Telegram Bot Gateway │  │ Background Cron │  │
│  │ (Alt+Space Desktop)   │  │  (Remote Phone Access)│  │ (Proactive Loop)│  │
│  └───────────┬───────────┘  └───────────┬───────────┘  └────────┬────────┘  │
│              │                          │                       │           │
│              └──────────────────────────┼───────────────────────┘           │
│                                         ▼                                   │
│                        FastAPI Orchestrator & Router                        │
│                 (Hardware Resource Governor + Safety Gating)                │
│                                         │                                   │
│  ┌──────────────────────────────────────┴────────────────────────────────┐  │
│  │                     Expanded Tools & Engine Ecosystem                 │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────┐  ┌────────────────────────────────────┐  │  │
│  │  │   Web & Research Engine │  │     File & Workspace Engine        │  │  │
│  │  │   • DuckDuckGo Search   │  │     • write_file                   │  │  │
│  │  │   • Fast HTML Scraper   │  │     • patch_file (fuzzy fallback)  │  │  │
│  │  │   • Dynamic URL Stream  │  │     • file_search (grep / glob)    │  │  │
│  │  └─────────────────────────┘  └────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────┐  ┌────────────────────────────────────┐  │  │
│  │  │  Windows OS Power Tools │  │   Long-Term Memory & Local RAG     │  │  │
│  │  │   • App Launcher/Focus  │  │     • SQLite FTS5 (Exact match)    │  │  │
│  │  │   • Media & Volume Ctrl │  │     • Vector Store (Semantic RAG)  │  │  │
│  │  │   • Active Clipboard    │  │     • Personal Notes Indexer       │  │  │
│  │  │   • Process Management  │  │     • Compaction + Fact Storage    │  │  │
│  │  └─────────────────────────┘  └────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────┐  ┌────────────────────────────────────┐  │  │
│  │  │ Screen Vision & OCR     │  │     Proactive Scheduler & Tasks    │  │  │
│  │  │   • Multi-monitor Snap  │  │     • Cron & Natural Language Jobs │  │  │
│  │  │   • Visual Error Diag   │  │     • Windows Desktop Toasts       │  │  │
│  │  └─────────────────────────┘  │     • Telegram Push Alerts         │  │  │
│  │                               └────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Resolved Design Decisions & Core Capabilities

| Subsystem Area | Current Implementation Status | Key Technical Specifications |
| :--- | :--- | :--- |
| **Model Backend (Stage B)** | **LM Studio `bonsai-27b` + Ollama `hermes3:8b` Rollback** | OpenAI function-calling format, deep reasoning support, automatic `lms` CLI VRAM eviction, and fallback to Hermes 3 / OpenRouter. |
| **Governor V2 (Stages 1–3)** | **Activity-Aware, Debounced, Overridable & ProcessWatcher** | 6-tier status (`IDLE`, `RUNNING`, `LOADING`, `PAUSED`, `UNLOADED`, `ERROR`), 50-event history buffer, `ProcessWatcher` for gaming/heavy app detection, manual overrides (`/pause`, `/resume`, `/resume-override`), manual reload/clear error, and Desktop Command Panel. |
| **Foundation Hardening (Stage A)** | **Validator, Loop-Breaker & Turn Cap** | Pydantic schema validation, `CallHistory` duplicate call suppression, `MAX_TOOL_CALLS_PER_TURN = 15`, tool call audit log table in SQLite. |
| **Web Research (Phase 1)** | **DuckDuckGo Search + Fast HTML Scraper** | Keyless `ddgs` search, `trafilatura`/`httpx` reader, URL redirect follow, conversational tool interception, and automatic answer synthesis. |
| **File Engine (Phase 2)** | **Workspace-Gated File Creator, Patcher & Searcher** | `write_file`, `patch_file` (with multi-strategy fallback), `file_search` (glob & text search), canonical path traversal protection. |
| **Voice & Desktop UI** | **Local `faster-whisper` + Glassmorphic Overlay** | Local Whisper STT engine, dual audio capture, persistent WebView2 storage origin for mic permissions, 6-tier governor arc ring & interactive command panel. |
| **Remote Access Channel** | *Phase 7 (Pending)* | Telegram Bot gateway with admin ID whitelist and inline interactive approval buttons for gated actions. |
| **Autonomous Engine** | *Phase 5 (Pending)* | Dual scheduler (preset cron routines + natural language reminders) + Windows Toast alerts. |

---

## 2. Foundational Milestones & Hardening Tracks (Status: Complete)

- [x] **Phase 0 — FastAPI Skeleton**: Async `/chat` endpoint with Pydantic validation and health checks.
- [x] **Phase 1 — Native Tool Loop & Validation**: Dynamic tool execution loop, inspect-based schema extraction, and OpenAI function format conversion.
- [x] **Phase 2 — Deterministic Safety Permissions**: $O(1)$ risk-tier lookup (`LOW_RISK`, `CONFIRMATION_REQUIRED`, `HIGH_RISK`) with SHA256 canonical action token hashes (`act_<hash>`).
- [x] **Phase 3 — Hardware Resource Governor (V2)**: PyNVML GPU/VRAM telemetry + `psutil` CPU/RAM monitoring with activity registry, 2-sided debounce, `ProcessWatcher` auto-unload via `lms unload --all`, and live desktop command panel.
- [x] **Phase 4 — Model Router & Heavy Mode**: Dynamic prompt complexity analyzer routing normal queries to LM Studio `bonsai-27b` (with Ollama `hermes3:8b` rollback) and heavy reasoning/architecture to OpenRouter.
- [x] **Phase 5 — SQLite Memory & Compaction**: Relational SQLite message store with 2-stage compaction (tool pruning + LLM summarization), tool audit logs, and reliability events tracking.
- [x] **Phase 6 — MCP Bridge & Dynamic Skills Loader**: Async stdio JSON-RPC 2.0 client + dynamic keyword-matching markdown skills loader.
- [x] **Phase 7 — Desktop UI & System Tray**: Frameless pywebview spotlight overlay (`Alt+Space`), Windows system tray with live hardware status, 6-tier arc ring, and governor command panel.
- [x] **Phase 8 — Voice & Wake-Word Engine**: Local `faster-whisper` STT engine, dual audio capture, Web Speech API fallback, and speech sanitization.
- [x] **Stage A — Safety & Execution Hardening**: Schema validator with repair-then-escalate loop, `CallHistory` duplicate breaker, rate limits, and audit log table.
- [x] **Stage B — LM Studio Bonsai 27B Migration**: Default inference migration, OpenAI tool schema conversion, `lms` CLI integration, and tool output answer synthesis.

---

## 3. OpenClaw Autonomous Evolution Roadmap

```
[x] Phase 1: Web Research Engine (DuckDuckGo + Fast HTML Scraper + Dynamic Fallback)
    ↓
[x] Phase 2: File Creation, Patching & Workspace Safety Gating
    ↓
[x] Phase 3: Windows OS Power Controls & Desktop Toast Alerts
    ↓
[ ] Phase 4: Multi-Monitor Screen Vision & Visual Diagnostics  ◄ [NEXT IN QUEUE]
    ↓
[ ] Phase 5: Proactive Background Scheduler & Autonomous Watchers
    ↓
[ ] Phase 6: Long-Term Memory & Hybrid Local RAG (Notes/Docs Indexing)
    ↓
[ ] Phase 7: Remote Telegram Bot Gateway with Interactive Approval Buttons
    ↓
[ ] Phase 8: Enhanced Executable Skills & Workflows
```

---

## 4. Phase 3 Detailed Plan: Windows OS Power Controls & Toast Alerts

### Objective
Provide Jarvis with safe, native operating system power tools on Windows 11 to launch and focus applications, manage media/volume, inspect active processes, interact with the clipboard, and trigger native Windows Toast notifications.

### Components to Build

#### 1. Windows OS Power Tools (`backend/app/agent/tools/os_tools.py`)
* **App Launcher / Switcher**:
  * Function: `launch_app(app_name: str) -> str`
  * Searches Windows Start Menu / App Paths registry / common paths and brings window to focus if already running.
* **Media & Audio Control**:
  * Function: `media_control(action: Literal["play_pause", "next", "previous", "mute", "volume_up", "volume_down", "set_volume"], value: Optional[int] = None) -> str`
  * Uses `pycaw` / `ctypes` keybd_event virtual key codes (`VK_MEDIA_PLAY_PAUSE`, `VK_VOLUME_MUTE`, etc.) for instant media control.
* **Active Clipboard Manager**:
  * Function: `get_clipboard_text() -> str` / `set_clipboard_text(text: str) -> str`
  * Reads or sets current Windows clipboard contents with safety truncation caps.
* **Process Inspector & Management**:
  * Function: `list_running_processes(filter_name: Optional[str] = None, top_n: int = 10) -> str`
  * Inspects CPU/RAM utilization of top running applications via `psutil`.

#### 2. Windows Toast Notification Engine (`backend/app/agent/tools/toast_notify.py`)
* Function: `notify_user(title: str, message: str, urgency: Literal["low", "normal", "critical"] = "normal") -> str`
* Dispatches native Windows 10/11 Toast notifications via Windows WinRT / PowerShell background dispatcher.

#### 3. Safety & Permission Integration
* `get_clipboard_text`, `media_control`, `list_running_processes`, `notify_user`: Classified as `LOW_RISK` (auto-execute).
* `set_clipboard_text`, `launch_app`: Classified as `LOW_RISK` (with target whitelist) or `CONFIRMATION_REQUIRED` for arbitrary executables.
* Terminating processes or running arbitrary shell commands: Strictly gated under `HIGH_RISK` / `CONFIRMATION_REQUIRED`.

---

## 5. Phase 4 Preview: Multi-Monitor Screen Vision & Diagnostics
* Screen capture via `mss` / `PIL.ImageGrab` across primary and secondary displays.
* Bounded image downsampling to prevent VRAM explosion on the RTX 4060 (8GB).
* Multimodal routing: Local vision or OpenRouter vision fallback (`anthropic/claude-3.5-sonnet` / `google/gemini-2.0-flash`).
* Desktop error dialog and IDE terminal OCR inspection.

---

## 6. Execution Guidelines

* Always verify each phase with mocked unit tests (`backend/tests/`) before proceeding to the next.
* Maintain deterministic safety checks in `permissions.py` — never allow an LLM to self-authorize.
* Keep context token footprints minimal and leverage two-stage compaction to preserve speed and low VRAM usage on the RTX 4060.
