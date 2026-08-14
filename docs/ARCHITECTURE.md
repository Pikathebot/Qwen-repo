# Jarvis Assistant — System Architecture

This document provides a comprehensive technical overview of the Jarvis Local AI Assistant architecture across all 8 subsystem layers.

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DESKTOP CLIENT & TRAY                             │
│   • Spotlight Overlay (pywebview)        • Windows System Tray (pystray)    │
│   • Global Hotkeys (Alt+Space / Ctrl+Space) • Voice / Wake-Word ("Jarvis")  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP JSON-RPC
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
│  └─────────────────────────┘                       │   • list_directory  │  │
│                                                    │   • MCP Tools       │  │
│                                                    └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Subsystems

### 1. Agent Orchestrator & Native Tool Loop (`backend/app/agent/`)
- **`orchestrator.py`**: Manages the iterative tool calling loop with Ollama and OpenRouter.
- **`tool_registry.py`**: Native tool registration with docstring parsing and schema extraction.
- **Introspection & Validation**: Uses Python's `inspect.signature` to validate LLM tool call arguments against function definitions, preventing hallucinations and signature mismatches.

### 2. Safety Permission Layer (`backend/app/agent/permissions.py`)
- **Deterministic Hardcoded Evaluation**: Zero-overhead $O(1)$ rule table mapping operations to risk tiers:
  - `LOW_RISK`: Automatically executed without user confirmation (`read_file`, `list_directory`).
  - `CONFIRMATION_REQUIRED`: Blocks execution and returns approval tokens (`write_file`, `execute_command`).
  - `HIGH_RISK`: Always requires confirmation (`delete_file`, destructive shell commands like `rm -rf`, `Format-Volume`).
- **Canonical Action Token Hashing**: Generates unique SHA-256 tokens (`act_<hash>`) for each blocked action, preventing replay attacks or hallucinated approvals.

### 3. Hardware Resource Governor (`backend/app/governor/`)
- **Real-Time Telemetry**: Uses `nvidia-ml-py` (PyNVML) to poll NVIDIA RTX 4060 GPU utilization, VRAM usage (MB and percentage), and temperature (°C), along with `psutil` for host CPU/RAM.
- **Adaptive Queueing & Overload Protection**: If hardware thresholds are exceeded, requests enter an adaptive waiting queue (`wait_until_healthy`). If the system remains overloaded beyond the timeout, HTTP 429 is returned to protect local hardware stability.

### 4. Model Router & Heavy Mode (`backend/app/agent/model_router.py`)
- **Dynamic Complexity Analysis**: Evaluates query depth, multi-step code synthesis, formal mathematical proofs, and architectural design prompts.
- **Dual-Tier Routing**:
  - **Normal Mode**: Runs locally on Ollama (`qwen3.5:9b` or `qwen2.5:0.5b`) ensuring complete offline privacy.
  - **Heavy Mode**: Routes complex tasks to high-capacity cloud models (e.g. `deepseek/deepseek-chat` or `anthropic/claude-3.5-sonnet`) via OpenRouter, with automatic fallback to local Ollama on failure.

### 5. Short-Term Memory & Context Compaction (`backend/app/memory/`)
- **SQLite Storage**: Relational message store in `data/jarvis_memory.db` tracking conversation turns, role metadata, and timestamps.
- **Two-Stage Progressive Compaction**:
  - **Stage 1 (Tool Pruning)**: Truncates verbose tool output dumps (>200 characters) in older turns to concise summaries.
  - **Stage 2 (LLM Summarization)**: Compresses older 50% turns into compact bullet points while preserving recent turns verbatim.
  - Transparent audit logging in `compaction_events` table.

### 6. Model Context Protocol (MCP) & Skills (`backend/app/mcp/`, `backend/app/skills/`)
- **MCP Stdio Client**: Async JSON-RPC 2.0 protocol client communicating with external subprocess tools.
- **Built-in Diagnostics Server**: Provides `get_disk_usage` and `get_system_uptime`.
- **Dynamic Skills Loader**: Parses YAML frontmatter and markdown instructions from `skills/*.md`. Dynamically matches triggers in user messages and injects specialized instructions without bloating base context.

### 7. Desktop Client & System Tray (`desktop/`)
- **Floating Spotlight Overlay**: Frameless glassmorphic search bar built with HTML5, CSS3, and `pywebview`.
- **Global Hotkey Daemon**: System-wide `Alt+Space` and `Ctrl+Space` triggers via `pynput`.
- **Windows System Tray**: Background service powered by `pystray` with live telemetry overview.

### 8. Voice & Wake-Word Engine (`backend/app/voice/`)
- **Wake-Word Detector**: Regex keyword spotter listening for `"Jarvis"`, `"Hey Jarvis"`, and variants.
- **Speech Sanitizer & Synthesizer**: Cleans markdown formatting, code blocks, and URLs for natural vocalization.
- **Web Speech API**: Zero-latency voice recognition and streaming dictation in the desktop UI.
