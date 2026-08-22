# JARVIS Assistant — Stage B Migration & Governor V2 Implementation Diff Report

This document details all structural additions, modifications, and bugfixes applied across the codebase according to the **Stage B Spec (LM Studio Bonsai 27B Migration)**, the **Governor V2 Spec (Activity-Aware, Debounced, Overridable, Observable & Process Watcher)**, and the subsequent **reliability, VRAM eviction, and timeout hardening fixes**.

---

## 1. Summary of Changes

| Subsystem | Key Files | Description |
|---|---|---|
| **Stage B: Model Migration** | `config.py`, `lmstudio_client.py`, `model_router.py`, `orchestrator.py` | Migrated default inference to LM Studio `prism-ml/bonsai-27b` with Ollama `hermes3:8b` as rollback target. Added OpenAI function tool conversions and `lms` CLI integration. |
| **Governor V2 Core** | `resource_governor.py`, `config.py`, `main.py` | Added `ActivityType` registry, async context managers, 2-sided debounced hysteresis, manual overrides (`force_pause`, `force_resume`), and a 50-event history ring buffer. |
| **Process Watcher** | `process_watcher.py`, `governor_watchlist.json` | Deterministic process scanner for heavy 3D/gaming executables with 4s launch debounce, 3s recovery debounce, mid-turn deferral, and lazy reload on close. |
| **Reliability & Eviction Fixes** | `orchestrator.py`, `lmstudio_client.py`, `desktop/ui/app.js`, `resource_governor.py`, `main.py` | Fixed `PermissionDecision` attribute mismatch (`p.tool`/`p.args`), extended timeout to 180s for deep reasoning, gated auto-unloading to GPU/gaming loads, and wired verified `lms unload --all` eviction. |
| **Desktop Launcher** | `run_jarvis.py`, `run_jarvis.spec` | Fixed shortcut working directory resolution and added socket IPC (`127.0.0.1:57321`) to prevent duplicate instances. |
| **Test Suite Isolation** | `test_governor.py`, `test_process_watcher.py`, `test_permissions.py`, `test_lmstudio_client.py` | 100% mocked isolation for pytest — 130/130 tests passing with zero VRAM impact. |

---

## 2. Configuration Changes

### `backend/app/config.py`
```diff
@@ -9,13 +9,25 @@
+    # Active Model Backend (Stage B: "bonsai" default, "hermes3" rollback target)
+    active_model_backend: str = "bonsai"
+
+    # LM Studio Local Configuration
+    lmstudio_base_url: str = "http://localhost:1234/v1"
+    lmstudio_model: str = "prism-ml/bonsai-27b"
+
+    # Local Ollama Configuration (Rollback Target)
+    ollama_host: str = "http://localhost:11434"
+    ollama_model: str = "hermes3:8b"
+    
     # Server Configuration
     app_host: str = "127.0.0.1"
     app_port: int = 8000
 
-    # Resource Governor Settings
+    # Resource Governor V2 Settings
     governor_enabled: bool = True
     governor_poll_interval: float = 1.0
-    governor_gpu_threshold: float = 85.0
-    governor_vram_threshold: float = 99.0
-    governor_cpu_threshold: float = 95.0
-    governor_ram_threshold: float = 95.0
+    governor_gpu_threshold: float = 88.0
+    governor_vram_threshold: float = 92.0
+    governor_cpu_threshold: float = 95.0
+    governor_ram_threshold: float = 98.5
+    governor_sustained_breach_polls: int = 3
+    governor_recovery_polls: int = 2
+    governor_startup_grace_seconds: float = 20.0
     governor_queue_timeout_seconds: float = 3.0
+    governor_watchlist_path: str = os.path.join(BASE_DIR.parent, "governor_watchlist.json")
+    governor_process_poll_interval: float = 2.0
+    governor_process_launch_debounce: float = 4.0
+    governor_process_recovery_debounce: float = 3.0
```

---

## 3. Stage B: LM Studio Integration & Model Routing

