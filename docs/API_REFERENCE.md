# Jarvis Assistant — API Reference

The Jarvis backend exposes RESTful endpoints at `http://127.0.0.1:8000`.

---

## Endpoints

### 1. Chat & Inference

#### `POST /chat`
Execute a chat turn with orchestrator, memory, tools, and skills.

**Request Body (`application/json`):**
```json
{
  "message": "Please list the files in the docs directory.",
  "session_id": "default",
  "model": "qwen2.5:0.5b",
  "mode": "auto",
  "system_prompt": null,
  "approved_action_ids": ["act_1a2b3c4d5e6f"]
}
```

**Response (`200 OK`):**
```json
{
  "response": "Here are the files in docs: PLAN.md, ARCHITECTURE.md",
  "model": "qwen2.5:0.5b",
  "provider": "ollama",
  "status": "completed",
  "session_id": "default",
  "route_reason": "Default normal mode",
  "fallback_used": false,
  "compaction_performed": null,
  "active_skills": [],
  "tools_used": [
    {
      "tool": "list_directory",
      "args": { "path": "docs" },
      "output_preview": "['PLAN.md', 'ARCHITECTURE.md']"
    }
  ],
  "pending_confirmations": []
}
```

---

### 2. System Status & Telemetry

#### `GET /health`
Returns backend connectivity, Ollama status, Resource Governor load, and subsystem counts.

**Response (`200 OK`):**
```json
{
  "status": "ok",
  "ollama_host": "http://localhost:11434",
  "ollama_connected": true,
  "configured_model": "qwen3.5:9b",
  "available_models": ["qwen3.5:9b", "qwen2.5:0.5b"],
  "governor_throttled": false,
  "openrouter_configured": true,
  "active_sessions_count": 3,
  "active_mcp_servers_count": 1,
  "available_skills_count": 2,
  "voice_enabled": true
}
```

#### `GET /governor/status`
Returns real-time GPU/VRAM/CPU telemetry metrics.

**Response (`200 OK`):**
```json
{
  "enabled": true,
  "throttled": false,
  "throttle_reasons": [],
  "metrics": {
    "cpu_percent": 12.4,
    "ram_percent": 54.2,
    "gpu_available": true,
    "gpu_name": "NVIDIA GeForce RTX 4060 Laptop GPU",
    "gpu_util_percent": 8.0,
    "vram_util_percent": 34.5,
    "vram_used_mb": 2824.0,
    "vram_total_mb": 8188.0,
    "gpu_temp_c": 51.0,
    "timestamp": 1723625400.0
  },
  "thresholds": {
    "gpu_threshold": 95.0,
    "vram_threshold": 95.0,
    "cpu_threshold": 95.0,
    "ram_threshold": 95.0
  }
}
```

---

### 3. Memory & Sessions

#### `GET /sessions`
List all active session identifiers and creation timestamps.

#### `GET /sessions/{session_id}/messages`
Retrieve the ordered message history for a specific conversation session.

#### `GET /sessions/{session_id}/compactions`
Retrieve compaction audit events and token reduction ratios for a session.

#### `DELETE /sessions/{session_id}`
Delete a conversation session and all its stored messages.

---

### 4. Skills & MCP

#### `GET /skills`
List all discovered markdown skills, descriptions, and trigger patterns.

#### `POST /skills/reload`
Hot-reload all markdown skill definitions from the `skills/` folder without restarting the backend.

#### `GET /mcp/servers`
List active Model Context Protocol (MCP) servers and their registered tool definitions.

---

### 5. Voice & Wake-Word

#### `GET /voice/status`
Returns wake-word detector status, configured wake phrases, and active synthesizer voice.

#### `POST /voice/speak`
Sanitizes markdown tags and prepares text for speech synthesis.

#### `POST /voice/transcribe`
Accepts an audio file upload (`multipart/form-data`) and returns transcribed text.
