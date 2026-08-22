# Jarvis Local Hardware & Voice Invariants

## Hardware Governor & VRAM Management
1. **Self-Inference Gating**: Any resource governor monitoring GPU/VRAM must check `is_inferencing`. High GPU load during active AI inference is normal and must NOT trigger auto-eviction or self-throttling.
2. **Zero Live Model Calls in Test Suite (CRITICAL)**: Unit and integration tests (pytest) must NEVER execute live model calls (Ollama or LM Studio). All tests MUST mock LLM responses in-memory using `unittest.mock.patch` / Mock clients to prevent laptop GPU overload or dual-model VRAM contention.
3. **Model Architecture (Stage B)**: Default inference backend is `prism-ml/bonsai-27b` via LM Studio (`http://localhost:1234/v1`). Ollama (`hermes3:8b`) serves as the rollback target.
4. **LM Studio VRAM Eviction**: LM Studio HTTP API has no REST unload endpoint (`/api/v0/models/unload` does not exist). Model eviction must be performed via the official `lms` CLI (`lms.exe unload --all`), failing loudly with a warning if the CLI is missing or errors.
5. **Governor RAM Calibration & Auto-Unload Gating**: Windows OS RAM caching naturally sits at 95–97%. VRAM auto-unload must NEVER trigger on passive OS RAM load alone; it is strictly gated to active GPU compute, VRAM saturation, or confirmed external 3D/gaming processes.
6. **Thinking Model Timeout Headroom**: Reasoning models (e.g. Bonsai 27B) produce hundreds of `reasoning_content` tokens prior to tool calls. Client and UI fetch timeouts must provide at least 180s headroom to prevent premature request aborts.

## Voice & Audio Architecture
1. **Audio Capture**: In Edge WebView2 environments, do not rely exclusively on `webkitSpeechRecognition`. Always provide `MediaRecorder` capturing raw audio and dispatching to `/voice/transcribe`.
2. **Neural TTS**: For spoken responses, prefer neural speech models (`edge-tts` with `en-GB-RyanNeural`) streamed over `/voice/tts` to maintain a natural, humanlike assistant persona.
