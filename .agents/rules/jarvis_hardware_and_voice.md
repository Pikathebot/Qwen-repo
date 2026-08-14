# Jarvis Local Hardware & Voice Invariants

## Hardware Governor & VRAM Management
1. **Self-Inference Gating**: Any resource governor monitoring GPU/VRAM must check `is_inferencing`. High GPU load during active AI inference is normal and must NOT trigger auto-eviction or self-throttling.
2. **Idle Game Protection**: VRAM auto-eviction (`keep_alive: 0`) must only engage when sustained high GPU/VRAM load (>= 4s) occurs while Jarvis is IDLE.
3. **Model Selection on 8GB VRAM**: Default to `hermes3:8b` for structured tool calling and `llama3.2:3b` for ultra-fast light tasks. Avoid sub-1B models for tool execution.

## Voice & Audio Architecture
1. **Audio Capture**: In Edge WebView2 environments, do not rely exclusively on `webkitSpeechRecognition`. Always provide `MediaRecorder` capturing raw audio and dispatching to `/voice/transcribe`.
2. **Neural TTS**: For spoken responses, prefer neural speech models (`edge-tts` with `en-GB-RyanNeural`) streamed over `/voice/tts` to maintain a natural, humanlike assistant persona.