### `backend/app/agent/lmstudio_client.py` (New Module)
```python
import inspect
import json
import logging
import os
import shutil
import asyncio
from typing import Any, Callable, Optional
import httpx
from app.config import settings
from app.agent.tools.registry import TOOL_SCHEMAS

logger = logging.getLogger("jarvis.agent.lmstudio")

def convert_tool_to_openai_schema(tool: Any) -> Optional[dict[str, Any]]:
    """Converts native Python tools and MCP tools to OpenAI JSON Schema."""
    if isinstance(tool, dict):
        if "type" in tool and tool["type"] == "function" and "function" in tool:
            return tool
        if "name" in tool and "parameters" in tool:
            return {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool["parameters"]
                }
            }
        return None

    if callable(tool):
        fn_name = getattr(tool, "__name__", str(tool))
        doc = inspect.getdoc(tool) or f"Execute {fn_name}."
        short_desc = doc.strip().split("\n")[0] if doc else f"Execute {fn_name}."
        schema_cls = TOOL_SCHEMAS.get(fn_name)
        parameters = {
            "type": "object",
            "properties": schema_cls.model_json_schema().get("properties", {}) if schema_cls else {},
            "required": schema_cls.model_json_schema().get("required", []) if schema_cls else []
        }
        return {
            "type": "function",
            "function": {"name": fn_name, "description": short_desc, "parameters": parameters}
        }
    return None

class LMStudioClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 180.0, api_key: str = "lm-studio"):
        self.base_url = (base_url or settings.lmstudio_base_url).rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    def _get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._get_headers())
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        models = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._get_headers())
                if resp.status_code == 200:
                    for item in resp.json().get("data", []):
                        m_id = item.get("id") or item.get("name")
                        if m_id:
                            models.append(m_id)
        except Exception as e:
            logger.warning("Failed to list models from LM Studio: %s", e)
        return models

    async def unload_model(self, model_name: Optional[str] = None) -> bool:
        """
        Unloads model(s) from GPU VRAM via LM Studio's official `lms` CLI utility.
        Returns True on confirmed eviction, False otherwise.
        """
        lms_bin = shutil.which("lms")
        if not lms_bin:
            default_path = os.path.expanduser(r"~\.lmstudio\bin\lms.exe")
            if os.path.exists(default_path):
                lms_bin = default_path

        if not lms_bin:
            logger.warning(
                "LM Studio CLI ('lms') not found in PATH or at default location (~\\.lmstudio\\bin\\lms.exe). "
                "Cannot automatically evict LM Studio models from GPU VRAM."
            )
            return False

        try:
            cmd = [lms_bin, "unload", model_name] if model_name else [lms_bin, "unload", "--all"]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=8.0)

            if proc.returncode == 0:
                out_msg = stdout.decode("utf-8", errors="ignore").strip()
                logger.info("LM Studio model(s) successfully evicted via 'lms' CLI: %s", out_msg or "OK")
                return True
            else:
                err_msg = stderr.decode("utf-8", errors="ignore").strip()
                logger.warning("LM Studio 'lms unload' failed (exit code %d): %s", proc.returncode, err_msg)
                return False
        except Exception as e:
            logger.warning("LM Studio CLI unload execution error: %s", e)
            return False

    async def chat(self, messages: list[dict[str, Any]], model: str, tools: Optional[list[Any]] = None, temperature: float = 0.7, timeout: Optional[float] = None) -> dict[str, Any]:
        req_timeout = timeout or self.timeout
        url = f"{self.base_url}/chat/completions"
        payload = {"model": model, "messages": messages, "temperature": temperature}

        if tools:
            formatted_tools = [convert_tool_to_openai_schema(t) for t in tools if convert_tool_to_openai_schema(t)]
            if formatted_tools:
                payload["tools"] = formatted_tools
                payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=req_timeout) as client:
            resp = await client.post(url, json=payload, headers=self._get_headers())

        if resp.status_code != 200:
            raise RuntimeError(f"LM Studio returned HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}, "raw": data}

        msg = choices[0].get("message", {})
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        tool_calls = msg.get("tool_calls")

        normalized_calls = None
        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
            normalized_calls = []
            for tc in tool_calls:
                fn_obj = tc.get("function", {})
                raw_args = fn_obj.get("arguments", {})
                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args if isinstance(raw_args, dict) else {})
                normalized_calls.append({"id": tc.get("id"), "type": "function", "function": {"name": fn_obj.get("name", ""), "arguments": parsed_args}})

        if not content and reasoning and not normalized_calls:
            lines = [l.strip() for l in reasoning.strip().split("\n") if l.strip()]
            if lines:
                content = lines[-1].lstrip("#*- ").strip()

        return {"message": {"role": "assistant", "content": content, "reasoning_content": reasoning, "tool_calls": normalized_calls}, "raw": data}
```

---

## 4. Full Governor V2 Implementation

