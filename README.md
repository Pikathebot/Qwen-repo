# Jarvis — Private Local AI Assistant for Windows

A private, fast, and lightweight local AI assistant for Windows 11 powered by Ollama (`qwen3.5:9b`), with Raycast-inspired glassmorphic floating UI, Windows System Tray integration, Model Context Protocol (MCP), dynamic skills loading, hardware resource governance, and voice interaction.

---

## Key Features

- **Floating Spotlight UI**: Sleek, keyboard-first desktop overlay triggered globally with `Alt+Space` or `Ctrl+Space`.
- **Windows System Tray**: Background service managing process lifecycles and displaying live hardware status.
- **Hardware Resource Governor**: Real-time PyNVML GPU/VRAM telemetry protecting your RTX 4060 GPU and CPU from overload.
- **Deterministic Safety Permissions**: $O(1)$ hardcoded security tiering (`LOW_RISK`, `CONFIRMATION_REQUIRED`, `HIGH_RISK`) with SHA256 action approval tokens.
- **Model Routing (Normal vs Heavy)**: Runs locally on Ollama for maximum privacy, and dynamically routes heavy math/architecture tasks to OpenRouter when needed.
- **SQLite Short-Term Memory**: Multi-turn conversation store with automatic progressive context compaction (16,000 token context window).
- **Model Context Protocol (MCP)**: Bidirectional JSON-RPC 2.0 stdio client for external tools and servers.
- **Dynamic Skills Loader**: Extensible Markdown-based domain skills (`skills/*.md`) with trigger keyword matching.
- **Hands-Free Voice & Wake-Word**: Wake-word detection ("Jarvis" / "Hey Jarvis") with speech recognition and natural text-to-speech sanitization.

---

## Quick Start

### 1. Launch Jarvis
Double-click **`Jarvis Assistant`** on your Desktop or run:
```powershell
d:/JARVIS/.venv/Scripts/python d:/JARVIS/run_jarvis.py
```

### 2. Pin to Windows Taskbar
1. Right-click the **`Jarvis Assistant`** shortcut on your Desktop or in `D:\JARVIS\`.
2. Select **"Pin to taskbar"**.

### 3. Run Automated Tests
```powershell
$env:PYTHONPATH="d:/JARVIS/backend;d:/JARVIS"; d:/JARVIS/.venv/Scripts/pytest d:/JARVIS/backend/tests -v
```

---

## Documentation

Detailed documentation is available in the [`docs/`](file:///d:/JARVIS/docs) directory:
- [**ARCHITECTURE.md**](file:///d:/JARVIS/docs/ARCHITECTURE.md): Complete architectural deep dive across all 8 subsystem layers.
- [**API_REFERENCE.md**](file:///d:/JARVIS/docs/API_REFERENCE.md): Comprehensive REST API endpoint reference.
- [**USER_GUIDE.md**](file:///d:/JARVIS/docs/USER_GUIDE.md): Keyboard shortcuts, voice controls, custom skills, and configuration.
- [**PLAN.md**](file:///d:/JARVIS/PLAN.md): Implementation milestones and design roadmap.
