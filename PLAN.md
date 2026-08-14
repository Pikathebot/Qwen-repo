# Jarvis Assistant — System Master Plan & Autonomous Evolution

**Stack:** FastAPI + Ollama (`qwen3.5:9b` / `qwen2.5:0.5b`) + OpenRouter (Heavy Mode & Vision fallback)  
**Target Machine:** Windows 11, Intel i7-14700HX (20 threads), NVIDIA RTX 4060 Laptop GPU (8GB VRAM), 16GB DDR5 RAM  
**Repository:** `d:/JARVIS`  

---

## 0. Project Vision & Architecture Comparison

Jarvis is a private, lightning-fast, hardware-governed AI assistant for Windows. Following our design interview, Jarvis is evolving into an autonomous, proactive, multi-channel personal assistant comparable to **OpenClaw** (formerly Warelay / Moltbot), **Open Interpreter**, and **Claude Computer Use**, while preserving its local privacy, deterministic safety permissions, and RTX 4060 GPU governor.

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
│  │  │   • Fast HTML Scraper   │  │     • patch_file                   │  │  │
│  │  │   • Playwright Dynamic  │  │     • search_files (grep/glob)     │  │  │
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

## 1. Resolved Design Tree Decisions (Grill-Me Alignment)

| Decision Area | Agreed Architecture | Rationale |
| :--- | :--- | :--- |
| **Remote Access Channel** | **Telegram Bot with Admin ID Whitelist** | Secure mobile access from anywhere, push notifications, and inline approval buttons for blocked actions. |
| **Web Research Architecture** | **Hybrid (Zero-Key DuckDuckGo + Fast Scraper + Playwright Fallback)** | Free, private, lightweight search by default via `ddgs` + `httpx`, falling back to Playwright for dynamic JS pages. |
| **File Safety Boundaries** | **Workspace-Aware Gating** | Auto-permits safe read/writes inside designated project folders; blocks and asks confirmation for paths outside workspace or in system directories. |
| **Vision Strategy** | **Unified / Smart Multimodal Routing** | Prevents VRAM swapping churn on the 8GB RTX 4060 GPU while enabling multi-monitor screenshot diagnostics. |
| **Long-Term Memory** | **Hybrid Local RAG (SQLite FTS5 + LanceDB / Chroma)** | High-precision exact keyword search combined with dense vector semantic search over user notes and docs. |
| **Autonomous Engine** | **Dual Scheduler (Preset Routines + Natural Language Reminders)** | Morning briefings and health monitors alongside on-the-fly conversational timers ("Remind me in 30 mins"). |
| **Windows Desktop Controls** | **Core Desktop Power Tools** | Native app launcher, audio/media keys, active clipboard, process manager, and Windows Toast notifications. |
| **Skills System** | **Enhanced Hybrid Skills** | Markdown files with YAML metadata declaring required tools, trigger keywords, and step-by-step execution workflows. |

---

## 2. Foundational Milestones (Status: Complete)

- [x] **Phase 0 — FastAPI Skeleton**: Async `/chat` endpoint calling Ollama with Pydantic validation.
- [x] **Phase 1 — Basic Native Tool Loop**: Function calling with inspect-based parameter filtering (`read_file`, `list_directory`).
- [x] **Phase 2 — Deterministic Safety Permissions**: $O(1)$ hardcoded tier lookup (`LOW_RISK`, `CONFIRMATION_REQUIRED`, `HIGH_RISK`) with SHA256 canonical action token hashes (`act_<hash>`).
- [x] **Phase 3 — Hardware Resource Governor**: PyNVML GPU/VRAM telemetry + `psutil` CPU/RAM monitoring with automatic VRAM model eviction under load.
- [x] **Phase 4 — Model Router & Heavy Mode**: Dynamic prompt complexity analyzer routing simple queries to local Ollama and heavy architecture/math to OpenRouter with automatic fallback.
- [x] **Phase 5 — SQLite Short-Term Memory & Compaction**: SQLite message history with two-stage compaction (verbose tool output pruning + LLM summarization).
- [x] **Phase 6 — MCP Bridge & Dynamic Skills Loader**: Async stdio JSON-RPC 2.0 client + dynamic keyword-matching markdown skills loader.
- [x] **Phase 7 — Desktop UI & System Tray**: Frameless pywebview spotlight overlay (`Alt+Space`), Windows system tray with live hardware status.
- [x] **Phase 8 — Voice & Wake-Word Engine**: "Jarvis" wake-word detection, Web Speech API dictation, and speech sanitization.

---

## 3. OpenClaw Evolution Roadmap