### `backend/app/governor/resource_governor.py`
```python
@dataclass
class GovernorEvent:
    timestamp: float = field(default_factory=time.time)
    from_status: str = "NORMAL"
    to_status: str = "NORMAL"
    raw_reasons: list[str] = field(default_factory=list)
    metrics_snapshot: Optional[SystemMetrics] = None
    active_activities: list[str] = field(default_factory=list)

class ResourceGovernor:
    def begin_activity(self, activity_type: Union[ActivityType, str], label: Optional[str] = None) -> str:
        act_enum = ActivityType(activity_type) if isinstance(activity_type, str) else activity_type
        activity_id = f"act_{uuid.uuid4().hex[:8]}"
        record = ActivityRecord(activity_id=activity_id, activity_type=act_enum, label=label, started_at=time.time())
        self._active_activities[activity_id] = record
        self._throttle_streak = 0
        logger.debug("Governor activity begun: %s (%s) [ID: %s]", act_enum.value, label, activity_id)
        self._check_status_transition()
        return activity_id

    def end_activity(self, activity_id: str) -> None:
        removed = self._active_activities.pop(activity_id, None)
        if removed:
            logger.debug("Governor activity ended: %s [ID: %s]", removed.activity_type.value, activity_id)
            if not self.is_busy and self._pending_external_app_unloads:
                apps_list = list(self._pending_external_app_unloads)
                self._pending_external_app_unloads.clear()
                logger.info("Governor: Applying deferred external app auto-unload for %s now that Jarvis is idle.", ", ".join(apps_list))
                self._trigger_unload_callback()
            self._check_status_transition()

    def force_pause(self, reason: str = "manual override") -> None:
        self._manual_paused = True
        self._manual_pause_reason = reason
        self._manual_resume_override_until = None
        logger.info("Governor manually PAUSED (reason: %s)", reason)
        self._check_status_transition()

    def force_resume(self) -> None:
        self._manual_paused = False
        self._manual_pause_reason = None
        self._manual_resume_override_until = None
        logger.info("Governor manually RESUMED (automatic mode restored)")
        self._check_status_transition()

    def force_resume_ignore_metrics(self, duration_seconds: Optional[float] = None) -> None:
        self._manual_paused = False
        self._manual_pause_reason = None
        if duration_seconds is not None:
            self._manual_resume_override_until = time.time() + float(duration_seconds)
            logger.info("Governor override active: Ignoring metrics for %.1f seconds", duration_seconds)
        else:
            self._manual_resume_override_until = float("inf")
            logger.info("Governor override active: Ignoring metrics indefinitely")
        self._check_status_transition()

    def get_history(self, limit: int = 50) -> list[GovernorEvent]:
        items = list(self._history)
        items.reverse()
        return items[:limit]

    def _trigger_unload_callback(self) -> None:
        if not self.on_throttle_unload:
            return

        async def _execute_unload():
            try:
                logger.warning("Governor AUTO-UNLOAD: Evicting models from GPU VRAM to yield to external workload.")
                res = await self.on_throttle_unload() if asyncio.iscoroutinefunction(self.on_throttle_unload) else self.on_throttle_unload()
                if res is not False:
                    self._has_auto_unloaded = True
                    logger.info("Governor: Model eviction callback completed successfully.")
                else:
                    logger.warning("Governor: Model eviction callback reported partial or failed unload.")
            except Exception as e:
                logger.error("Error executing governor unload callback: %s", e)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_execute_unload())
        except RuntimeError:
            asyncio.run(_execute_unload())
```

---

## 5. Main API Routes

### `backend/app/main.py`
```python
@app.post("/governor/pause")
async def governor_pause(req: Optional[GovernorPauseRequest] = None):
    reason = req.reason if req and req.reason else "manual override"
    governor.force_pause(reason=reason)
    return {"status": "ok", "governor_status": governor.status.value, "reason": reason}

@app.post("/governor/resume")
async def governor_resume():
    governor.force_resume()
    return {"status": "ok", "governor_status": governor.status.value}

@app.post("/governor/resume-override")
async def governor_resume_override(req: Optional[GovernorResumeOverrideRequest] = None):
    duration = req.duration_seconds if req else None
    governor.force_resume_ignore_metrics(duration_seconds=duration)
    return {"status": "ok", "governor_status": governor.status.value, "duration_seconds": duration}

@app.get("/governor/history")
async def governor_history(limit: int = 20):
    events = governor.get_history(limit=limit)
    return [
        {
            "timestamp": e.timestamp,
            "from_status": e.from_status,
            "to_status": e.to_status,
            "raw_reasons": e.raw_reasons,
            "active_activities": e.active_activities,
            "metrics_snapshot": {
                "cpu_percent": e.metrics_snapshot.cpu_percent,
                "ram_percent": e.metrics_snapshot.ram_percent,
                "gpu_util_percent": e.metrics_snapshot.gpu_util_percent,
                "vram_util_percent": e.metrics_snapshot.vram_util_percent,
            } if e.metrics_snapshot else None
        }
        for e in events
    ]
```

---

## 6. Test Suite Status

```text
============================= 130 passed in 41.91s ==============================
- test_governor.py: 9 passed
- test_process_watcher.py: 5 passed
- test_permissions.py: 16 passed
- test_lmstudio_client.py: 7 passed
- test_model_router.py: 12 passed
- test_tools.py: 22 passed
- test_main.py: 18 passed
- test_memory.py: 14 passed
- test_voice.py: 10 passed
- test_mcp_skills.py: 17 passed
```