```
Phase 1: Web Research Engine (DuckDuckGo + Fast HTML Scraper + Dynamic Fallback)
   ↓
Phase 2: File Creation, Patching & Workspace Safety Gating
   ↓
Phase 3: Windows OS Power Controls & Desktop Toast Alerts
   ↓
Phase 4: Multi-Monitor Screen Vision & Visual Diagnostics
   ↓
Phase 5: Proactive Background Scheduler & Autonomous Watchers
   ↓
Phase 6: Long-Term Memory & Hybrid Local RAG (Notes/Docs Indexing)
   ↓
Phase 7: Remote Telegram Bot Gateway with Interactive Approval Buttons
   ↓
Phase 8: Enhanced Executable Skills & Workflows
```

---

## 4. Phase 1 Detailed Plan: Web Research Engine

### Objective
Enable Jarvis to search the public web in real-time without external API keys, extract readable markdown from articles and documentation, and handle dynamic JavaScript-rendered sites when needed.

### Components to Build

#### 1. Web Search Tool (`backend/app/agent/tools/web_search.py`)
* **Package**: `duckduckgo_search` (`ddgs`)
* **Function**: `web_search(query: str, max_results: int = 5) -> str`
* **Features**:
  * Clean, formatted JSON/markdown result cards: Title, URL, and snippet.
  * Automatic deduplication of search results.
  * Configurable result limits (default 5, max 10) to protect context window tokens.
  * Graceful network timeout & error formatting.

```python
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo for live information, current documentation, or news.
    
    Args:
        query: The search query string.
        max_results: Number of top results to return (default 5, max 10).
    """
```

#### 2. Fast HTML Scraper & Article Extractor (`backend/app/agent/tools/fetch_url.py`)
* **Packages**: `httpx`, `trafilatura` (or `beautifulsoup4` + `html2text`)
* **Function**: `fetch_url(url: str, max_chars: int = 8000) -> str`
* **Features**:
  * Strips out boilerplate, navigation bars, cookie banners, and advertisements.
  * Converts core content into clean, readable Markdown.
  * Enforces a strict character cap (`max_chars`, default 8,000) to keep LLM context lightweight and fast.
  * Browser User-Agent header rotation to avoid anti-bot blocks.

```python
def fetch_url(url: str, max_chars: int = 8000) -> str:
    """
    Fetch the content of a web page URL and return its main article text in clean markdown.
    
    Args:
        url: The web URL to fetch.
        max_chars: Maximum characters to return (default 8000).
    """
```

#### 3. Dynamic Browser Fallback (`backend/app/agent/tools/dynamic_fetch.py`)
* **Package**: `playwright` (optional/on-demand)
* **Function**: `fetch_dynamic_url(url: str, wait_selector: Optional[str] = None) -> str`
* **Features**:
  * Spins up headless Chromium only when simple HTTP fetching returns empty content (e.g. Single-Page React/Vue apps).
  * Auto-closes browser instance to prevent memory leaks.

#### 4. Permission Gating & Safety Integration
* `web_search`: Classified as `LOW_RISK` (auto-executes without confirmation).
* `fetch_url`: Classified as `LOW_RISK` for public `http://` and `https://` URLs; internal local IP ranges (`127.0.0.1`, `192.168.*`, `10.*`) trigger `CONFIRMATION_REQUIRED` to protect local network security.

#### 5. Tool Registry & Orchestrator Integration
* Register `web_search` and `fetch_url` in `backend/app/agent/tools/registry.py`.
* Update orchestrator prompt rules to guide the model when searching vs. fetching.

---

## 5. Phase 1 Verification & Testing Plan

### Automated Test Suite (`backend/tests/test_web_tools.py`)
1. **`test_web_search_mocked`**: Verify search query packaging, result parsing, and token trimming.
2. **`test_fetch_url_html_conversion`**: Verify HTML boilerplate stripping and markdown formatting.
3. **`test_fetch_url_character_budgeting`**: Verify content truncation respect `max_chars`.
4. **`test_permission_classification_web`**: Verify `web_search` is `LOW_RISK` and private subnet fetches require confirmation.

### Manual Verification Checklist
- [ ] Run `web_search(query="Python 3.12 new features")` in Jarvis Spotlight (`Alt+Space`) and receive a coherent, up-to-date answer.
- [ ] Ask Jarvis to read a specific documentation page (e.g., `fetch_url("https://fastapi.tiangolo.com")`) and answer questions based on the live content.
- [ ] Confirm that search results are cleanly trimmed and do not blow out the 16K token compaction window.

---

## 6. Execution Guidelines

* Always build one phase at a time and verify with tests before proceeding to the next.
* Maintain deterministic safety checks in `permissions.py` — never allow an LLM to self-authorize.
* Keep context token footprints minimal to maintain fast response times and low VRAM overhead on the RTX 4060.
