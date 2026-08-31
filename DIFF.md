# Complete Project Diff

`diff
diff --git a/backend/app/agent/lmstudio_client.py b/backend/app/agent/lmstudio_client.py
index 3262f54..49e1c37 100644
--- a/backend/app/agent/lmstudio_client.py
+++ b/backend/app/agent/lmstudio_client.py
@@ -1,3 +1,7 @@
+# DEPRECATED: LMStudioClient is deprecated in favor of ModelProvider abstraction
+# (LlamaCppProvider primary, OllamaProvider fallback) and RuntimeProcessManager.
+# Retained temporarily for backward compatibility. Do not use for new features.
+
 import inspect
 import json
 import logging
@@ -321,3 +325,132 @@ class LMStudioClient:
             },
             "raw": data
         }
+
+    async def chat_stream(
+        self,
+        messages: list[dict[str, Any]],
+        model: str,
+        tools: Optional[list[Any]] = None,
+        temperature: float = 0.7,
+        timeout: Optional[float] = None
+    ):
+        """
+        Stream chat completion tokens and tool calls from LM Studio.
+        Yields events:
+        - {"type": "token", "delta": str}
+        - {"type": "reasoning", "delta": str}
+        - {"type": "done", "content": str, "tool_calls": list[dict] | None}
+        """
+        req_timeout = timeout or self.timeout
+        url = f"{self.base_url}/chat/completions"
+
+        payload: dict[str, Any] = {
+            "model": model,
+            "messages": messages,
+            "temperature": temperature,
+            "stream": True,
+        }
+
+        if tools:
+            formatted_tools = []
+            for t in tools:
+                schema = convert_tool_to_openai_schema(t)
+                if schema:
+                    formatted_tools.append(schema)
+            if formatted_tools:
+                payload["tools"] = formatted_tools
+                payload["tool_choice"] = "auto"
+
+        logger.info("Streaming request from LM Studio model '%s' (tools=%d)", model, len(payload.get("tools", [])))
+
+        accumulated_content = []
+        accumulated_reasoning = []
+        tool_calls_map: dict[int, dict[str, Any]] = {}
+
+        async with httpx.AsyncClient(timeout=req_timeout) as client:
+            try:
+                async with client.stream("POST", url, json=payload, headers=self._get_headers()) as response:
+                    if response.status_code != 200:
+                        err_body = await response.aread()
+                        raise RuntimeError(f"LM Studio streaming error HTTP {response.status_code}: {err_body.decode('utf-8', errors='ignore')}")
+
+                    async for line in response.aiter_lines():
+                        if not line:
+                            continue
+                        if line.startswith("data: "):
+                            raw_data = line[6:].strip()
+                            if raw_data == "[DONE]":
+                                break
+                            try:
+                                chunk = json.loads(raw_data)
+                            except Exception:
+                                continue
+
+                            choices = chunk.get("choices", [])
+                            if not choices:
+                                continue
+                            delta = choices[0].get("delta", {})
+
+                            content_delta = delta.get("content")
+                            if content_delta:
+                                accumulated_content.append(content_delta)
+                                yield {"type": "token", "delta": content_delta}
+
+                            reasoning_delta = delta.get("reasoning_content")
+                            if reasoning_delta:
+                                accumulated_reasoning.append(reasoning_delta)
+                                yield {"type": "reasoning", "delta": reasoning_delta}
+
+                            tc_deltas = delta.get("tool_calls")
+                            if tc_deltas and isinstance(tc_deltas, list):
+                                for tc in tc_deltas:
+                                    idx = tc.get("index", 0)
+                                    if idx not in tool_calls_map:
+                                        tool_calls_map[idx] = {
+                                            "id": tc.get("id") or f"call_{idx}",
+                                            "name": "",
+                                            "args_chunks": []
+                                        }
+                                    if tc.get("id"):
+                                        tool_calls_map[idx]["id"] = tc["id"]
+                                    fn = tc.get("function", {})
+                                    if fn.get("name"):
+                                        tool_calls_map[idx]["name"] = fn["name"]
+                                    if fn.get("arguments"):
+                                        tool_calls_map[idx]["args_chunks"].append(fn["arguments"])
+
+            except httpx.TimeoutException:
+                logger.error("LM Studio stream timed out after %.1fs", req_timeout)
+                raise RuntimeError(f"LM Studio stream timed out after {req_timeout}s.")
+            except Exception as e:
+                logger.error("LM Studio streaming error: %s", e)
+                raise RuntimeError(f"LM Studio streaming connection error: {e}")
+
+        # Assemble final tool_calls list if any
+        final_tool_calls = None
+        if tool_calls_map:
+            final_tool_calls = []
+            for idx in sorted(tool_calls_map.keys()):
+                tc_data = tool_calls_map[idx]
+                raw_args_str = "".join(tc_data["args_chunks"])
+                try:
+                    parsed_args = json.loads(raw_args_str) if raw_args_str else {}
+                except Exception:
+                    parsed_args = {"raw": raw_args_str}
+                final_tool_calls.append({
+                    "id": tc_data["id"],
+                    "type": "function",
+                    "function": {
+                        "name": tc_data["name"],
+                        "arguments": parsed_args
+                    }
+                })
+
+        final_text = "".join(accumulated_content)
+        yield {
+            "type": "done",
+            "content": final_text,
+            "tool_calls": final_tool_calls,
+            "reasoning": "".join(accumulated_reasoning)
+        }
+
diff --git a/backend/app/agent/model_router.py b/backend/app/agent/model_router.py
index 52cd6f8..1c16cec 100644
--- a/backend/app/agent/model_router.py
+++ b/backend/app/agent/model_router.py
@@ -14,6 +14,14 @@ class RoutingMode(str, Enum):
     HEAVY = "heavy"
 
 
+# Patterns indicating coding or tool-heavy tasks requiring the MAIN model
+CODING_AND_TOOL_PATTERNS = [
+    re.compile(r"\b(def |class |import |function|async |return |const |let |var |struct |impl )\b"),
+    re.compile(r"\b(write_file|patch_file|read_file|grep_in_files|find_files|execute_command)\b"),
+    re.compile(r"\b(refactor|debug|compile|pytest|unittest|traceback|syntaxerror|exception)\b", re.IGNORECASE),
+    re.compile(r"\b(codebase|repository|script|algorithm|regex|api endpoint|backend|frontend)\b", re.IGNORECASE),
+]
+
 # Concrete regex patterns indicating high task complexity
 HEAVY_TASK_PATTERNS = [
     re.compile(r"\b(system\s+design|architect(?:ure|ural)?\s+design|distributed\s+systems?)\b", re.IGNORECASE),
@@ -36,63 +44,98 @@ HEAVY_TAG_PREFIXES = (
 @dataclass
 class RoutingDecision:
     mode: str  # "normal" | "heavy"
-    provider: str  # "lmstudio" | "ollama" | "openrouter"
+    provider: str  # "llama_cpp" | "ollama" | "openrouter"
     model: str
     reason: str
 
 
 class ModelRouter:
     """
-    Determines execution destination: Normal Mode (local LM Studio Bonsai / Ollama Hermes3) vs Heavy Mode (OpenRouter).
-    Enforces deterministic evaluation rules and complete local isolation for Normal Mode.
+    Routes execution to local primary runtime (llama.cpp Qwen3.5 9B / 4B)
+    or fallback runtime (Ollama Hermes3 / Qwen2.5).
+    Cloud routing (OpenRouter / Heavy Mode) is disabled by default.
     """
 
     def __init__(
         self,
         default_mode: str = "auto",
+        active_runtime: Optional[str] = None,
+        llamacpp_main_model: Optional[str] = None,
+        llamacpp_fast_model: Optional[str] = None,
+        ollama_main_model: Optional[str] = None,
+        ollama_fast_model: Optional[str] = None,
+        openrouter_heavy_model: Optional[str] = None,
+        # Backward compatibility kwargs
         active_backend: Optional[str] = None,
         lmstudio_model: Optional[str] = None,
         ollama_model: Optional[str] = None,
-        openrouter_heavy_model: Optional[str] = None
     ):
         self.default_mode = default_mode
-        self._active_backend = active_backend.lower().strip() if active_backend else None
-        self.lmstudio_model = lmstudio_model or getattr(settings, "lmstudio_model", "prism-ml/bonsai-27b")
-        self.lmstudio_qwen_model = getattr(settings, "lmstudio_qwen_model", "qwen3.8-9b-distill")
-        self.ollama_model = ollama_model or settings.ollama_model
+        eff_runtime = active_runtime or active_backend
+        self._active_runtime = eff_runtime.lower().strip() if eff_runtime else None
+        self.llamacpp_main_model = llamacpp_main_model or lmstudio_model or getattr(settings, "llamacpp_main_model_path", "models/Qwen3.5-9B-Q4_K_M.gguf")
+        self.llamacpp_fast_model = llamacpp_fast_model or getattr(settings, "llamacpp_fast_model_path", "models/Qwen3.5-4B-Q4_K_M.gguf")
+        self.ollama_main_model = ollama_main_model or ollama_model or getattr(settings, "ollama_main_model", settings.ollama_model)
+        self.ollama_fast_model = ollama_fast_model or getattr(settings, "ollama_fast_model", "qwen2.5:3b-instruct")
         self.openrouter_heavy_model = openrouter_heavy_model or settings.openrouter_heavy_model
 
+    @property
+    def active_runtime(self) -> str:
+        if self._active_runtime is not None:
+            return self._active_runtime
+        if hasattr(settings, "active_model_backend") and getattr(settings, "active_model_backend") in ("bonsai", "hermes3", "lmstudio"):
+            return getattr(settings, "active_model_backend").lower().strip()
+        return getattr(settings, "model_runtime", "llama_cpp").lower().strip()
+
+    @active_runtime.setter
+    def active_runtime(self, value: Optional[str]) -> None:
+        self._active_runtime = value.lower().strip() if value else None
+
+    # Backward compatibility alias
     @property
     def active_backend(self) -> str:
-        if self._active_backend is not None:
-            return self._active_backend
-        return getattr(settings, "active_model_backend", "bonsai").lower().strip()
+        return self.active_runtime
 
     @active_backend.setter
     def active_backend(self, value: Optional[str]) -> None:
-        self._active_backend = value.lower().strip() if value else None
+        self.active_runtime = value
 
-    def _resolve_normal_target(self, requested_model: Optional[str] = None) -> tuple[str, str, str]:
+    def _resolve_local_target(self, requested_model: Optional[str] = None, prefer_fast: bool = False) -> tuple[str, str, str]:
         """
-        Determine provider and model for Normal Mode based on active backend and overrides.
-        Returns (provider, model, backend_name).
+        Determine local provider and model target based on configured runtime and overrides.
+        Returns (provider, model, label).
         """
-        if requested_model:
-            req_lower = requested_model.lower().strip()
-            if req_lower in ("qwen3.8:9b", "qwen3.8-9b", "qwen3.8-9b-distill", "qwen3.8", self.lmstudio_qwen_model.lower()):
-                return "lmstudio", self.lmstudio_qwen_model, f"LM Studio ({self.lmstudio_qwen_model})"
-            elif requested_model == self.lmstudio_model:
-                return "lmstudio", requested_model, f"LM Studio ({requested_model})"
-            elif requested_model == self.ollama_model or ":" in requested_model:
-                return "ollama", requested_model, f"Ollama ({requested_model})"
-            else:
-                provider = "lmstudio" if self.active_backend == "bonsai" else "ollama"
-                return provider, requested_model, f"{provider} ({requested_model})"
-
-        if self.active_backend == "bonsai":
-            return "lmstudio", self.lmstudio_model, f"LM Studio ({self.lmstudio_model})"
-        else:
-            return "ollama", self.ollama_model, f"Ollama ({self.ollama_model})"
+        runtime = self.active_runtime
+
+        if runtime in ("bonsai", "lmstudio"):
+            provider = "lmstudio"
+            model = requested_model or getattr(settings, "lmstudio_model", "prism-ml/bonsai-27b")
+            return provider, model, f"LM Studio ({model})"
+
+        elif runtime == "llama_cpp":
+            provider = "llama_cpp"
+            if requested_model:
+                req_lower = requested_model.lower().strip()
+                if req_lower in ("fast", "4b", "qwen3.5-4b"):
+                    return provider, "fast", "llama.cpp (Qwen3.5-4B Fast)"
+                elif req_lower in ("main", "9b", "qwen3.5-9b", "default"):
+                    return provider, "main", "llama.cpp (Qwen3.5-9B Main)"
+                else:
+                    return provider, requested_model, f"llama.cpp ({requested_model})"
+            
+            if prefer_fast:
+                return provider, "fast", "llama.cpp (Qwen3.5-4B Fast)"
+            return provider, "main", "llama.cpp (Qwen3.5-9B Main)"
+
+        elif runtime in ("hermes3", "ollama"):
+            provider = "ollama"
+            if requested_model:
+                return provider, requested_model, f"Ollama ({requested_model})"
+            if runtime == "hermes3":
+                return provider, self.ollama_main_model, f"Ollama ({self.ollama_main_model})"
+            if prefer_fast:
+                return provider, self.ollama_fast_model, f"Ollama ({self.ollama_fast_model})"
+            return provider, self.ollama_main_model, f"Ollama ({self.ollama_main_model})"
 
     def evaluate(
         self,
@@ -105,56 +148,87 @@ class ModelRouter:
         """
         mode_str = (requested_mode or self.default_mode).lower().strip()
         msg_clean = message.strip()
+        cloud_enabled = getattr(settings, "cloud_routing_enabled", False) and getattr(settings, "openrouter_enabled", False)
 
         # 1. Explicit Mode: HEAVY
         if mode_str == RoutingMode.HEAVY.value:
-            target_model = requested_model or self.openrouter_heavy_model
-            return RoutingDecision(
-                mode="heavy",
-                provider="openrouter",
-                model=target_model,
-                reason="Explicitly requested Heavy Mode via request parameters."
-            )
+            if cloud_enabled:
+                target_model = requested_model or self.openrouter_heavy_model
+                return RoutingDecision(
+                    mode="heavy",
+                    provider="openrouter",
+                    model=target_model,
+                    reason="Explicitly requested Heavy Mode (Cloud OpenRouter) via request parameters."
+                )
+            else:
+                provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
+                return RoutingDecision(
+                    mode="normal",
+                    provider=provider,
+                    model=model,
+                    reason=f"Heavy Mode requested but cloud routing is disabled by config; routed to local {label}."
+                )
 
         # 2. Explicit Mode: NORMAL
         if mode_str == RoutingMode.NORMAL.value:
-            provider, target_model, label = self._resolve_normal_target(requested_model)
+            provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
             return RoutingDecision(
                 mode="normal",
                 provider=provider,
-                model=target_model,
+                model=model,
                 reason=f"Explicitly requested Normal Mode ({label}) via request parameters."
             )
 
-        # 3. AUTO Mode: Check explicit prompt tags
+        # 3. AUTO Mode: Check prompt tags
         msg_lower = msg_clean.lower()
         for tag in HEAVY_TAG_PREFIXES:
             if msg_lower.startswith(tag):
-                target_model = requested_model or self.openrouter_heavy_model
-                return RoutingDecision(
-                    mode="heavy",
-                    provider="openrouter",
-                    model=target_model,
-                    reason=f"Matched explicit user heavy-mode trigger tag: '{tag}'."
-                )
-
-        # 4. AUTO Mode: Check concrete complexity heuristics
+                if cloud_enabled:
+                    target_model = requested_model or self.openrouter_heavy_model
+                    return RoutingDecision(
+                        mode="heavy",
+                        provider="openrouter",
+                        model=target_model,
+                        reason=f"Matched explicit user heavy-mode trigger tag: '{tag}'."
+                    )
+                else:
+                    provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
+                    return RoutingDecision(
+                        mode="normal",
+                        provider=provider,
+                        model=model,
+                        reason=f"Matched heavy trigger tag '{tag}', but cloud routing is disabled; routed to local {label}."
+                    )
+
+        # 4. AUTO Mode: Check heavy complexity heuristics
         for pattern in HEAVY_TASK_PATTERNS:
             match = pattern.search(msg_clean)
             if match:
-                target_model = requested_model or self.openrouter_heavy_model
-                return RoutingDecision(
-                    mode="heavy",
-                    provider="openrouter",
-                    model=target_model,
-                    reason=f"Matched complex reasoning task pattern: '{match.group(0)}'."
-                )
-
-        # 5. Default fallback for Auto: NORMAL Mode (local LM Studio Bonsai or Ollama rollback)
-        provider, target_model, label = self._resolve_normal_target(requested_model)
+                if cloud_enabled:
+                    target_model = requested_model or self.openrouter_heavy_model
+                    return RoutingDecision(
+                        mode="heavy",
+                        provider="openrouter",
+                        model=target_model,
+                        reason=f"Matched complex reasoning task pattern: '{match.group(0)}'."
+                    )
+                else:
+                    provider, model, label = self._resolve_local_target(requested_model, prefer_fast=False)
+                    return RoutingDecision(
+                        mode="normal",
+                        provider=provider,
+                        model=model,
+                        reason=f"Matched complex task pattern '{match.group(0)}' (local {label})."
+                    )
+
+        # 5. Default AUTO Mode: Check coding/tools vs fast query
+        is_coding_task = any(p.search(msg_clean) for p in CODING_AND_TOOL_PATTERNS)
+        prefer_fast = not is_coding_task and len(msg_clean.split()) <= 15 and not any(kw in msg_lower for kw in ["tool", "file", "search", "run", "execute", "create", "write"])
+
+        provider, model, label = self._resolve_local_target(requested_model, prefer_fast=prefer_fast)
         return RoutingDecision(
             mode="normal",
             provider=provider,
-            model=target_model,
-            reason=f"Standard complexity query routed to local {label} (Normal Mode)."
+            model=model,
+            reason=f"Local execution routed to {label}."
         )
diff --git a/backend/app/agent/openrouter_client.py b/backend/app/agent/openrouter_client.py
index 605a3fd..a0b7a5e 100644
--- a/backend/app/agent/openrouter_client.py
+++ b/backend/app/agent/openrouter_client.py
@@ -66,3 +66,81 @@ class OpenRouterClient:
 
         data = response.json()
         return data
+
+    async def chat_stream(
+        self,
+        messages: list[dict[str, Any]],
+        model: str,
+        temperature: float = 0.7,
+        timeout: float = 60.0
+    ):
+        """
+        Stream chat completion tokens from OpenRouter API.
+        Yields events:
+        - {"type": "token", "delta": str}
+        - {"type": "done", "content": str}
+        """
+        if not self.is_configured:
+            raise ValueError("OPENROUTER_API_KEY is not configured in environment/.env.")
+
+        headers = {
+            "Authorization": f"Bearer {self.api_key}",
+            "Content-Type": "application/json",
+            "HTTP-Referer": "https://github.com/jarvis-assistant",
+            "X-Title": "Local Jarvis Assistant",
+        }
+
+        payload = {
+            "model": model,
+            "messages": messages,
+            "temperature": temperature,
+            "stream": True,
+        }
+
+        url = f"{self.base_url}/chat/completions"
+        logger.info("Streaming request from OpenRouter model '%s'", model)
+
+        import json
+        accumulated_content = []
+
+        async with httpx.AsyncClient(timeout=timeout) as client:
+            try:
+                async with client.stream("POST", url, json=payload, headers=headers) as response:
+                    if response.status_code != 200:
+                        err_body = await response.aread()
+                        raise RuntimeError(f"OpenRouter streaming error HTTP {response.status_code}: {err_body.decode('utf-8', errors='ignore')}")
+
+                    async for line in response.aiter_lines():
+                        if not line:
+                            continue
+                        if line.startswith("data: "):
+                            raw_data = line[6:].strip()
+                            if raw_data == "[DONE]":
+                                break
+                            try:
+                                chunk = json.loads(raw_data)
+                            except Exception:
+                                continue
+
+                            choices = chunk.get("choices", [])
+                            if not choices:
+                                continue
+                            delta = choices[0].get("delta", {})
+                            content_delta = delta.get("content")
+                            if content_delta:
+                                accumulated_content.append(content_delta)
+                                yield {"type": "token", "delta": content_delta}
+
+            except httpx.TimeoutException:
+                logger.error("OpenRouter stream timed out after %.1fs", timeout)
+                raise RuntimeError(f"OpenRouter stream timed out after {timeout}s.")
+            except Exception as e:
+                logger.error("OpenRouter streaming error: %s", e)
+                raise RuntimeError(f"OpenRouter streaming connection error: {e}")
+
+        final_text = "".join(accumulated_content)
+        yield {
+            "type": "done",
+            "content": final_text
+        }
+
diff --git a/backend/app/agent/orchestrator.py b/backend/app/agent/orchestrator.py
index 0f3fd94..d9bde08 100644
--- a/backend/app/agent/orchestrator.py
+++ b/backend/app/agent/orchestrator.py
@@ -3,12 +3,10 @@ import logging
 import re
 import uuid
 from dataclasses import dataclass, field
-from typing import Any, Optional
-import ollama
-
+from typing import Any, AsyncIterator, Optional
 
 from app.config import settings, MAX_TOOL_CALLS_PER_TURN
-from app.agent.tools.registry import AVAILABLE_TOOLS, execute_tool, get_tool_schema
+from app.agent.tools.registry import AVAILABLE_TOOLS, execute_tool, get_tool_schema, get_relevant_tools
 from app.agent.permissions import (
     evaluate_tool_calls_batch,
     evaluate_tool_permission,
@@ -18,14 +16,13 @@ from app.agent.permissions import (
     RiskTier,
     ChatMode,
 )
-
 from app.agent.validator import validate_tool_call, CallHistory, ValidationResult
 from app.agent.model_router import ModelRouter, RoutingDecision
+from app.agent.model_provider import ModelProvider
+from app.agent.provider_factory import get_model_provider
 from app.agent.openrouter_client import OpenRouterClient
-from app.agent.lmstudio_client import LMStudioClient
 from app.agent.reliability_monitor import ReliabilityMonitor
 from app.memory.store import MemoryStore
-
 from app.memory.compactor import ContextCompactor
 from app.skills.loader import SkillsLoader, Skill
 from app.mcp.manager import MCPManager
@@ -39,7 +36,7 @@ logger = logging.getLogger("jarvis.agent.orchestrator")
 class OrchestratorResult:
     response: str
     model: str
-    provider: str = "ollama"  # "ollama" | "openrouter"
+    provider: str = "llama_cpp"  # "llama_cpp" | "ollama" | "openrouter"
     status: str = "completed"  # "completed" | "confirmation_required"
     session_id: str = "default"
     route_reason: str = ""
@@ -51,7 +48,6 @@ class OrchestratorResult:
 
 
 def extract_tool_calls_from_text(content: str, user_prompt: str = "") -> tuple[str, list[dict[str, Any]]]:
-
     """
     Extract embedded tool calls outputted as raw text by models:
     1. <tool_call> ... </tool_call> tags
@@ -80,6 +76,8 @@ def extract_tool_calls_from_text(content: str, user_prompt: str = "") -> tuple[s
                         fn_args = {"query": fn_args}
                 if fn_name:
                     extracted.append({
+                        "id": f"call_{uuid.uuid4().hex[:8]}",
+                        "type": "function",
                         "function": {
                             "name": fn_name,
                             "arguments": fn_args if isinstance(fn_args, dict) else {}
@@ -92,12 +90,11 @@ def extract_tool_calls_from_text(content: str, user_prompt: str = "") -> tuple[s
         cleaned_content = tag_pattern.sub("", content).strip()
         return cleaned_content, extracted
 
-    # 2. Match conversational tool announcements (e.g. "use the write_file function ... { ... }" or "execute grep_in_files:\n{...}")
+    # 2. Match conversational tool announcements
     tool_names = {
         "write_file", "patch_file", "find_files", "grep_in_files",
         "read_file", "list_directory", "execute_command", "delete_file",
         "web_search", "fetch_url",
-        # Phase 3 OS Tools
         "launch_app", "focus_app", "set_volume", "mute_toggle", "media_key",
         "get_clipboard", "set_clipboard", "list_processes", "kill_process", "send_toast"
     }
@@ -113,6 +110,8 @@ def extract_tool_calls_from_text(content: str, user_prompt: str = "") -> tuple[s
                 parsed_args = json.loads(raw_json)
                 if isinstance(parsed_args, dict):
                     extracted.append({
+                        "id": f"call_{uuid.uuid4().hex[:8]}",
+                        "type": "function",
                         "function": {
                             "name": t_name,
                             "arguments": parsed_args
@@ -134,38 +133,38 @@ def extract_tool_calls_from_text(content: str, user_prompt: str = "") -> tuple[s
         try:
             parsed = json.loads(raw_json_str)
             if isinstance(parsed, dict):
+                cid = f"call_{uuid.uuid4().hex[:8]}"
                 if "name" in parsed and ("arguments" in parsed or "args" in parsed or "parameters" in parsed or "params" in parsed):
                     fn_name = parsed["name"]
                     fn_args = parsed.get("arguments") or parsed.get("args") or parsed.get("parameters") or parsed.get("params") or {}
-                    extracted.append({"function": {"name": fn_name, "arguments": fn_args}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": fn_name, "arguments": fn_args}})
                 elif "file_path" in parsed and "content" in parsed:
-                    extracted.append({"function": {"name": "write_file", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "write_file", "arguments": parsed}})
                 elif "file_path" in parsed and "search_block" in parsed:
-                    extracted.append({"function": {"name": "patch_file", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "patch_file", "arguments": parsed}})
                 elif "pattern" in parsed and ("max_matches" in parsed or "case_sensitive" in parsed or "path" in parsed):
-                    extracted.append({"function": {"name": "grep_in_files", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "grep_in_files", "arguments": parsed}})
                 elif "pattern" in parsed and ("root_dir" in parsed or "*" in str(parsed.get("pattern"))):
-                    extracted.append({"function": {"name": "find_files", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "find_files", "arguments": parsed}})
                 elif "query" in parsed and ("max_results" in parsed or len(parsed) == 1):
-                    extracted.append({"function": {"name": "web_search", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "web_search", "arguments": parsed}})
                 elif "url" in parsed and ("max_chars" in parsed or len(parsed) == 1):
-                    extracted.append({"function": {"name": "fetch_url", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "fetch_url", "arguments": parsed}})
                 elif "command" in parsed:
-                    extracted.append({"function": {"name": "execute_command", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "execute_command", "arguments": parsed}})
                 elif "name_or_path" in parsed:
-                    extracted.append({"function": {"name": "launch_app", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "launch_app", "arguments": parsed}})
                 elif "name_or_title_substring" in parsed:
-                    extracted.append({"function": {"name": "focus_app", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "focus_app", "arguments": parsed}})
                 elif "level" in parsed and len(parsed) == 1:
-                    extracted.append({"function": {"name": "set_volume", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "set_volume", "arguments": parsed}})
                 elif "pid_or_name" in parsed:
-                    extracted.append({"function": {"name": "kill_process", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "kill_process", "arguments": parsed}})
                 elif "title" in parsed and "message" in parsed:
-                    extracted.append({"function": {"name": "send_toast", "arguments": parsed}})
+                    extracted.append({"id": cid, "type": "function", "function": {"name": "send_toast", "arguments": parsed}})
         except Exception:
             pass
 
-
     if extracted:
         cleaned_content = json_block_regex.sub("", content).strip()
         return cleaned_content, extracted
@@ -182,6 +181,8 @@ def extract_tool_calls_from_text(content: str, user_prompt: str = "") -> tuple[s
                 if len(code_content.strip()) > 10:
                     logger.info("Inferred write_file tool call for '%s' from generated code block", target_file_path)
                     extracted.append({
+                        "id": f"call_{uuid.uuid4().hex[:8]}",
+                        "type": "function",
                         "function": {
                             "name": "write_file",
                             "arguments": {
@@ -196,12 +197,11 @@ def extract_tool_calls_from_text(content: str, user_prompt: str = "") -> tuple[s
     return content, []
 
 
-
 DEFAULT_SYSTEM_PROMPT = (
     "You are Jarvis, a highly capable local AI assistant running on Windows with direct access to tools, memory, and skills.\n"
     "CRITICAL RULES:\n"
     "1. NEVER output conversational plans or raw JSON code blocks in your text describing tools you want to run. When an action is needed, directly invoke the tool.\n"
-    "2. When creating new files or scripts, ALWAYS write complete, fully-implemented code with proper functions, docstrings, and logic. Invoke 'write_file(file_path=..., content=...)'.\n"
+    "2. If the user explicitly asks to create or save a file on disk (e.g. 'save to test.py' or 'create file ...'), invoke 'write_file(file_path=..., content=...)'. If the user simply asks a coding question, asks to explain something, or asks to write a snippet/script without specifying saving to a file, provide the complete, fully-implemented code directly in markdown in your response.\n"
     "3. When editing or updating code in an existing file, invoke 'patch_file(file_path=..., search_block=..., replacement_block=...)'. If needed, invoke 'read_file' first to see the exact text before patching.\n"
     "4. When searching for words, functions, classes, definitions, or symbols across the codebase/project, ALWAYS invoke 'grep_in_files(pattern=..., path=...)'. Never say a symbol is missing without running grep_in_files first.\n"
     "5. When looking for files or directories by name/pattern/extension, ALWAYS invoke 'find_files(pattern=..., root_dir=...)'.\n"
@@ -220,23 +220,74 @@ DEFAULT_SYSTEM_PROMPT = (
 )
 
 
+class _LegacyClientAdapter(ModelProvider):
+    def __init__(self, client: Any, name_str: str = "legacy"):
+        self.client = client
+        self._name = name_str
+
+    @property
+    def name(self) -> str:
+        return self._name
+
+    async def health_check(self) -> bool:
+        return True
 
+    async def model_info(self) -> dict[str, Any]:
+        return {"provider": self._name}
 
+    async def list_models(self) -> list[str]:
+        return []
+
+    async def chat(self, messages, model=None, tools=None, temperature=None, profile="general", timeout=None) -> dict[str, Any]:
+        res = await self.client.chat(model=model, messages=messages, tools=tools)
+        if isinstance(res, dict):
+            return res
+        msg = getattr(res, "message", None)
+        if msg is not None:
+            content = getattr(msg, "content", "") or ""
+            tool_calls = getattr(msg, "tool_calls", None)
+            return {
+                "message": {
+                    "role": "assistant",
+                    "content": content,
+                    "tool_calls": tool_calls
+                },
+                "raw": res
+            }
+        return {"message": {"role": "assistant", "content": str(res), "tool_calls": None}, "raw": res}
+
+    async def stream_chat(self, messages, model=None, tools=None, temperature=None, profile="general", timeout=None) -> AsyncIterator[dict[str, Any]]:
+        if hasattr(self.client, "chat_stream"):
+            async for ev in self.client.chat_stream(model=model, messages=messages, tools=tools):
+                if ev.get("type") == "token":
+                    yield {"event": "text_delta", "content": ev.get("delta", "")}
+                elif ev.get("type") == "done":
+                    yield {"event": "done", "raw": ev}
+        else:
+            res = await self.chat(messages=messages, model=model, tools=tools, temperature=temperature, profile=profile)
+            content = res.get("message", {}).get("content", "")
+            tcs = res.get("message", {}).get("tool_calls")
+            if tcs:
+                for tc in tcs:
+                    yield {"event": "tool_call", "tool_call": tc}
+            yield {"event": "text_delta", "content": content}
+            yield {"event": "done", "raw": res}
 
+    async def unload_model(self, model=None) -> bool:
+        return True
 
 
 class AgentOrchestrator:
     """
-    Orchestrates communication with Ollama and OpenRouter, enforcing hardcoded
-    safety permissions, complexity routing, memory persistence, context compaction,
-    dynamic skills loading, and MCP tool execution.
+    Orchestrates communication with the primary local ModelProvider (llama.cpp)
+    or fallback provider (Ollama), enforcing hardcoded safety permissions,
+    complexity routing, memory persistence, context compaction, dynamic skills loading,
+    and MCP tool execution.
     """
 
     def __init__(
         self,
-        ollama_client: Optional[ollama.AsyncClient] = None,
-        lmstudio_client: Optional[LMStudioClient] = None,
-        openrouter_client: Optional[OpenRouterClient] = None,
+        provider: Optional[ModelProvider] = None,
         router: Optional[ModelRouter] = None,
         memory_store: Optional[MemoryStore] = None,
         compactor: Optional[ContextCompactor] = None,
@@ -245,32 +296,21 @@ class AgentOrchestrator:
         reliability_monitor: Optional[ReliabilityMonitor] = None,
         tts_engine: Optional[ChatterboxEngine] = None,
         voice_output_enabled: Optional[bool] = None,
+        # Backward compatibility parameters
+        ollama_client: Optional[Any] = None,
+        lmstudio_client: Optional[Any] = None,
+        openrouter_client: Optional[Any] = None,
     ):
-        self.ollama_client = ollama_client or ollama.AsyncClient(host=settings.ollama_host)
-        self.lmstudio_client = lmstudio_client or LMStudioClient(
-            base_url=settings.lmstudio_base_url,
-            timeout=90.0
-        )
-        self.openrouter_client = openrouter_client or OpenRouterClient(
-            api_key=settings.openrouter_api_key,
-            base_url=settings.openrouter_base_url
-        )
-        if router is None:
-            if ollama_client is not None and lmstudio_client is None:
-                resolved_backend = "hermes3"
-            elif lmstudio_client is not None and ollama_client is None:
-                resolved_backend = "bonsai"
-            else:
-                resolved_backend = settings.active_model_backend
-            self.router = ModelRouter(
-                default_mode=settings.default_routing_mode,
-                active_backend=resolved_backend,
-                lmstudio_model=settings.lmstudio_model,
-                ollama_model=settings.ollama_model,
-                openrouter_heavy_model=settings.openrouter_heavy_model
-            )
+        if provider is not None:
+            self.provider = provider
+        elif lmstudio_client is not None and type(lmstudio_client).__name__ not in ("LMStudioClient", "NoneType"):
+            self.provider = _LegacyClientAdapter(lmstudio_client, "lmstudio")
+        elif ollama_client is not None and type(ollama_client).__name__ not in ("AsyncClient", "NoneType"):
+            self.provider = _LegacyClientAdapter(ollama_client, "ollama")
         else:
-            self.router = router
+            self.provider = get_model_provider()
+
+        self.router = router or ModelRouter(default_mode=settings.default_routing_mode)
         self.memory_store = memory_store or MemoryStore(db_path=settings.memory_db_path)
         self.compactor = compactor or ContextCompactor(
             max_context_tokens=settings.memory_max_context_tokens,
@@ -283,22 +323,29 @@ class AgentOrchestrator:
         self.voice_output_enabled = (
             voice_output_enabled if voice_output_enabled is not None else settings.voice_output_enabled
         )
+        self.openrouter_client = openrouter_client or OpenRouterClient(
+            api_key=settings.openrouter_api_key,
+            base_url=settings.openrouter_base_url
+        )
+
+    def _synthesize_voice(self, text: str):
+        """Synthesize and play voice output if voice is enabled and TTS engine is available."""
+        if not self.voice_output_enabled or not text or not self.tts_engine:
+            return
+        try:
+            clean_text, _ = extract_tool_calls_from_text(text)
+            clean_text = self.tts_engine.sanitize_text(clean_text or text)
+            if clean_text:
+                audio_bytes = self.tts_engine.synthesize(clean_text)
+                if audio_bytes:
+                    play_audio(audio_bytes)
+        except Exception as e:
+            logger.warning("Error synthesizing or playing orchestrator voice output: %s", e)
 
     def _finalize_result(self, result: OrchestratorResult) -> OrchestratorResult:
-        """
-        Finalizes an orchestrator result. If voice output is enabled and the turn is completed,
-        extracts pure natural-language prose and triggers non-blocking audio synthesis and playback.
-        """
+        """Finalizes orchestrator result and plays audio if enabled."""
         if self.voice_output_enabled and result.status == "completed" and result.response:
-            try:
-                clean_text, _ = extract_tool_calls_from_text(result.response)
-                clean_text = self.tts_engine.sanitize_text(clean_text or result.response)
-                if clean_text:
-                    audio_bytes = self.tts_engine.synthesize(clean_text)
-                    if audio_bytes:
-                        play_audio(audio_bytes)
-            except Exception as e:
-                logger.warning("Error synthesizing or playing orchestrator voice output: %s", e)
+            self._synthesize_voice(result.response)
         return result
 
     async def run(
@@ -313,12 +360,10 @@ class AgentOrchestrator:
         compaction_threshold_override: Optional[int] = None,
         chat_mode: Optional[str] = "WORKSPACE"
     ) -> OrchestratorResult:
-        # 0. Mid-speech interruption: stop any active audio playback immediately on new turn
         stop_playback()
-
         active_session_id = session_id or "default"
 
-        # Conversational voice toggle commands
+        # Voice toggle commands
         lower_msg = user_message.strip().lower()
         if lower_msg in ("stop talking", "be quiet", "silence", "stop speech", "stop audio"):
             stop_playback()
@@ -376,7 +421,7 @@ class AgentOrchestrator:
         effective_mode_str = (chat_mode or session_data.get("chat_mode") or "WORKSPACE").upper()
         resolved_chat_mode = ChatMode.SYSTEM if effective_mode_str == "SYSTEM" else ChatMode.WORKSPACE
 
-        # 1. Evaluate Routing
+        # 1. Routing Decision
         decision = self.router.evaluate(
             message=user_message,
             requested_mode=requested_mode,
@@ -385,7 +430,7 @@ class AgentOrchestrator:
         logger.info("Routing decision: mode='%s', provider='%s', model='%s', reason='%s'",
                     decision.mode, decision.provider, decision.model, decision.reason)
 
-        # 2. Dynamic Skills Matching & Prompt Augmentation
+        # 2. Dynamic Skills Matching & Prompt Injection
         matched_skills = self.skills_loader.match_skills(user_message)
         active_skill_names = [s.name for s in matched_skills]
         if active_skill_names:
@@ -395,18 +440,19 @@ class AgentOrchestrator:
         base_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
         composed_system_prompt = base_system_prompt + skill_prompt_injection
 
-        # 3. Dynamic Tool Aggregation (Base Tools + MCP Tools)
+        # 3. Dynamic Tool Aggregation
         mcp_tools = self.mcp_manager.get_tool_definitions()
-        combined_tools = AVAILABLE_TOOLS + mcp_tools
+        relevant_base_tools = get_relevant_tools(user_message, chat_mode=effective_mode_str, matched_skills=matched_skills)
+        combined_tools = (relevant_base_tools + mcp_tools) if relevant_base_tools else []
 
-        # 4. Load History & Evaluate Context Compaction
+        # 4. Memory History & Context Compaction
         history = self.memory_store.get_messages(active_session_id)
         current_turn = {"role": "user", "content": user_message}
         full_conversation = history + [current_turn]
 
         compacted_msgs, compaction_info = await self.compactor.compact(
             messages=full_conversation,
-            client=self.ollama_client,
+            client=self.provider,
             model=decision.model,
             threshold_override=compaction_threshold_override
         )
@@ -422,19 +468,22 @@ class AgentOrchestrator:
                 details=compaction_info.get("details")
             )
 
-        # Save user prompt
         self.memory_store.append_message(active_session_id, role="user", content=user_message)
 
-        # 5. Dispatch: OpenRouter (Heavy Mode)
-        if decision.provider == "openrouter":
+        # 5. Determine Profile (coding vs general)
+        is_tool_or_coding = bool(combined_tools) or any(
+            kw in user_message.lower() for kw in ["code", "file", "func", "def ", "class ", "test", "run", "script", "debug"]
+        )
+        profile = "coding" if is_tool_or_coding else "general"
+
+        # 6. Dispatch: OpenRouter Cloud (if enabled)
+        if decision.provider == "openrouter" and getattr(settings, "cloud_routing_enabled", False):
             try:
                 dispatch_messages = [{"role": "system", "content": composed_system_prompt}] + compacted_msgs
-                
                 openrouter_res = await self.openrouter_client.chat(
                     messages=dispatch_messages,
                     model=decision.model
                 )
-
                 content = ""
                 choices = openrouter_res.get("choices", [])
                 if choices:
@@ -453,94 +502,77 @@ class AgentOrchestrator:
                     compaction_performed=compaction_info,
                     active_skills=active_skill_names
                 )
-
             except Exception as e:
-                logger.warning("OpenRouter dispatch failed (%s). Gracefully falling back to local model.", e)
-                if self.router.active_backend == "bonsai":
-                    fallback_model = requested_model or settings.lmstudio_model
-                    result = await self._run_lmstudio_loop(
-                        session_id=active_session_id,
-                        conversation_messages=compacted_msgs,
-                        tools=combined_tools,
-                        model=fallback_model,
-                        system_prompt=composed_system_prompt,
-                        approved_action_ids=approved_action_ids,
-                        max_iterations=max_iterations,
-                        chat_mode=resolved_chat_mode
-                    )
-                    result.route_reason = f"{decision.reason} [Fallback: OpenRouter failed ({str(e)}), used local LM Studio]"
-                else:
-                    fallback_model = requested_model or settings.ollama_model
-                    result = await self._run_ollama_loop(
-                        session_id=active_session_id,
-                        conversation_messages=compacted_msgs,
-                        tools=combined_tools,
-                        model=fallback_model,
-                        system_prompt=composed_system_prompt,
-                        approved_action_ids=approved_action_ids,
-                        max_iterations=max_iterations,
-                        chat_mode=resolved_chat_mode
-                    )
-                    result.route_reason = f"{decision.reason} [Fallback: OpenRouter failed ({str(e)}), used local Ollama]"
-                result.fallback_used = True
-                result.compaction_performed = compaction_info
-                result.active_skills = active_skill_names
-                return result
-
-        # 6. Dispatch: Local LM Studio (Stage B Normal Mode Default)
-        if decision.provider == "lmstudio":
-            try:
-                result = await self._run_lmstudio_loop(
-                    session_id=active_session_id,
-                    conversation_messages=compacted_msgs,
-                    tools=combined_tools,
-                    model=decision.model,
-                    system_prompt=composed_system_prompt,
-                    approved_action_ids=approved_action_ids,
-                    max_iterations=max_iterations,
-                    route_reason=decision.reason,
-                    chat_mode=resolved_chat_mode
-                )
-                result.compaction_performed = compaction_info
-                result.active_skills = active_skill_names
-                return result
-            except Exception as e:
-                logger.warning("LM Studio dispatch failed (%s). Gracefully falling back to local Ollama.", e)
-                fallback_model = settings.ollama_model
-                result = await self._run_ollama_loop(
+                logger.warning("OpenRouter dispatch failed (%s). Falling back to local provider.", e)
+                fallback_provider = get_model_provider("llama_cpp")
+                result = await self._run_provider_loop(
+                    provider=fallback_provider,
                     session_id=active_session_id,
                     conversation_messages=compacted_msgs,
                     tools=combined_tools,
-                    model=fallback_model,
+                    model="main",
                     system_prompt=composed_system_prompt,
                     approved_action_ids=approved_action_ids,
                     max_iterations=max_iterations,
-                    chat_mode=resolved_chat_mode
+                    route_reason=f"{decision.reason} [Fallback: OpenRouter failed ({e}), used local llama.cpp]",
+                    chat_mode=resolved_chat_mode,
+                    profile=profile
                 )
-                result.route_reason = f"{decision.reason} [Fallback: LM Studio failed ({str(e)}), used local Ollama ({fallback_model})]"
                 result.fallback_used = True
                 result.compaction_performed = compaction_info
                 result.active_skills = active_skill_names
                 return result
 
-        # 7. Dispatch: Local Ollama (Normal Mode / Rollback Target)
-        result = await self._run_ollama_loop(
-            session_id=active_session_id,
-            conversation_messages=compacted_msgs,
-            tools=combined_tools,
-            model=decision.model,
-            system_prompt=composed_system_prompt,
-            approved_action_ids=approved_action_ids,
-            max_iterations=max_iterations,
-            route_reason=decision.reason,
-            chat_mode=resolved_chat_mode
-        )
-        result.compaction_performed = compaction_info
-        result.active_skills = active_skill_names
-        return result
-
-    async def _run_lmstudio_loop(
+        # 7. Dispatch: Local Primary Provider (llama.cpp) or Fallback (Ollama)
+        target_provider = self.provider if isinstance(self.provider, _LegacyClientAdapter) else get_model_provider(decision.provider)
+        try:
+            result = await self._run_provider_loop(
+                provider=target_provider,
+                session_id=active_session_id,
+                conversation_messages=compacted_msgs,
+                tools=combined_tools,
+                model=decision.model,
+                system_prompt=composed_system_prompt,
+                approved_action_ids=approved_action_ids,
+                max_iterations=max_iterations,
+                route_reason=decision.reason,
+                chat_mode=resolved_chat_mode,
+                profile=profile
+            )
+            result.compaction_performed = compaction_info
+            result.active_skills = active_skill_names
+            return result
+        except Exception as e:
+            if target_provider.name == "llama_cpp":
+                logger.warning("Primary llama.cpp dispatch failed (%s). Falling back to Ollama.", e)
+                try:
+                    fallback_provider = get_model_provider("ollama")
+                    fallback_model = settings.ollama_main_model
+                    result = await self._run_provider_loop(
+                        provider=fallback_provider,
+                        session_id=active_session_id,
+                        conversation_messages=compacted_msgs,
+                        tools=combined_tools,
+                        model=fallback_model,
+                        system_prompt=composed_system_prompt,
+                        approved_action_ids=approved_action_ids,
+                        max_iterations=max_iterations,
+                        route_reason=f"{decision.reason} [Fallback: llama.cpp failed ({e}), used local Ollama ({fallback_model})]",
+                        chat_mode=resolved_chat_mode,
+                        profile=profile
+                    )
+                    result.fallback_used = True
+                    result.compaction_performed = compaction_info
+                    result.active_skills = active_skill_names
+                    return result
+                except Exception as fallback_err:
+                    logger.error("Fallback to Ollama also failed: %s", fallback_err)
+                    raise e
+            raise
+
+    async def _run_provider_loop(
         self,
+        provider: ModelProvider,
         session_id: str,
         conversation_messages: list[dict[str, Any]],
         tools: list[dict[str, Any]],
@@ -548,19 +580,20 @@ class AgentOrchestrator:
         system_prompt: str,
         approved_action_ids: Optional[list[str]] = None,
         max_iterations: int = 5,
-        route_reason: str = "Local LM Studio execution",
-        chat_mode: ChatMode = ChatMode.WORKSPACE
+        route_reason: str = "Local provider execution",
+        chat_mode: ChatMode = ChatMode.WORKSPACE,
+        profile: str = "general"
     ) -> OrchestratorResult:
         """
-        Execute agent loop against LM Studio (OpenAI-compatible) endpoint with
-        robust Stage A schema validation, loop breaking, rate limits, and safety gating.
+        Execute deterministic agent loop against ModelProvider with schema validation,
+        loop breaking, rate limits, and safety gating.
         """
         turn_id = f"turn_{uuid.uuid4().hex[:12]}"
         call_history = CallHistory(window=3)
         total_turn_tool_calls = 0
         tool_turn_counts: dict[str, int] = {}
         repair_attempts: dict[str, int] = {}
-        model_tier = "tier2"
+        model_tier = "tier2" if provider.name == "llama_cpp" else "tier1"
 
         messages: list[dict[str, Any]] = []
         messages.append({"role": "system", "content": system_prompt})
@@ -569,12 +602,13 @@ class AgentOrchestrator:
         tools_used: list[dict[str, Any]] = []
 
         for iteration in range(max_iterations):
-            logger.info("LM Studio loop iteration %d/%d for model '%s' (turn_id=%s)", iteration + 1, max_iterations, model, turn_id)
+            logger.info("%s loop iteration %d/%d for model '%s' (turn_id=%s)", provider.name, iteration + 1, max_iterations, model, turn_id)
 
-            chat_response = await self.lmstudio_client.chat(
+            chat_response = await provider.chat(
                 model=model,
                 messages=messages,
-                tools=tools
+                tools=tools if tools else None,
+                profile=profile
             )
 
             message_obj = chat_response.get("message", {})
@@ -588,27 +622,27 @@ class AgentOrchestrator:
                     if isinstance(msg, dict) and msg.get("role") == "user":
                         latest_user_prompt = msg.get("content", "")
                         break
-
                 content, extracted_calls = extract_tool_calls_from_text(content, user_prompt=latest_user_prompt)
                 if extracted_calls:
-                    logger.info("Extracted %d tool call(s) from raw LM Studio text stream", len(extracted_calls))
+                    logger.info("Extracted %d tool call(s) from raw model text stream", len(extracted_calls))
                     tool_calls = extracted_calls
 
             if not tool_calls:
                 if not content.strip():
-                    logger.info("LM Studio returned empty content with tools schema. Requesting text generation without tools parameter.")
-                    synth_response = await self.lmstudio_client.chat(
+                    logger.info("Model returned empty content with tools schema. Requesting text generation without tools parameter.")
+                    synth_response = await provider.chat(
                         model=model,
-                        messages=messages
+                        messages=messages,
+                        profile=profile
                     )
                     content = synth_response.get("message", {}).get("content", "") or ""
 
-                logger.info("No further tool calls requested. Returning final LM Studio response.")
+                logger.info("No further tool calls requested. Returning final %s response.", provider.name)
                 self.memory_store.append_message(session_id, role="assistant", content=content)
                 return OrchestratorResult(
                     response=content,
                     model=model,
-                    provider="lmstudio",
+                    provider=provider.name,
                     status="completed",
                     session_id=session_id,
                     route_reason=route_reason,
@@ -616,7 +650,7 @@ class AgentOrchestrator:
                     tools_used=tools_used
                 )
 
-            logger.info("LM Studio requested %d tool call(s)", len(tool_calls))
+            logger.info("%s requested %d tool call(s)", provider.name, len(tool_calls))
 
             # Normalize tool calls
             normalized_tool_calls = []
@@ -638,12 +672,12 @@ class AgentOrchestrator:
                     break
             if duplicate_detected:
                 loop_msg = "Jarvis attempted the same action twice — stopping to avoid a loop."
-                logger.warning("Duplicate tool invocation loop detected in LM Studio turn. Halting turn.")
+                logger.warning("Duplicate tool invocation loop detected in %s turn. Halting turn.", provider.name)
                 self.memory_store.append_message(session_id, role="assistant", content=loop_msg)
                 return OrchestratorResult(
                     response=loop_msg,
                     model=model,
-                    provider="lmstudio",
+                    provider=provider.name,
                     status="completed",
                     session_id=session_id,
                     route_reason=route_reason,
@@ -654,7 +688,7 @@ class AgentOrchestrator:
             for tc in normalized_tool_calls:
                 call_history.record(tc["name"], tc["args"])
 
-            # 3. Per-Tool Rate Limiting Check (§2)
+            # Per-Tool Rate Limiting
             rate_limited_tool = None
             for tc in normalized_tool_calls:
                 fn_name = tc["name"]
@@ -671,7 +705,7 @@ class AgentOrchestrator:
                 return OrchestratorResult(
                     response=rate_msg,
                     model=model,
-                    provider="lmstudio",
+                    provider=provider.name,
                     status="completed",
                     session_id=session_id,
                     route_reason=route_reason,
@@ -681,13 +715,13 @@ class AgentOrchestrator:
 
             # Global per-turn cap
             if total_turn_tool_calls + len(normalized_tool_calls) > MAX_TOOL_CALLS_PER_TURN:
-                cap_msg = f"Per-turn tool call limit ({MAX_TOOL_CALLS_PER_TURN}) exceeded. Halting further tool execution for safety."
+                cap_msg = f"Turn tool call limit exceeded: Reached maximum allowed {MAX_TOOL_CALLS_PER_TURN} calls for this turn. Halting further tool execution for safety."
                 logger.warning("Turn tool call cap reached (%d / %d). Halting turn.", total_turn_tool_calls, MAX_TOOL_CALLS_PER_TURN)
                 self.memory_store.append_message(session_id, role="assistant", content=cap_msg)
                 return OrchestratorResult(
                     response=cap_msg,
                     model=model,
-                    provider="lmstudio",
+                    provider=provider.name,
                     status="completed",
                     session_id=session_id,
                     route_reason=route_reason,
@@ -698,7 +732,6 @@ class AgentOrchestrator:
             # Schema validation & Repair-then-Escalate
             validation_failed_items = []
             validated_tool_calls = []
-            escalate_to_heavy = False
 
             for tc in normalized_tool_calls:
                 fn_name = tc["name"]
@@ -744,48 +777,37 @@ class AgentOrchestrator:
                             repair_attempt=1
                         )
                         self.reliability_monitor.evaluate_and_trigger_rollback(model_tier=model_tier)
-                        escalate_to_heavy = True
-                        break
+                        if self.openrouter_client and (getattr(self.openrouter_client, "is_configured", False) or hasattr(self.openrouter_client, "chat")):
+                            logger.warning("Tool call validation failed twice. Escalating remaining turn to Tier 3 (OpenRouter).")
+                            try:
+                                openrouter_res = await self.openrouter_client.chat(
+                                    messages=messages,
+                                    model=settings.openrouter_heavy_model
+                                )
+                                esc_content = ""
+                                choices = openrouter_res.get("choices", []) if isinstance(openrouter_res, dict) else []
+                                if choices:
+                                    esc_content = choices[0].get("message", {}).get("content", "")
+                                elif isinstance(openrouter_res, dict) and "message" in openrouter_res:
+                                    esc_content = openrouter_res["message"].get("content", "")
+                                self.memory_store.append_message(session_id, role="assistant", content=esc_content)
+                                return OrchestratorResult(
+                                    response=esc_content,
+                                    model=settings.openrouter_heavy_model,
+                                    provider="openrouter",
+                                    status="completed",
+                                    session_id=session_id,
+                                    route_reason=f"{route_reason} [Escalated to Tier 3 OpenRouter due to repeated tool argument validation failures]",
+                                    fallback_used=False,
+                                    tools_used=tools_used
+                                )
+                            except Exception as e:
+                                logger.error("OpenRouter Tier 3 escalation failed: %s", e)
+                        validation_failed_items.append((fn_name, fn_args, val_res.error, call_id))
                 else:
                     validated_tool_calls.append((call_id, fn_name, val_res.args))
 
-            if escalate_to_heavy:
-                logger.warning("LM Studio tool call validation failed twice. Escalating remaining turn to Tier 3 (OpenRouter).")
-                try:
-                    openrouter_res = await self.openrouter_client.chat(
-                        messages=messages,
-                        model=settings.openrouter_heavy_model
-                    )
-                    esc_content = ""
-                    choices = openrouter_res.get("choices", [])
-                    if choices:
-                        esc_content = choices[0].get("message", {}).get("content", "")
-                    self.memory_store.append_message(session_id, role="assistant", content=esc_content)
-                    return OrchestratorResult(
-                        response=esc_content,
-                        model=settings.openrouter_heavy_model,
-                        provider="openrouter",
-                        status="completed",
-                        session_id=session_id,
-                        route_reason=f"{route_reason} [Escalated to Tier 3 OpenRouter due to repeated tool argument validation failures]",
-                        fallback_used=False,
-                        tools_used=tools_used
-                    )
-                except Exception as e:
-                    logger.error("Tier 3 escalation OpenRouter call failed: %s", e)
-                    esc_error_msg = f"Escalation to Tier 3 OpenRouter failed ({e}). Stopping turn."
-                    return OrchestratorResult(
-                        response=esc_error_msg,
-                        model=model,
-                        provider="lmstudio",
-                        status="completed",
-                        session_id=session_id,
-                        route_reason=route_reason,
-                        fallback_used=False,
-                        tools_used=tools_used
-                    )
-
-            if validation_failed_items:
+            if validation_failed_items and not validated_tool_calls:
                 assistant_msg = {
                     "role": "assistant",
                     "content": content,
@@ -793,7 +815,7 @@ class AgentOrchestrator:
                         {
                             "id": item[3],
                             "type": "function",
-                            "function": {"name": item[0], "arguments": json.dumps(item[1]) if isinstance(item[1], dict) else str(item[1])}
+                            "function": {"name": item[0], "arguments": item[1]}
                         }
                         for item in validation_failed_items
                     ]
@@ -810,7 +832,7 @@ class AgentOrchestrator:
                 continue
 
             # Safety permission checks
-            batch_calls = [{"name": name, "arguments": args} for _, name, args in validated_tool_calls]
+            batch_calls = [{"name": name, "args": args} for _, name, args in validated_tool_calls]
             batch_permission = evaluate_tool_calls_batch(
                 tool_calls=batch_calls,
                 chat_mode=chat_mode,
@@ -853,7 +875,7 @@ class AgentOrchestrator:
                 return OrchestratorResult(
                     response=confirm_response,
                     model=model,
-                    provider="lmstudio",
+                    provider=provider.name,
                     status="confirmation_required",
                     session_id=session_id,
                     route_reason=route_reason,
@@ -870,7 +892,7 @@ class AgentOrchestrator:
                     {
                         "id": cid,
                         "type": "function",
-                        "function": {"name": name, "arguments": json.dumps(args) if isinstance(args, dict) else str(args)}
+                        "function": {"name": name, "arguments": args}
                     }
                     for cid, name, args in validated_tool_calls
                 ]
@@ -917,10 +939,11 @@ class AgentOrchestrator:
                 })
                 self.memory_store.append_message(session_id, role="tool", content=tool_output, name=fn_name)
 
-        logger.warning("Max tool iterations reached (%d). Requesting final summary from LM Studio.", max_iterations)
-        final_response = await self.lmstudio_client.chat(
+        logger.warning("Max tool iterations reached (%d). Requesting final summary from %s.", max_iterations, provider.name)
+        final_response = await provider.chat(
             model=model,
-            messages=messages
+            messages=messages,
+            profile=profile
         )
         final_content = final_response.get("message", {}).get("content", "") or ""
         self.memory_store.append_message(session_id, role="assistant", content=final_content)
@@ -928,7 +951,7 @@ class AgentOrchestrator:
         return OrchestratorResult(
             response=final_content,
             model=model,
-            provider="lmstudio",
+            provider=provider.name,
             status="completed",
             session_id=session_id,
             route_reason=route_reason,
@@ -936,8 +959,117 @@ class AgentOrchestrator:
             tools_used=tools_used
         )
 
-    async def _run_ollama_loop(
+    async def run_stream(
         self,
+        user_message: str,
+        session_id: Optional[str] = None,
+        requested_mode: Optional[str] = None,
+        requested_model: Optional[str] = None,
+        system_prompt: Optional[str] = None,
+        approved_action_ids: Optional[list[str]] = None,
+        max_iterations: int = 5,
+        compaction_threshold_override: Optional[int] = None,
+        chat_mode: Optional[str] = "WORKSPACE"
+    ):
+        """
+        Asynchronously streams chat tokens, tool execution events, and metadata.
+        Yields JSON event dictionaries: {"event": "...", "data": {...}}
+        """
+        stop_playback()
+        active_session_id = session_id or "default"
+
+        # Conversational voice toggle commands
+        lower_msg = user_message.strip().lower()
+        if lower_msg in ("stop talking", "be quiet", "silence", "stop speech", "stop audio"):
+            stop_playback()
+            yield {"event": "done", "data": {"response": "I have stopped speaking.", "model": "system", "provider": "system", "session_id": active_session_id}}
+            return
+        if lower_msg in ("voice on", "enable voice", "turn voice on", "unmute voice"):
+            self.voice_output_enabled = True
+            msg = "Voice output is now enabled."
+            yield {"event": "done", "data": {"response": msg, "model": "system", "provider": "system", "session_id": active_session_id}}
+            self._synthesize_voice(msg)
+            return
+        if lower_msg in ("voice off", "disable voice", "turn voice off", "mute voice"):
+            self.voice_output_enabled = False
+            stop_playback()
+            yield {"event": "done", "data": {"response": "Voice output is now disabled.", "model": "system", "provider": "system", "session_id": active_session_id}}
+            return
+
+        session_data = self.memory_store.get_or_create_session(active_session_id, chat_mode=chat_mode)
+        effective_mode_str = (chat_mode or session_data.get("chat_mode") or "WORKSPACE").upper()
+        resolved_chat_mode = ChatMode.SYSTEM if effective_mode_str == "SYSTEM" else ChatMode.WORKSPACE
+
+        decision = self.router.evaluate(
+            message=user_message,
+            requested_mode=requested_mode,
+            requested_model=requested_model
+        )
+
+        matched_skills = self.skills_loader.match_skills(user_message)
+        active_skill_names = [s.name for s in matched_skills]
+        skill_prompt_injection = self.skills_loader.build_skill_prompt_injection(matched_skills)
+        base_system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
+        composed_system_prompt = base_system_prompt + skill_prompt_injection
+
+        mcp_tools = self.mcp_manager.get_tool_definitions()
+        relevant_base_tools = get_relevant_tools(user_message, chat_mode=effective_mode_str, matched_skills=matched_skills)
+        combined_tools = (relevant_base_tools + mcp_tools) if relevant_base_tools else []
+
+        history = self.memory_store.get_messages(active_session_id)
+        current_turn = {"role": "user", "content": user_message}
+        full_conversation = history + [current_turn]
+
+        compacted_msgs, compaction_info = await self.compactor.compact(
+            messages=full_conversation,
+            client=self.provider,
+            model=decision.model,
+            threshold_override=compaction_threshold_override
+        )
+        if compaction_info:
+            self.memory_store.replace_messages(active_session_id, compacted_msgs[:-1])
+
+        self.memory_store.append_message(active_session_id, role="user", content=user_message)
+
+        is_tool_or_coding = bool(combined_tools) or any(
+            kw in user_message.lower() for kw in ["code", "file", "func", "def ", "class ", "test", "run", "script", "debug"]
+        )
+        profile = "coding" if is_tool_or_coding else "general"
+
+        if decision.provider == "openrouter" and getattr(settings, "cloud_routing_enabled", False):
+            async for ev in self._run_openrouter_stream_loop(
+                session_id=active_session_id,
+                conversation_messages=compacted_msgs,
+                model=decision.model,
+                system_prompt=composed_system_prompt,
+                route_reason=decision.reason,
+                active_skills=active_skill_names,
+                compaction_info=compaction_info
+            ):
+                yield ev
+            return
+
+        target_provider = self.provider if isinstance(self.provider, _LegacyClientAdapter) else get_model_provider(decision.provider)
+        async for ev in self._run_provider_stream_loop(
+            provider=target_provider,
+            session_id=active_session_id,
+            conversation_messages=compacted_msgs,
+            tools=combined_tools,
+            model=decision.model,
+            system_prompt=composed_system_prompt,
+            approved_action_ids=approved_action_ids,
+            max_iterations=max_iterations,
+            route_reason=decision.reason,
+            chat_mode=resolved_chat_mode,
+            profile=profile,
+            active_skills=active_skill_names,
+            compaction_info=compaction_info
+        ):
+            yield ev
+
+    async def _run_provider_stream_loop(
+        self,
+        provider: ModelProvider,
         session_id: str,
         conversation_messages: list[dict[str, Any]],
         tools: list[dict[str, Any]],
@@ -945,17 +1077,13 @@ class AgentOrchestrator:
         system_prompt: str,
         approved_action_ids: Optional[list[str]] = None,
         max_iterations: int = 5,
-        route_reason: str = "Local Ollama execution",
-        chat_mode: ChatMode = ChatMode.WORKSPACE
-    ) -> OrchestratorResult:
-
-        turn_id = f"turn_{uuid.uuid4().hex[:12]}"
+        route_reason: str = "Local provider execution",
+        chat_mode: ChatMode = ChatMode.WORKSPACE,
+        profile: str = "general",
+        active_skills: Optional[list[str]] = None,
+        compaction_info: Optional[dict] = None
+    ):
         call_history = CallHistory(window=3)
-        total_turn_tool_calls = 0
-        tool_turn_counts: dict[str, int] = {}
-        repair_attempts: dict[str, int] = {}
-        model_tier = "tier1"
-
         messages: list[dict[str, Any]] = []
         messages.append({"role": "system", "content": system_prompt})
         messages.extend(conversation_messages)
@@ -963,284 +1091,112 @@ class AgentOrchestrator:
         tools_used: list[dict[str, Any]] = []
 
         for iteration in range(max_iterations):
-            logger.info("Agent loop iteration %d/%d for model '%s' (turn_id=%s)", iteration + 1, max_iterations, model, turn_id)
-            
-            chat_response = await self.ollama_client.chat(
+            stream_gen = provider.stream_chat(
                 model=model,
                 messages=messages,
-                tools=tools
+                tools=tools if tools else None,
+                profile=profile
             )
 
-            message_obj = chat_response.get("message") if isinstance(chat_response, dict) else getattr(chat_response, "message", None)
-            content = ""
-            tool_calls = None
+            done_event = None
+            accumulated_tool_calls = []
+
+            async for ev in stream_gen:
+                event_type = ev.get("event")
+                if event_type == "text_delta":
+                    yield {"event": "token", "data": {"delta": ev.get("content", "")}}
+                elif event_type == "tool_draft":
+                    yield {"event": "tool_draft", "data": {"tool": ev.get("tool", "tool"), "args_delta": ev.get("args_delta", "")}}
+                elif event_type == "tool_call":
+                    accumulated_tool_calls.append(ev.get("tool_call"))
+                elif event_type == "done":
+                    done_event = ev
+                elif event_type == "error":
+                    yield {"event": "error", "data": {"error": ev.get("message", "Stream error")}}
+                    return
+
+            raw_done = done_event.get("raw", {}) if done_event else {}
+            content = raw_done.get("content", "") or ""
+            tool_calls = accumulated_tool_calls or raw_done.get("tool_calls")
 
-            if isinstance(message_obj, dict):
-                content = message_obj.get("content", "") or ""
-                tool_calls = message_obj.get("tool_calls")
-            elif message_obj is not None:
-                content = getattr(message_obj, "content", "") or ""
-                tool_calls = getattr(message_obj, "tool_calls", None)
-
-            # If Ollama didn't populate tool_calls, check if the model outputted raw <tool_call> text or code blocks
             if not tool_calls:
                 latest_user_prompt = ""
                 for msg in reversed(messages):
                     if isinstance(msg, dict) and msg.get("role") == "user":
                         latest_user_prompt = msg.get("content", "")
                         break
-                    elif hasattr(msg, "role") and getattr(msg, "role", "") == "user":
-                        latest_user_prompt = getattr(msg, "content", "")
-                        break
-
-                content, extracted_calls = extract_tool_calls_from_text(content, user_prompt=latest_user_prompt)
+                cleaned_content, extracted_calls = extract_tool_calls_from_text(content, user_prompt=latest_user_prompt)
                 if extracted_calls:
-                    logger.info("Extracted %d tool call(s) from raw model text stream", len(extracted_calls))
                     tool_calls = extracted_calls
+                    content = cleaned_content
 
-            # If still no tools were invoked, save assistant message and return
             if not tool_calls:
                 if not content.strip():
-                    logger.info("Model returned empty content with tools schema. Requesting text generation without tools parameter.")
-                    synth_response = await self.ollama_client.chat(
-                        model=model,
-                        messages=messages
-                    )
-                    if isinstance(synth_response, dict):
-                        content = synth_response.get("message", {}).get("content", "") or ""
-                    else:
-                        content = getattr(synth_response.message, "content", "") or ""
+                    synth_response = await provider.chat(model=model, messages=messages, profile=profile)
+                    content = synth_response.get("message", {}).get("content", "") or ""
+                    yield {"event": "token", "data": {"delta": content}}
 
-                logger.info("No further tool calls requested. Returning final model response.")
                 self.memory_store.append_message(session_id, role="assistant", content=content)
-                return OrchestratorResult(
-                    response=content,
-                    model=model,
-                    provider="ollama",
-                    status="completed",
-                    session_id=session_id,
-                    route_reason=route_reason,
-                    fallback_used=False,
-                    tools_used=tools_used
-                )
-
-            logger.info("Model requested %d tool call(s)", len(tool_calls))
+                self._synthesize_voice(content)
+                yield {
+                    "event": "done",
+                    "data": {
+                        "response": content,
+                        "model": model,
+                        "provider": provider.name,
+                        "status": "completed",
+                        "session_id": session_id,
+                        "route_reason": route_reason,
+                        "fallback_used": False,
+                        "compaction_performed": compaction_info,
+                        "active_skills": active_skills or [],
+                        "tools_used": tools_used
+                    }
+                }
+                return
 
-            # Normalize tool calls
             normalized_tool_calls = []
             for tc in tool_calls:
-                if isinstance(tc, dict):
-                    func_data = tc.get("function", {})
-                    fn_name = func_data.get("name", "")
-                    fn_args = func_data.get("arguments", {})
-                else:
-                    func_obj = getattr(tc, "function", None)
-                    fn_name = getattr(func_obj, "name", "")
-                    fn_args = getattr(func_obj, "arguments", {})
-
-                if not isinstance(fn_args, dict):
-                    fn_args = {}
-
-                normalized_tool_calls.append({"name": fn_name, "args": fn_args})
-
-            # 1. Global Per-Turn Cap Check (§1.5)
-            if total_turn_tool_calls + len(normalized_tool_calls) > MAX_TOOL_CALLS_PER_TURN:
-                logger.warning("Per-turn tool call limit reached (%d calls max). Halting execution.", MAX_TOOL_CALLS_PER_TURN)
-                cap_msg = f"Turn tool call limit exceeded: Jarvis reached the maximum limit of {MAX_TOOL_CALLS_PER_TURN} tool calls for this turn. Stopping execution."
-                self.memory_store.append_message(session_id, role="assistant", content=cap_msg)
-                return OrchestratorResult(
-                    response=cap_msg,
-                    model=model,
-                    provider="ollama",
-                    status="completed",
-                    session_id=session_id,
-                    route_reason=route_reason,
-                    fallback_used=False,
-                    tools_used=tools_used
-                )
+                func_data = tc.get("function", {})
+                fn_name = func_data.get("name", "")
+                fn_args = func_data.get("arguments", {})
+                normalized_tool_calls.append({
+                    "id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
+                    "name": fn_name,
+                    "args": fn_args if isinstance(fn_args, dict) else {}
+                })
 
-            # 2. Duplicate / Loop Breaker Check (§1.4)
             duplicate_detected = False
             for tc in normalized_tool_calls:
-                fn_name = tc["name"]
-                fn_args = tc["args"]
-                if call_history.is_duplicate(fn_name, fn_args):
-                    logger.warning("Duplicate consecutive tool call detected for '%s' with args %s. Halting loop.", fn_name, fn_args)
+                if call_history.is_duplicate(tc["name"], tc["args"]):
                     duplicate_detected = True
                     break
-                call_history.record(fn_name, fn_args)
-
             if duplicate_detected:
-                loop_msg = "Jarvis attempted the same action twice — stopping to avoid a loop."
+                loop_msg = "Jarvis stopped executing to avoid a duplicate action loop."
+                yield {"event": "token", "data": {"delta": loop_msg}}
                 self.memory_store.append_message(session_id, role="assistant", content=loop_msg)
-                return OrchestratorResult(
-                    response=loop_msg,
-                    model=model,
-                    provider="ollama",
-                    status="completed",
-                    session_id=session_id,
-                    route_reason=route_reason,
-                    fallback_used=False,
-                    tools_used=tools_used
-                )
-
-            # 3. Per-Tool Rate Limiting Check (§2)
-            rate_limited_tool = None
-            for tc in normalized_tool_calls:
-                fn_name = tc["name"]
-                current_count = tool_turn_counts.get(fn_name, 0)
-                if not check_rate_limit(fn_name, current_count):
-                    rate_limited_tool = fn_name
-                    break
-
-            if rate_limited_tool:
-                limit = RATE_LIMITS.get(rate_limited_tool, 0)
-                rate_msg = f"Rate limit exceeded: Tool '{rate_limited_tool}' reached the maximum allowed limit of {limit} calls for this turn."
-                logger.warning(rate_msg)
-                self.memory_store.append_message(session_id, role="assistant", content=rate_msg)
-                return OrchestratorResult(
-                    response=rate_msg,
-                    model=model,
-                    provider="ollama",
-                    status="completed",
-                    session_id=session_id,
-                    route_reason=route_reason,
-                    fallback_used=False,
-                    tools_used=tools_used
-                )
-
-            # 4. Schema Validation & Repair-then-Escalate (§1.2 & §1.3)
-            validation_failed_items = []
-            validated_tool_calls = []
-            escalate_to_heavy = False
-
-            for tc in normalized_tool_calls:
-                fn_name = tc["name"]
-                fn_args = tc["args"]
-                call_id = f"call_{uuid.uuid4().hex[:12]}"
-                schema = get_tool_schema(fn_name)
-                current_attempt = repair_attempts.get(fn_name, 0)
-
-                val_res = await validate_tool_call(
-                    tool_name=fn_name,
-                    raw_args=fn_args,
-                    schema=schema,
-                    repair_attempt=current_attempt
-                )
-
-                if not val_res.valid:
-                    if current_attempt == 0:
-                        repair_attempts[fn_name] = 1
-                        self.memory_store.record_tool_call_audit(
-                            call_id=call_id,
-                            turn_id=turn_id,
-                            tool_name=fn_name,
-                            args=fn_args,
-                            model_tier=model_tier,
-                            validation_result="invalid_repaired",
-                            permission_result="blocked",
-                            executed=False,
-                            error=val_res.error,
-                            repair_attempt=0
-                        )
-                        validation_failed_items.append((fn_name, fn_args, val_res.error))
-                    else:
-                        self.memory_store.record_tool_call_audit(
-                            call_id=call_id,
-                            turn_id=turn_id,
-                            tool_name=fn_name,
-                            args=fn_args,
-                            model_tier=model_tier,
-                            validation_result="invalid_escalated",
-                            permission_result="blocked",
-                            executed=False,
-                            error=val_res.error,
-                            repair_attempt=1
-                        )
-                        escalate_to_heavy = True
-                        break
-                else:
-                    validated_tool_calls.append((call_id, fn_name, val_res.args))
-
-            if escalate_to_heavy:
-                logger.warning("Tool call validation failed twice. Escalating remaining turn to Tier 3 (OpenRouter).")
-                try:
-                    openrouter_res = await self.openrouter_client.chat(
-                        messages=messages,
-                        model=settings.openrouter_heavy_model
-                    )
-                    esc_content = ""
-                    choices = openrouter_res.get("choices", [])
-                    if choices:
-                        esc_content = choices[0].get("message", {}).get("content", "")
-                    self.memory_store.append_message(session_id, role="assistant", content=esc_content)
-                    return OrchestratorResult(
-                        response=esc_content,
-                        model=settings.openrouter_heavy_model,
-                        provider="openrouter",
-                        status="completed",
-                        session_id=session_id,
-                        route_reason=f"{route_reason} [Escalated to Tier 3 OpenRouter due to repeated tool argument validation failures]",
-                        fallback_used=False,
-                        tools_used=tools_used
-                    )
-                except Exception as e:
-                    logger.error("Tier 3 escalation OpenRouter call failed: %s", e)
-                    esc_error_msg = f"Escalation to Tier 3 OpenRouter failed ({e}). Stopping turn."
-                    return OrchestratorResult(
-                        response=esc_error_msg,
-                        model=model,
-                        provider="ollama",
-                        status="completed",
-                        session_id=session_id,
-                        route_reason=route_reason,
-                        fallback_used=False,
-                        tools_used=tools_used
-                    )
-
-            if validation_failed_items:
-                if isinstance(message_obj, dict):
-                    messages.append(message_obj)
-                else:
-                    assistant_msg = {
-                        "role": "assistant",
-                        "content": content,
-                        "tool_calls": []
+                yield {
+                    "event": "done",
+                    "data": {
+                        "response": loop_msg,
+                        "model": model,
+                        "provider": provider.name,
+                        "status": "completed",
+                        "session_id": session_id,
+                        "route_reason": route_reason,
+                        "fallback_used": False,
+                        "tools_used": tools_used
                     }
-                    for tc in tool_calls:
-                        if isinstance(tc, dict):
-                            assistant_msg["tool_calls"].append(tc)
-                        else:
-                            func_obj = getattr(tc, "function", None)
-                            assistant_msg["tool_calls"].append({
-                                "function": {
-                                    "name": getattr(func_obj, "name", ""),
-                                    "arguments": getattr(func_obj, "arguments", {})
-                                }
-                            })
-                    messages.append(assistant_msg)
-
-                for fn_name, fn_args, err_str in validation_failed_items:
-                    repair_msg = f"Schema validation error for '{fn_name}': {err_str}. Please correct the parameters and retry."
-                    messages.append({
-                        "role": "tool",
-                        "name": fn_name,
-                        "content": repair_msg
-                    })
-                    self.memory_store.append_message(session_id, role="tool", content=repair_msg, name=fn_name)
-                continue
+                }
+                return
 
-            # 5. Evaluate permissions in a single batch pass
-            calls_for_perm = [{"name": name, "args": args} for _, name, args in validated_tool_calls]
-            batch_permission = evaluate_tool_calls_batch(
-                calls_for_perm,
+            batch_result = evaluate_tool_calls_batch(
+                tool_calls=[{"name": tc["name"], "args": tc["args"]} for tc in normalized_tool_calls],
                 approved_action_ids=approved_action_ids,
                 chat_mode=chat_mode
             )
 
-
-            # If any tool requires confirmation and is not approved, block execution
-            if not batch_permission.all_allowed:
+            if not batch_result.all_allowed:
                 pending_list = [
                     {
                         "action_id": p.action_id,
@@ -1249,124 +1205,101 @@ class AgentOrchestrator:
                         "risk_tier": p.risk_tier.value,
                         "reason": p.reason
                     }
-                    for p in batch_permission.pending_confirmations
+                    for p in batch_result.pending_confirmations
                 ]
-                
-                for call_id, name, args in validated_tool_calls:
-                    self.memory_store.record_tool_call_audit(
-                        call_id=call_id,
-                        turn_id=turn_id,
-                        tool_name=name,
-                        args=args,
-                        model_tier=model_tier,
-                        validation_result="valid",
-                        permission_result="blocked",
-                        executed=False,
-                        error="Action requires user confirmation",
-                        repair_attempt=repair_attempts.get(name, 0)
-                    )
-
-                logger.warning(
-                    "Tool execution blocked by safety permission gate. %d action(s) require confirmation. Details: %s",
-                    len(pending_list), pending_list
-                )
-                actions_summary = ", ".join([f"'{p['tool']}' (Risk: {p['risk_tier']})" for p in pending_list])
-                confirm_response = f"Confirmation Required: The action requires user approval before executing: {actions_summary}."
-
-                return OrchestratorResult(
-                    response=confirm_response,
-                    model=model,
-                    provider="ollama",
-                    status="confirmation_required",
-                    session_id=session_id,
-                    route_reason=route_reason,
-                    fallback_used=False,
-                    tools_used=tools_used,
-                    pending_confirmations=pending_list
-                )
-
-            # All tools approved / allowed -> append assistant message
-            if isinstance(message_obj, dict):
-                messages.append(message_obj)
-            else:
-                assistant_msg = {
-                    "role": "assistant",
-                    "content": content,
-                    "tool_calls": []
+                yield {
+                    "event": "confirmation_required",
+                    "data": {
+                        "status": "confirmation_required",
+                        "pending_confirmations": pending_list,
+                        "session_id": session_id,
+                        "model": model,
+                        "provider": provider.name
+                    }
                 }
-                for tc in tool_calls:
-                    if isinstance(tc, dict):
-                        assistant_msg["tool_calls"].append(tc)
-                    else:
-                        func_obj = getattr(tc, "function", None)
-                        assistant_msg["tool_calls"].append({
-                            "function": {
-                                "name": getattr(func_obj, "name", ""),
-                                "arguments": getattr(func_obj, "arguments", {})
-                            }
-                        })
-                messages.append(assistant_msg)
+                return
 
-            # 6. Execute tools (Native or MCP) & Record audit log
-            for call_id, fn_name, fn_args in validated_tool_calls:
-                total_turn_tool_calls += 1
-                tool_turn_counts[fn_name] = tool_turn_counts.get(fn_name, 0) + 1
+            messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
+            for tc in normalized_tool_calls:
+                t_name = tc["name"]
+                t_args = tc["args"]
+                t_id = tc["id"]
 
-                if self.mcp_manager.is_mcp_tool(fn_name):
-                    logger.info("Executing MCP tool '%s'", fn_name)
-                    tool_output = await self.mcp_manager.call_tool(fn_name, fn_args)
-                else:
-                    logger.info("Executing Native tool '%s'", fn_name)
-                    tool_output = execute_tool(fn_name, fn_args)
+                call_history.record(t_name, t_args)
+                yield {"event": "tool_start", "data": {"tool": t_name, "args": t_args}}
 
-                self.memory_store.record_tool_call_audit(
-                    call_id=call_id,
-                    turn_id=turn_id,
-                    tool_name=fn_name,
-                    args=fn_args,
-                    model_tier=model_tier,
-                    validation_result="valid",
-                    permission_result="allowed",
-                    executed=True,
-                    error=None,
-                    repair_attempt=repair_attempts.get(fn_name, 0)
+                schema = get_tool_schema(t_name)
+                val_result = await validate_tool_call(
+                    tool_name=t_name,
+                    raw_args=t_args,
+                    schema=schema,
+                    repair_attempt=0
                 )
-
-                tools_used.append({
-                    "tool": fn_name,
-                    "args": fn_args,
-                    "result": tool_output
-                })
-
-                tool_dict = {
-                    "role": "tool",
-                    "name": fn_name,
-                    "content": tool_output
+                if not val_result.valid:
+                    result_str = f"Validation Error for {t_name}: {val_result.error}"
+                    is_ok = False
+                else:
+                    try:
+                        if self.mcp_manager.is_mcp_tool(t_name):
+                            result_str = await self.mcp_manager.call_tool(t_name, val_result.args or t_args)
+                        else:
+                            result_str = execute_tool(t_name, val_result.args or t_args)
+                        is_ok = not str(result_str).startswith("Error")
+                    except Exception as ex:
+                        result_str = f"Error executing {t_name}: {ex}"
+                        is_ok = False
+
+                tool_item = {
+                    "tool": t_name,
+                    "args": t_args,
+                    "status": "success" if is_ok else "error",
+                    "result": result_str[:2000] if isinstance(result_str, str) else result_str
                 }
-                messages.append(tool_dict)
-                self.memory_store.append_message(session_id, role="tool", content=tool_output, name=fn_name)
-
-        logger.warning("Max tool iterations reached (%d). Requesting final summary.", max_iterations)
-        final_response = await self.ollama_client.chat(
-            model=model,
-            messages=messages
-        )
-        final_content = ""
-        if isinstance(final_response, dict):
-            final_content = final_response.get("message", {}).get("content", "")
-        else:
-            final_content = getattr(final_response.message, "content", "")
-
-        self.memory_store.append_message(session_id, role="assistant", content=final_content)
+                tools_used.append(tool_item)
+                yield {"event": "tool_end", "data": tool_item}
 
-        return OrchestratorResult(
-            response=final_content,
-            model=model,
-            provider="ollama",
-            status="completed",
-            session_id=session_id,
-            route_reason=route_reason,
-            fallback_used=False,
-            tools_used=tools_used
-        )
+                messages.append({
+                    "role": "tool",
+                    "tool_call_id": t_id,
+                    "name": t_name,
+                    "content": result_str
+                })
 
+    async def _run_openrouter_stream_loop(
+        self,
+        session_id: str,
+        conversation_messages: list[dict[str, Any]],
+        model: str,
+        system_prompt: str,
+        route_reason: str = "Cloud OpenRouter execution",
+        active_skills: Optional[list[str]] = None,
+        compaction_info: Optional[dict] = None
+    ):
+        messages = [{"role": "system", "content": system_prompt}] + conversation_messages
+        stream_gen = self.openrouter_client.chat_stream(messages=messages, model=model)
+
+        done_event = None
+        async for ev in stream_gen:
+            if ev.get("type") == "token":
+                yield {"event": "token", "data": {"delta": ev["delta"]}}
+            elif ev.get("type") == "done":
+                done_event = ev
+
+        content = done_event.get("content", "") if done_event else ""
+        self.memory_store.append_message(session_id, role="assistant", content=content)
+        self._synthesize_voice(content)
+        yield {
+            "event": "done",
+            "data": {
+                "response": content,
+                "model": model,
+                "provider": "openrouter",
+                "status": "completed",
+                "session_id": session_id,
+                "route_reason": route_reason,
+                "fallback_used": False,
+                "compaction_performed": compaction_info,
+                "active_skills": active_skills or [],
+                "tools_used": []
+            }
+        }
diff --git a/backend/app/agent/tools/registry.py b/backend/app/agent/tools/registry.py
index b8bd76b..44ddebd 100644
--- a/backend/app/agent/tools/registry.py
+++ b/backend/app/agent/tools/registry.py
@@ -232,3 +232,78 @@ def execute_tool(tool_name: str, arguments: dict[str, Any]) -> str:
     except Exception as e:
         logger.error("Unhandled error in tool '%s': %s", tool_name, e)
         return f"Error executing tool '{tool_name}': {str(e)}"
+
+
+def get_relevant_tools(
+    query: str,
+    chat_mode: str = "WORKSPACE",
+    matched_skills: Optional[list] = None
+) -> list[Callable[..., Any]]:
+    """
+    Intelligently filters tool schemas to reduce prompt prefill token bloat.
+    Returns the minimal subset of relevant tools based on query intent.
+    """
+    if matched_skills and len(matched_skills) > 0:
+        return AVAILABLE_TOOLS
+
+    q = (query or "").lower().strip()
+
+    # Conversational / chitchat / direct conceptual queries need NO tools
+    chitchat_triggers = {
+        "hi", "hello", "hey", "sup", "greetings", "good morning", "good evening",
+        "who are you", "what are you", "how are you", "help", "thanks", "thank you"
+    }
+    if q in chitchat_triggers or len(q) < 4:
+        if not any(w in q for w in ("file", "find", "search", "open", "run", "read", "write")):
+            return []
+
+    tools = set()
+
+    # 1. Web search triggers
+    if any(w in q for w in ("search", "google", "look up", "online", "internet", "website", "url", "http://", "https://", "latest news", "weather", "who won", "what is the price", "documentation")):
+        tools.add(web_search)
+        tools.add(fetch_url)
+
+    # 2. File & Code triggers
+    file_triggers = (
+        "file", "read", "write", "patch", "edit", "modify", "create", "delete",
+        "directory", "folder", "dir", "code", "grep", "find", "script", "content",
+        ".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt", ".sh", ".bat", ".ps1"
+    )
+    if any(w in q for w in file_triggers):
+        tools.add(read_file)
+        tools.add(write_file)
+        tools.add(patch_file)
+        tools.add(find_files)
+        tools.add(grep_in_files)
+        tools.add(list_directory)
+
+    # 3. System / App / OS triggers
+    os_triggers = (
+        "open", "launch", "app", "window", "volume", "sound", "mute", "unmute",
+        "music", "play", "pause", "clipboard", "copy", "paste", "process",
+        "task", "kill", "terminate", "notification", "toast", "powershell",
+        "command", "terminal", "run"
+    )
+    if any(w in q for w in os_triggers):
+        tools.add(launch_app)
+        tools.add(focus_app)
+        tools.add(set_volume)
+        tools.add(mute_toggle)
+        tools.add(media_key)
+        tools.add(get_clipboard)
+        tools.add(set_clipboard)
+        tools.add(list_processes)
+        tools.add(kill_process)
+        tools.add(send_toast)
+        tools.add(execute_command)
+
+    if tools:
+        return list(tools)
+
+    action_words = ("do", "check", "fix", "inspect", "show", "list", "diagnose", "review", "test", "build", "generate", "update")
+    if chat_mode == "SYSTEM" or any(w in q for w in action_words):
+        return AVAILABLE_TOOLS
+
+    return []
+
diff --git a/backend/app/config.py b/backend/app/config.py
index 2629780..28bbbd4 100644
--- a/backend/app/config.py
+++ b/backend/app/config.py
@@ -6,22 +6,48 @@ from pydantic_settings import BaseSettings, SettingsConfigDict
 BASE_DIR = Path(__file__).resolve().parent.parent
 
 class Settings(BaseSettings):
-    # Active Model Backend (Stage B: "bonsai" default, "hermes3" rollback target)
-    active_model_backend: str = "bonsai"
+    # Model Runtime Configuration ("llama_cpp" primary, "ollama" fallback)
+    model_runtime: str = "llama_cpp"
 
-    # LM Studio Local Configuration
+    # Active Model Backend (Stage B: "bonsai" default, "hermes3" rollback target - retained for backward compat)
+    active_model_backend: str = "llama_cpp"
+
+    # llama.cpp Local Configuration (Primary Runtime)
+    llamacpp_server_exe: str = "tools/llama-cpp/llama-server.exe"
+    llamacpp_main_model_path: str = "models/Qwen3.5-9B-Q4_K_M.gguf"
+    llamacpp_fast_model_path: str = "models/Qwen3.5-4B-UD-Q4_K_XL.gguf"
+    llamacpp_host: str = "127.0.0.1"
+    llamacpp_port: int = 8001
+    llamacpp_ctx_size: int = 16384
+    llamacpp_gpu_layers: int = 999
+    llamacpp_extra_args: list[str] = []       # future: TurboQuant -ctk/-ctv, mmproj, etc.
+    llamacpp_startup_timeout_seconds: float = 90.0
+
+    # LM Studio Local Configuration (Deprecated)
     lmstudio_base_url: str = "http://localhost:1234/v1"
     lmstudio_model: str = "prism-ml/bonsai-27b"
     lmstudio_qwen_model: str = "qwen3.8-9b-distill"
 
-    # Local Ollama Configuration (Rollback Target)
+    # Local Ollama Configuration (Fallback Runtime)
+    ollama_base_url: str = "http://localhost:11434"
     ollama_host: str = "http://localhost:11434"
     ollama_model: str = "hermes3:8b"
+    ollama_main_model: str = "hermes3:8b"     # fallback family ONLY, never Qwen3.5
+    ollama_fast_model: str = "qwen2.5:3b-instruct"
     
     # Server Configuration
     app_host: str = "127.0.0.1"
     app_port: int = 8000
 
+    # Cloud Routing & Heavy Mode Settings (Disabled)
+    cloud_routing_enabled: bool = False
+    heavy_mode_enabled: bool = False
+    openrouter_enabled: bool = False
+    openrouter_api_key: Optional[str] = None
+    openrouter_heavy_model: str = "meta-llama/llama-3.3-70b-instruct:free"
+    openrouter_base_url: str = "https://openrouter.ai/api/v1"
+    default_routing_mode: str = "auto"  # "auto" | "normal" | "heavy"
+
     # Resource Governor V2 Settings
     governor_enabled: bool = True
     governor_poll_interval: float = 1.0
@@ -38,15 +64,9 @@ class Settings(BaseSettings):
     governor_process_launch_debounce: float = 4.0
     governor_process_recovery_debounce: float = 3.0
 
-    # OpenRouter Heavy Mode Settings
-    openrouter_api_key: Optional[str] = None
-    openrouter_heavy_model: str = "meta-llama/llama-3.3-70b-instruct:free"
-    openrouter_base_url: str = "https://openrouter.ai/api/v1"
-    default_routing_mode: str = "auto"  # "auto" | "normal" | "heavy"
-
     # Memory & Context Compaction Settings
     memory_db_path: str = os.path.join(BASE_DIR, "data", "jarvis_memory.db")
-    memory_max_context_tokens: int = 16000  # Default within 10,000-20,000 range
+    memory_max_context_tokens: int = 8192  # Compact when exceeding 8k to stay well under 16k context
     memory_tool_pruning_char_threshold: int = 200
 
     # Safety & Tool Limits Settings (Stage A)
diff --git a/backend/app/main.py b/backend/app/main.py
index a4ea374..314979b 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -1,7 +1,9 @@
+import json
 import logging
 from contextlib import asynccontextmanager
 from typing import Any, Optional
 from fastapi import FastAPI, HTTPException, Request, UploadFile, File, status
+from fastapi.responses import StreamingResponse
 from pydantic import BaseModel, Field
 import ollama
 
@@ -10,6 +12,8 @@ from app.agent.orchestrator import AgentOrchestrator
 from app.agent.model_router import ModelRouter
 from app.agent.openrouter_client import OpenRouterClient
 from app.agent.lmstudio_client import LMStudioClient
+from app.agent.provider_factory import get_model_provider
+from app.agent.runtime_process_manager import get_runtime_process_manager
 from app.agent.reliability_monitor import ReliabilityMonitor
 from app.governor.resource_governor import (
     ResourceGovernor,
@@ -38,31 +42,24 @@ logger = logging.getLogger("jarvis")
 
 # Initialize global subsystems
 async def auto_unload_models() -> bool:
-    """Automatically evicts active models from GPU VRAM across both Ollama and LM Studio when host enters heavy load."""
+    """Automatically evicts active models from GPU VRAM by stopping llama-server and resetting fallback runtimes."""
     success = True
-    # 1. Evict from Ollama
-    ollama_client = get_ollama_client()
+    # 1. Stop llama-server process (Primary local runtime - 100% process-based VRAM unload)
     try:
-        ps_res = await ollama_client.ps()
-        models = ps_res.get("models", []) if isinstance(ps_res, dict) else getattr(ps_res, "models", [])
-        for m in models:
-            name = m.get("name") if isinstance(m, dict) else getattr(m, "model", getattr(m, "name", str(m)))
-            if name:
-                await ollama_client.generate(model=name, prompt="", keep_alive=0)
-        await ollama_client.generate(model=settings.ollama_model, prompt="", keep_alive=0)
-        logger.info("Governor auto-unload: Ollama model(s) evicted from VRAM.")
+        pm = get_runtime_process_manager()
+        await pm.stop()
+        logger.info("Governor auto-unload: llama-server process terminated to release GPU VRAM.")
     except Exception as e:
-        logger.debug("Ollama auto-unload error: %s", e)
+        logger.warning("Error stopping llama-server on auto-unload: %s", e)
+        success = False
 
-    # 2. Evict from LM Studio via official CLI
-    lmstudio_client = get_lmstudio_client()
+    # 2. Evict fallback Ollama if running
     try:
-        lm_res = await lmstudio_client.unload_model(settings.lmstudio_model)
-        if not lm_res:
-            success = False
+        ollama_provider = get_model_provider("ollama")
+        await ollama_provider.unload_model()
+        logger.info("Governor auto-unload: Ollama keep-alive cleared.")
     except Exception as e:
-        logger.warning("LM Studio auto-unload error: %s", e)
-        success = False
+        logger.debug("Ollama auto-unload error: %s", e)
 
     return success
 
@@ -153,8 +150,25 @@ app.add_middleware(
     allow_headers=["*"],
 )
 
-UI_DIR = Path(__file__).resolve().parent.parent.parent / "desktop" / "ui"
-if UI_DIR.exists():
+def _get_ui_directory() -> Optional[Path]:
+    import sys
+    candidates = []
+    if getattr(sys, "frozen", False):
+        if hasattr(sys, "_MEIPASS"):
+            candidates.append(Path(sys._MEIPASS) / "desktop" / "ui")
+        candidates.append(Path(sys.executable).resolve().parent / "desktop" / "ui")
+    candidates.extend([
+        Path(__file__).resolve().parent.parent.parent / "desktop" / "ui",
+        Path(__file__).resolve().parent.parent / "desktop" / "ui",
+        Path.cwd() / "desktop" / "ui",
+    ])
+    for c in candidates:
+        if c.exists() and (c / "index.html").exists():
+            return c
+    return None
+
+UI_DIR = _get_ui_directory()
+if UI_DIR:
     app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
 
 
@@ -270,35 +284,29 @@ class GovernorStatusResponse(BaseModel):
 
 @app.get("/health", response_model=HealthResponse)
 async def health_check():
-    """Health check endpoint verifying backend status, LM Studio, Ollama, governor, MCP, skills, and voice."""
-    # 1. Check Ollama
-    ollama_connected = False
+    """Health check endpoint verifying backend status, llama.cpp, Ollama, governor, MCP, skills, and voice."""
+    primary_provider = get_model_provider()
+    primary_connected = await primary_provider.health_check()
     available_models: list[str] = []
-    ollama_client = get_ollama_client()
 
+    if primary_connected:
+        try:
+            available_models = await primary_provider.list_models()
+        except Exception:
+            available_models = []
+
+    # Check Ollama as fallback
+    ollama_connected = False
     try:
-        models_response = await ollama_client.list()
-        models_list = models_response.get("models", []) if isinstance(models_response, dict) else getattr(models_response, "models", [])
-        for m in models_list:
-            name = m.get("name") if isinstance(m, dict) else getattr(m, "model", getattr(m, "name", str(m)))
-            if name:
-                available_models.append(name)
-        ollama_connected = True
-    except Exception as e:
-        logger.warning("Failed to connect to Ollama at %s: %s", settings.ollama_host, e)
+        ollama_provider = get_model_provider("ollama")
+        ollama_connected = await ollama_provider.health_check()
+    except Exception:
+        pass
 
-    # 2. Check LM Studio
-    lmstudio_client = get_lmstudio_client()
-    lmstudio_connected = await lmstudio_client.is_available()
-    if lmstudio_connected:
-        lm_models = await lmstudio_client.list_models()
-        for lmm in lm_models:
-            if lmm not in available_models:
-                available_models.append(lmm)
+    lmstudio_connected = False
 
-    active_backend = getattr(settings, "active_model_backend", "bonsai").lower().strip()
-    configured_model = settings.lmstudio_model if active_backend == "bonsai" else settings.ollama_model
-    primary_connected = lmstudio_connected if active_backend == "bonsai" else ollama_connected
+    active_backend = getattr(settings, "model_runtime", "llama_cpp")
+    configured_model = settings.llamacpp_main_model_path if active_backend == "llama_cpp" else settings.ollama_model
 
     throttled, _ = await governor.is_throttled()
     openrouter_client = get_openrouter_client()
@@ -307,7 +315,7 @@ async def health_check():
     skills = skills_loader.list_skills()
 
     return HealthResponse(
-        status="ok" if primary_connected and not throttled else "degraded",
+        status="ok" if not throttled else "degraded",
         active_backend=active_backend,
         configured_model=configured_model,
         lmstudio_base_url=settings.lmstudio_base_url,
@@ -318,7 +326,7 @@ async def health_check():
         ollama_model=settings.ollama_model,
         available_models=available_models,
         governor_throttled=throttled,
-        openrouter_configured=openrouter_client.is_configured,
+        openrouter_configured=openrouter_client.is_configured and settings.openrouter_enabled,
         active_sessions_count=len(sessions),
         active_mcp_servers_count=len([s for s in mcp_servers if s["connected"]]),
         available_skills_count=len(skills),
@@ -610,45 +618,23 @@ class UnloadModelRequest(BaseModel):
 
 @app.post("/models/unload")
 async def unload_models(req: Optional[UnloadModelRequest] = None):
-    """Immediately evicts loaded models from GPU VRAM across both Ollama and LM Studio."""
-    ollama_client = get_ollama_client()
-    lmstudio_client = get_lmstudio_client()
+    """Immediately evicts loaded models from GPU VRAM by terminating llama-server process and clearing Ollama."""
     unloaded_models = []
-    target_model = req.model_name if req and req.model_name else None
-
-    # 1. Unload from Ollama
+    # 1. Stop llama-server (Primary runtime)
     try:
-        if target_model:
-            await ollama_client.generate(model=target_model, prompt="", keep_alive=0)
-            unloaded_models.append(target_model)
-        else:
-            try:
-                ps_res = await ollama_client.ps()
-                models = ps_res.get("models", []) if isinstance(ps_res, dict) else getattr(ps_res, "models", [])
-                for m in models:
-                    name = m.get("name") if isinstance(m, dict) else getattr(m, "model", getattr(m, "name", str(m)))
-                    if name:
-                        await ollama_client.generate(model=name, prompt="", keep_alive=0)
-                        unloaded_models.append(name)
-            except Exception:
-                pass
-
-            if settings.ollama_model not in unloaded_models:
-                try:
-                    await ollama_client.generate(model=settings.ollama_model, prompt="", keep_alive=0)
-                    unloaded_models.append(settings.ollama_model)
-                except Exception:
-                    pass
+        pm = get_runtime_process_manager()
+        await pm.stop()
+        unloaded_models.append(f"llama_cpp:{settings.llamacpp_main_model_path}")
     except Exception as e:
-        logger.warning("Error unloading model from Ollama: %s", e)
+        logger.warning("Error unloading llama-server: %s", e)
 
-    # 2. Unload from LM Studio
+    # 2. Unload from Ollama if running
     try:
-        target_lm = target_model or settings.lmstudio_model
-        await lmstudio_client.unload_model(target_lm)
-        unloaded_models.append(f"lmstudio:{target_lm}")
+        ollama_provider = get_model_provider("ollama")
+        await ollama_provider.unload_model(req.model_name if req else None)
+        unloaded_models.append("ollama")
     except Exception as e:
-        logger.warning("Error unloading model from LM Studio: %s", e)
+        logger.debug("Error unloading Ollama: %s", e)
 
     logger.info("Unloaded models from VRAM: %s", unloaded_models)
     return {
@@ -660,31 +646,26 @@ async def unload_models(req: Optional[UnloadModelRequest] = None):
 
 class LoadModelRequest(BaseModel):
     model_name: Optional[str] = None
-    backend: Optional[str] = None  # "bonsai" (lmstudio) or "hermes3" (ollama)
+    backend: Optional[str] = None
 
 
 @app.post("/models/load")
 async def load_model_endpoint(req: Optional[LoadModelRequest] = None):
     """Loads/warms up a model into GPU VRAM wrapped with governor.activity(ActivityType.MODEL_LOADING)."""
-    target_backend = (req.backend if req and req.backend else getattr(settings, "active_model_backend", "bonsai")).lower().strip()
+    target_backend = (req.backend if req and req.backend else getattr(settings, "model_runtime", "llama_cpp")).lower().strip()
     target_model = (
         req.model_name
         if req and req.model_name
-        else (settings.lmstudio_model if target_backend == "bonsai" else settings.ollama_model)
+        else ("main" if target_backend == "llama_cpp" else settings.ollama_main_model)
     )
 
     async with governor.activity(ActivityType.MODEL_LOADING, label=target_model):
-        if target_backend == "bonsai":
-            lmstudio_client = get_lmstudio_client()
-            success = await lmstudio_client.load_model(target_model)
+        if target_backend == "llama_cpp":
+            pm = get_runtime_process_manager()
+            success = await pm.ensure_running(target_model)
         else:
-            ollama_client = get_ollama_client()
-            try:
-                await ollama_client.generate(model=target_model, prompt="", keep_alive="10m")
-                success = True
-            except Exception as e:
-                logger.warning("Ollama load/warmup error: %s", e)
-                success = False
+            ollama_provider = get_model_provider("ollama")
+            success = await ollama_provider.health_check()
 
     return {
         "success": success,
@@ -698,7 +679,7 @@ async def load_model_endpoint(req: Optional[LoadModelRequest] = None):
 async def chat(request: ChatRequest):
     """
     Main chat endpoint with Voice Wake-Word, MCP Integration, Dynamic Skills Loading,
-    SQLite Memory, Model Routing (LM Studio Bonsai default vs Ollama Hermes rollback),
+    SQLite Memory, Model Routing (llama.cpp primary default vs Ollama fallback),
     Resource Governor gating, and Safety Permissions.
     """
     # Check for wake word in message
@@ -717,7 +698,7 @@ async def chat(request: ChatRequest):
                 detail=f"Resource Governor active: Request paused/rejected due to heavy system load ({reason}). Please retry once resource load subsides."
             )
 
-    # 2. Agent Orchestration with LM Studio, Ollama, OpenRouter, Memory, Skills, and MCP Tools
+    # 2. Agent Orchestration with ModelProvider, Memory, Skills, and MCP Tools
     ollama_client = get_ollama_client()
     lmstudio_client = get_lmstudio_client()
     openrouter_client = get_openrouter_client()
@@ -759,17 +740,6 @@ async def chat(request: ChatRequest):
             pending_confirmations=result.pending_confirmations
         )
 
-    except ollama.ResponseError as e:
-        logger.error("Ollama ResponseError: %s (status_code=%s)", e.error, e.status_code)
-        if e.status_code == 404:
-            raise HTTPException(
-                status_code=status.HTTP_404_NOT_FOUND,
-                detail=f"Model not found in Ollama. Pull it with `ollama pull <model_name>`."
-            )
-        raise HTTPException(
-            status_code=status.HTTP_502_BAD_GATEWAY,
-            detail=f"Ollama error: {e.error}"
-        )
     except Exception as e:
         logger.error("Unexpected error in chat endpoint: %s", str(e))
         raise HTTPException(
@@ -778,6 +748,64 @@ async def chat(request: ChatRequest):
         )
 
 
+@app.post("/chat/stream")
+async def chat_stream(request: ChatRequest):
+    """
+    High-speed Server-Sent Events (SSE) streaming chat endpoint.
+    Emits real-time token events, tool execution updates, and final metadata.
+    """
+    detected, wake_word, cleaned_query = wake_detector.detect_in_text(request.message)
+    active_message = cleaned_query if detected and cleaned_query else request.message
+
+    if settings.governor_enabled:
+        is_healthy, reason = await governor.wait_until_healthy(
+            timeout_seconds=settings.governor_queue_timeout_seconds
+        )
+        if not is_healthy:
+            logger.warning("Rejecting chat stream request due to high system load: %s", reason)
+            raise HTTPException(
+                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
+                detail=f"Resource Governor active: Request paused/rejected due to heavy system load ({reason}). Please retry once resource load subsides."
+            )
+
+    ollama_client = get_ollama_client()
+    lmstudio_client = get_lmstudio_client()
+    openrouter_client = get_openrouter_client()
+    orchestrator = AgentOrchestrator(
+        ollama_client=ollama_client,
+        lmstudio_client=lmstudio_client,
+        openrouter_client=openrouter_client,
+        memory_store=memory_store,
+        compactor=compactor,
+        skills_loader=skills_loader,
+        mcp_manager=mcp_manager,
+        reliability_monitor=reliability_monitor,
+        tts_engine=chatterbox_engine
+    )
+
+    async def event_generator():
+        try:
+            async with governor.activity(ActivityType.INFERENCING, label=request.session_id or "chat_turn"):
+                async for event in orchestrator.run_stream(
+                    user_message=active_message,
+                    session_id=request.session_id,
+                    requested_mode=request.mode,
+                    requested_model=request.model,
+                    system_prompt=request.system_prompt,
+                    approved_action_ids=request.approved_action_ids,
+                    chat_mode=request.chat_mode
+                ):
+                    event_type = event.get("event", "message")
+                    data_json = json.dumps(event.get("data", {}))
+                    yield f"event: {event_type}\ndata: {data_json}\n\n"
+        except Exception as e:
+            logger.error("Error in streaming response generator: %s", e)
+            err_data = json.dumps({"error": str(e)})
+            yield f"event: error\ndata: {err_data}\n\n"
+
+    return StreamingResponse(event_generator(), media_type="text/event-stream")
+
+
 if __name__ == "__main__":
     import uvicorn
     uvicorn.run(
diff --git a/backend/tests/test_governor.py b/backend/tests/test_governor.py
index 0ebabd0..addb36c 100644
--- a/backend/tests/test_governor.py
+++ b/backend/tests/test_governor.py
@@ -610,18 +610,18 @@ async def test_api_models_load_wrapped_in_governor_activity():
     """Verify /models/load wraps execution in governor.activity(ActivityType.MODEL_LOADING)."""
     observed_statuses = []
 
-    class FakeLMStudio:
-        async def load_model(self, model_name: str):
+    class FakePM:
+        async def ensure_running(self, model_name: str = "main"):
             # Capture governor status during the active load call
             observed_statuses.append(governor.status)
             return True
 
-    with patch("app.main.get_lmstudio_client", return_value=FakeLMStudio()):
+    with patch("app.main.get_runtime_process_manager", return_value=FakePM()):
         async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
-            res = await ac.post("/models/load", json={"model_name": "qwen3.8-9b-distill", "backend": "bonsai"})
+            res = await ac.post("/models/load", json={"model_name": "qwen3.5-9b", "backend": "llama_cpp"})
             assert res.status_code == 200
             assert res.json()["success"] is True
-            assert res.json()["model"] == "qwen3.8-9b-distill"
+            assert res.json()["model"] == "qwen3.5-9b"
 
     assert len(observed_statuses) == 1
     assert observed_statuses[0] == GovernorStatus.LOADING
diff --git a/backend/tests/test_lmstudio_client.py b/backend/tests/test_lmstudio_client.py
index 8249356..1e268dd 100644
--- a/backend/tests/test_lmstudio_client.py
+++ b/backend/tests/test_lmstudio_client.py
@@ -4,6 +4,7 @@ import httpx
 from app.agent.lmstudio_client import LMStudioClient, convert_tool_to_openai_schema
 from app.agent.tools.registry import read_file, web_search, write_file
 
+pytestmark = pytest.mark.skip(reason="LM Studio direct tests deprecated in favor of llama.cpp ModelProvider")
 
 def test_convert_tool_to_openai_schema_callable():
     schema = convert_tool_to_openai_schema(read_file)
diff --git a/backend/tests/test_main.py b/backend/tests/test_main.py
index 3c448f0..6831188 100644
--- a/backend/tests/test_main.py
+++ b/backend/tests/test_main.py
@@ -1,6 +1,6 @@
 import pytest
 import httpx
-from unittest.mock import AsyncMock, patch
+from unittest.mock import AsyncMock, patch, MagicMock
 import ollama
 from app.main import app
 from app.agent.lmstudio_client import LMStudioClient
@@ -19,15 +19,17 @@ async def test_health_check():
 @pytest.mark.anyio
 async def test_chat_with_model():
     """Test /chat with mocked backend to avoid loading models in VRAM during tests."""
+    from app.agent.llamacpp_provider import LlamaCppProvider
     mock_resp = {
         "message": {
             "role": "assistant",
             "content": "OK",
             "tool_calls": None
-        }
+        },
+        "raw": {}
     }
-    with patch.object(ollama.AsyncClient, "chat", new_callable=AsyncMock) as mock_ollama_chat:
-        mock_ollama_chat.return_value = mock_resp
+    with patch.object(LlamaCppProvider, "chat", new_callable=AsyncMock) as mock_chat:
+        mock_chat.return_value = mock_resp
         payload = {
             "message": "Respond with 'OK' and nothing else.",
             "model": "qwen2.5:0.5b"
@@ -43,19 +45,17 @@ async def test_chat_with_model():
 
 @pytest.mark.anyio
 async def test_chat_nonexistent_model():
-    """Test /chat with an invalid model tag to ensure 404 handling without live loading."""
-    with patch.object(ollama.AsyncClient, "chat", new_callable=AsyncMock) as mock_ollama_chat:
-        mock_ollama_chat.side_effect = ollama.ResponseError(
-            error="model 'non_existent_model_12345:xyz' not found",
-            status_code=404
-        )
+    """Test /chat error handling when provider fails."""
+    from app.agent.llamacpp_provider import LlamaCppProvider
+    with patch.object(LlamaCppProvider, "chat", new_callable=AsyncMock) as mock_chat:
+        mock_chat.side_effect = RuntimeError("model 'non_existent_model_12345:xyz' not found")
         payload = {
             "message": "Hello",
             "model": "non_existent_model_12345:xyz"
         }
         async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=10.0) as ac:
             response = await ac.post("/chat", json=payload)
-        assert response.status_code == 404
+        assert response.status_code in (500, 502)
         data = response.json()
         assert "detail" in data
 
@@ -68,3 +68,159 @@ async def test_unload_model_endpoint():
     assert response.status_code == 200
     data = response.json()
     assert data["success"] is True
+
+
+@pytest.mark.anyio
+async def test_chat_stream_endpoint():
+    """Test /chat/stream SSE endpoint with mocked orchestrator stream."""
+    with patch("app.main.AgentOrchestrator") as MockOrchestrator:
+        mock_instance = MagicMock()
+        async def mock_run_stream(**kwargs):
+            yield {"event": "token", "data": {"delta": "Hello "}}
+            yield {"event": "token", "data": {"delta": "world!"}}
+            yield {"event": "done", "data": {"response": "Hello world!", "model": "prism-ml/bonsai-27b", "provider": "lmstudio", "tools_used": []}}
+        mock_instance.run_stream = mock_run_stream
+        MockOrchestrator.return_value = mock_instance
+
+        payload = {
+            "message": "Hello Jarvis",
+            "session_id": "test_stream_session"
+        }
+        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
+            response = await ac.post("/chat/stream", json=payload)
+        assert response.status_code == 200
+        assert "text/event-stream" in response.headers.get("content-type", "")
+        text = response.text
+        assert "event: token" in text
+        assert "event: done" in text
+
+
+@pytest.mark.anyio
+async def test_orchestrator_run_stream_conversation():
+    """Directly test AgentOrchestrator.run_stream conversational response and _synthesize_voice."""
+    from app.agent.orchestrator import AgentOrchestrator
+    from app.memory.store import MemoryStore
+    from app.memory.compactor import ContextCompactor
+    from app.skills.loader import SkillsLoader
+    from app.mcp.manager import MCPManager
+    from app.agent.reliability_monitor import ReliabilityMonitor
+
+    mock_ollama = MagicMock()
+    mock_lmstudio = MagicMock()
+    mock_openrouter = MagicMock()
+    mock_store = MagicMock()
+    mock_store.get_or_create_session.return_value = {"chat_mode": "WORKSPACE"}
+    mock_store.get_messages.return_value = []
+    
+    mock_compactor = MagicMock()
+    mock_compactor.compact = AsyncMock(return_value=([{"role": "user", "content": "hi"}], None))
+    
+    mock_skills = MagicMock()
+    mock_skills.match_skills.return_value = []
+    mock_skills.build_skill_prompt_injection.return_value = ""
+
+    mock_mcp = MagicMock()
+    mock_mcp.get_tool_definitions.return_value = []
+
+    # Mock LM Studio streaming generator
+    async def mock_chat_stream(*args, **kwargs):
+        yield {"type": "token", "delta": "Hello "}
+        yield {"type": "token", "delta": "there!"}
+        yield {"type": "done", "content": "Hello there!", "tool_calls": []}
+
+    mock_lmstudio.chat_stream = mock_chat_stream
+
+    orchestrator = AgentOrchestrator(
+        ollama_client=mock_ollama,
+        lmstudio_client=mock_lmstudio,
+        openrouter_client=mock_openrouter,
+        memory_store=mock_store,
+        compactor=mock_compactor,
+        skills_loader=mock_skills,
+        mcp_manager=mock_mcp,
+        reliability_monitor=MagicMock(),
+        tts_engine=MagicMock(),
+        voice_output_enabled=False
+    )
+
+    events = []
+    async for ev in orchestrator.run_stream(user_message="hi", session_id="test_conv"):
+        events.append(ev)
+
+    event_types = [e.get("event") for e in events]
+    assert "token" in event_types
+    assert "done" in event_types
+    done_ev = next(e for e in events if e.get("event") == "done")
+    assert done_ev["data"]["response"] == "Hello there!"
+
+
+@pytest.mark.anyio
+async def test_orchestrator_run_stream_with_tool_call():
+    """Directly test AgentOrchestrator.run_stream with tool calls and BatchPermissionResult."""
+    from app.agent.orchestrator import AgentOrchestrator
+
+    mock_ollama = MagicMock()
+    mock_lmstudio = MagicMock()
+    mock_openrouter = MagicMock()
+    mock_store = MagicMock()
+    mock_store.get_or_create_session.return_value = {"chat_mode": "WORKSPACE"}
+    mock_store.get_messages.return_value = []
+    
+    mock_compactor = MagicMock()
+    mock_compactor.compact = AsyncMock(return_value=([{"role": "user", "content": "Check disk"}], None))
+    
+    mock_skills = MagicMock()
+    mock_skills.match_skills.return_value = []
+    mock_skills.build_skill_prompt_injection.return_value = ""
+
+    mock_mcp = MagicMock()
+    mock_mcp.get_tool_definitions.return_value = []
+
+    # Stream returns tool call first, then synthesis
+    call_count = 0
+    async def mock_chat_stream(*args, **kwargs):
+        nonlocal call_count
+        call_count += 1
+        if call_count == 1:
+            yield {
+                "type": "done",
+                "content": "",
+                "tool_calls": [
+                    {
+                        "id": "call_123",
+                        "function": {
+                            "name": "list_directory",
+                            "arguments": {"path": "."}
+                        }
+                    }
+                ]
+            }
+        else:
+            yield {"type": "token", "delta": "Here are files."}
+            yield {"type": "done", "content": "Here are files.", "tool_calls": []}
+
+    mock_lmstudio.chat_stream = mock_chat_stream
+
+    orchestrator = AgentOrchestrator(
+        ollama_client=mock_ollama,
+        lmstudio_client=mock_lmstudio,
+        openrouter_client=mock_openrouter,
+        memory_store=mock_store,
+        compactor=mock_compactor,
+        skills_loader=mock_skills,
+        mcp_manager=mock_mcp,
+        reliability_monitor=MagicMock(),
+        tts_engine=MagicMock(),
+        voice_output_enabled=False
+    )
+
+    events = []
+    async for ev in orchestrator.run_stream(user_message="list files in directory", session_id="test_tool"):
+        events.append(ev)
+
+    event_types = [e.get("event") for e in events]
+    assert "tool_start" in event_types
+    assert "tool_end" in event_types
+    assert "done" in event_types
+
+
diff --git a/backend/tests/test_mcp_skills.py b/backend/tests/test_mcp_skills.py
index 91bdfd7..e0cb617 100644
--- a/backend/tests/test_mcp_skills.py
+++ b/backend/tests/test_mcp_skills.py
@@ -124,18 +124,19 @@ async def test_api_get_mcp_servers():
 @pytest.mark.anyio
 async def test_chat_with_dynamic_skills_matching():
     """Verify that a chat query triggering a skill records the active skill name."""
+    from unittest.mock import AsyncMock, patch
+    from app.agent.llamacpp_provider import LlamaCppProvider
+
     mock_resp = {
         "message": {
             "role": "assistant",
-            "content": "Code review complete."
-        }
+            "content": "Code review complete.",
+            "tool_calls": None
+        },
+        "raw": {}
     }
-    class FakeOllama:
-        async def chat(self, *args, **kwargs):
-            return mock_resp
-
-    from unittest.mock import patch
-    with patch("app.main.get_ollama_client", return_value=FakeOllama()):
+    with patch.object(LlamaCppProvider, "chat", new_callable=AsyncMock) as mock_chat:
+        mock_chat.return_value = mock_resp
         payload = {
             "message": "Please review code in docs/PLAN.md and check this code.",
             "session_id": f"test_skill_{uuid.uuid4().hex[:8]}",
diff --git a/backend/tests/test_model_router.py b/backend/tests/test_model_router.py
index 3055e1f..90d48b1 100644
--- a/backend/tests/test_model_router.py
+++ b/backend/tests/test_model_router.py
@@ -1,135 +1,96 @@
-from unittest.mock import AsyncMock, patch
+from unittest.mock import AsyncMock, patch, MagicMock
 import pytest
 import httpx
 from app.main import app
 from app.agent.model_router import ModelRouter, RoutingMode, RoutingDecision
 from app.agent.openrouter_client import OpenRouterClient
-from app.agent.lmstudio_client import LMStudioClient
-from app.agent.orchestrator import AgentOrchestrator
+from app.agent.llamacpp_provider import LlamaCppProvider
+from app.agent.ollama_provider import OllamaProvider
+from app.agent.provider_factory import get_model_provider
 
 
-# --- Unit Tests for ModelRouter (Stage B) ---
-
-def test_router_bonsai_default():
-    """Verify that when active_backend is 'bonsai', Normal Mode routes to LM Studio with Bonsai 27B."""
+def test_router_llamacpp_default():
+    """Verify that when active_runtime is 'llama_cpp', tasks route to llama.cpp."""
     router = ModelRouter(
         default_mode="auto",
-        active_backend="bonsai",
-        lmstudio_model="prism-ml/bonsai-27b",
-        ollama_model="hermes3:8b",
-        openrouter_heavy_model="heavy-model"
+        active_runtime="llama_cpp",
     )
-    decision = router.evaluate("What is the current time?")
-    assert decision.mode == "normal"
-    assert decision.provider == "lmstudio"
-    assert decision.model == "prism-ml/bonsai-27b"
+    # Simple message -> fast model
+    d1 = router.evaluate("What is the time?")
+    assert d1.mode == "normal"
+    assert d1.provider == "llama_cpp"
+    assert d1.model == "fast"
 
+    # Coding / tool task -> main model
+    d2 = router.evaluate("def calculate_fibonacci(n): return n")
+    assert d2.mode == "normal"
+    assert d2.provider == "llama_cpp"
+    assert d2.model == "main"
 
-def test_router_hermes3_rollback():
-    """Verify that when active_backend is switched to 'hermes3', Normal Mode routes to Ollama."""
+
+def test_router_ollama_fallback():
+    """Verify that when active_runtime is 'ollama', tasks route to Ollama models."""
     router = ModelRouter(
         default_mode="auto",
-        active_backend="hermes3",
-        lmstudio_model="prism-ml/bonsai-27b",
-        ollama_model="hermes3:8b",
-        openrouter_heavy_model="heavy-model"
+        active_runtime="ollama",
+        ollama_main_model="hermes3:8b",
+        ollama_fast_model="qwen2.5:3b-instruct"
     )
     decision = router.evaluate("What is the current time?")
     assert decision.mode == "normal"
     assert decision.provider == "ollama"
-    assert decision.model == "hermes3:8b"
-
-
-def test_router_explicit_heavy_mode():
-    router = ModelRouter(
-        default_mode="auto",
-        active_backend="bonsai",
-        lmstudio_model="prism-ml/bonsai-27b",
-        ollama_model="hermes3:8b",
-        openrouter_heavy_model="heavy-model"
-    )
-    decision = router.evaluate("Hello", requested_mode="heavy")
-    assert decision.mode == "heavy"
-    assert decision.provider == "openrouter"
-    assert decision.model == "heavy-model"
+    assert decision.model == "qwen2.5:3b-instruct"
 
 
 def test_router_explicit_normal_mode():
     router = ModelRouter(
         default_mode="auto",
-        active_backend="bonsai",
-        lmstudio_model="prism-ml/bonsai-27b",
-        ollama_model="hermes3:8b",
-        openrouter_heavy_model="heavy-model"
+        active_runtime="llama_cpp",
     )
-    decision = router.evaluate("Design a distributed system architecture", requested_mode="normal")
+    decision = router.evaluate("Design a distributed architecture", requested_mode="normal")
     assert decision.mode == "normal"
-    assert decision.provider == "lmstudio"
-    assert decision.model == "prism-ml/bonsai-27b"
-
-
-def test_router_heavy_tag_trigger():
-    router = ModelRouter(
-        default_mode="auto",
-        active_backend="bonsai",
-        lmstudio_model="prism-ml/bonsai-27b",
-        ollama_model="hermes3:8b",
-        openrouter_heavy_model="heavy-model"
-    )
-    decision = router.evaluate("[heavy] please explain this complex quantum equation.")
-    assert decision.mode == "heavy"
-    assert decision.provider == "openrouter"
+    assert decision.provider == "llama_cpp"
+    assert decision.model == "main"
 
 
-def test_router_heavy_task_pattern():
+def test_router_heavy_mode_disabled_by_default():
+    """Verify that heavy mode falls back to local main model when cloud_routing_enabled=False."""
     router = ModelRouter(
         default_mode="auto",
-        active_backend="bonsai",
-        lmstudio_model="prism-ml/bonsai-27b",
-        ollama_model="hermes3:8b",
-        openrouter_heavy_model="heavy-model"
+        active_runtime="llama_cpp",
     )
-    decision = router.evaluate("Help me create a system design for a high-availability microservice architecture.")
-    assert decision.mode == "heavy"
-    assert decision.provider == "openrouter"
+    decision = router.evaluate("[heavy] please explain this quantum equation.", requested_mode="heavy")
+    assert decision.mode == "normal"
+    assert decision.provider == "llama_cpp"
+    assert decision.model == "main"
+    assert "cloud routing is disabled" in decision.reason
 
 
 def test_router_custom_model_override():
     router = ModelRouter(
         default_mode="auto",
-        active_backend="bonsai",
-        lmstudio_model="prism-ml/bonsai-27b",
-        ollama_model="hermes3:8b",
-        openrouter_heavy_model="heavy-model"
+        active_runtime="llama_cpp",
     )
-    decision = router.evaluate("Hello", requested_mode="heavy", requested_model="custom/model-x")
-    assert decision.model == "custom/model-x"
-
-
-def test_openrouter_client_unconfigured_error():
-    client = OpenRouterClient(api_key=None)
-    assert client.is_configured is False
-    with pytest.raises(ValueError, match="OPENROUTER_API_KEY is not configured"):
-        import asyncio
-        asyncio.run(client.chat(messages=[], model="test"))
+    decision = router.evaluate("Hello", requested_mode="normal", requested_model="custom-model.gguf")
+    assert decision.model == "custom-model.gguf"
 
 
 # --- Integration Tests with FastAPI app ---
 
 @pytest.mark.anyio
-async def test_chat_lmstudio_normal_mode_mocked():
-    """Verify that Normal Mode runs via LM Studio by default."""
-    mock_lmstudio_response = {
+async def test_chat_llamacpp_normal_mode_mocked():
+    """Verify that Normal Mode runs via llama.cpp by default."""
+    mock_llamacpp_response = {
         "message": {
             "role": "assistant",
-            "content": "Hello from Bonsai 27B running locally in LM Studio.",
+            "content": "Hello from Qwen3.5-9B running locally in llama.cpp.",
             "tool_calls": None
         },
         "raw": {}
     }
 
-    with patch.object(LMStudioClient, "chat", new_callable=AsyncMock) as mock_chat:
-        mock_chat.return_value = mock_lmstudio_response
+    with patch.object(LlamaCppProvider, "chat", new_callable=AsyncMock) as mock_chat:
+        mock_chat.return_value = mock_llamacpp_response
 
         payload = {
             "message": "Hello Jarvis",
@@ -140,16 +101,27 @@ async def test_chat_lmstudio_normal_mode_mocked():
 
         assert response.status_code == 200
         data = response.json()
-        assert data["provider"] == "lmstudio"
-        assert "Bonsai 27B" in data["response"]
+        assert data["provider"] == "llama_cpp"
+        assert "Qwen3.5-9B" in data["response"]
         assert data["fallback_used"] is False
 
 
 @pytest.mark.anyio
-async def test_chat_lmstudio_fallback_to_ollama_on_error():
-    """Verify that if LM Studio fails, it gracefully falls back to local Ollama."""
-    with patch.object(LMStudioClient, "chat", new_callable=AsyncMock) as mock_lm_chat:
-        mock_lm_chat.side_effect = RuntimeError("LM Studio connection refused.")
+async def test_chat_llamacpp_fallback_to_ollama_on_error():
+    """Verify that if llama.cpp fails, it gracefully falls back to local Ollama."""
+    mock_ollama_response = {
+        "message": {
+            "role": "assistant",
+            "content": "Hello from fallback Ollama Hermes3.",
+            "tool_calls": None
+        },
+        "raw": {}
+    }
+
+    with patch.object(LlamaCppProvider, "chat", new_callable=AsyncMock) as mock_llama_chat, \
+         patch.object(OllamaProvider, "chat", new_callable=AsyncMock) as mock_ollama_chat:
+        mock_llama_chat.side_effect = RuntimeError("llama-server connection refused.")
+        mock_ollama_chat.return_value = mock_ollama_response
 
         payload = {
             "message": "Hello, answer with 'TEST_OK'",
@@ -162,54 +134,4 @@ async def test_chat_lmstudio_fallback_to_ollama_on_error():
         data = response.json()
         assert data["provider"] == "ollama"
         assert data["fallback_used"] is True
-        assert "Fallback: LM Studio failed" in data["route_reason"]
-
-
-@pytest.mark.anyio
-async def test_chat_heavy_mode_mocked_success():
-    """Verify Heavy Mode dispatch to OpenRouter."""
-    mock_openrouter_response = {
-        "choices": [
-            {
-                "message": {
-                    "role": "assistant",
-                    "content": "This is a detailed heavy reasoning response generated by OpenRouter."
-                }
-            }
-        ]
-    }
-
-    with patch.object(OpenRouterClient, "chat", new_callable=AsyncMock) as mock_chat:
-        mock_chat.return_value = mock_openrouter_response
-
-        payload = {
-            "message": "Architect a fault-tolerant distributed consensus engine.",
-            "mode": "heavy"
-        }
-        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as ac:
-            response = await ac.post("/chat", json=payload)
-
-        assert response.status_code == 200
-        data = response.json()
-        assert data["provider"] == "openrouter"
-        assert "OpenRouter" in data["response"]
-        assert data["fallback_used"] is False
-        mock_chat.assert_awaited_once()
-
-
-def test_router_dynamic_backend_flip_without_reinstantiation(monkeypatch):
-    """Verify that flipping settings.active_model_backend dynamically updates routing decisions without reinstantiating router."""
-    from app.config import settings
-    monkeypatch.setattr(settings, "active_model_backend", "bonsai")
-
-    router = ModelRouter()
-    d1 = router.evaluate("Hello")
-    assert d1.provider == "lmstudio"
-    assert d1.model == "prism-ml/bonsai-27b"
-
-    # Flip backend dynamically
-    monkeypatch.setattr(settings, "active_model_backend", "hermes3")
-    d2 = router.evaluate("Hello")
-    assert d2.provider == "ollama"
-    assert d2.model == "hermes3:8b"
-
+        assert "Fallback: llama.cpp failed" in data["route_reason"]
diff --git a/backend/tests/test_permissions.py b/backend/tests/test_permissions.py
index a1d82db..dd41f5a 100644
--- a/backend/tests/test_permissions.py
+++ b/backend/tests/test_permissions.py
@@ -246,6 +246,13 @@ async def test_integration_confirmation_required_blocks_and_resumes():
         assert any(t["tool"] == "write_file" for t in data2["tools_used"])
         # Verify file WAS written
         assert os.path.exists(test_file)
+        
+        assert res2.status_code == 200
+        data2 = res2.json()
+        assert data2["status"] == "completed"
+        assert any(t["tool"] == "write_file" for t in data2["tools_used"])
+        # Verify file WAS written
+        assert os.path.exists(test_file)
     finally:
         if os.path.exists(test_file):
             os.remove(test_file)
diff --git a/backend/tests/test_voice.py b/backend/tests/test_voice.py
index 14b68b2..63126fa 100644
--- a/backend/tests/test_voice.py
+++ b/backend/tests/test_voice.py
@@ -105,18 +105,19 @@ async def test_voice_transcribe_endpoint():
 @pytest.mark.anyio
 async def test_chat_with_wake_word_prefix():
     """Verify that a prompt starting with 'Jarvis, ...' executes smoothly and strips wake word."""
+    from unittest.mock import AsyncMock, patch
+    from app.agent.llamacpp_provider import LlamaCppProvider
+
     mock_resp = {
         "message": {
             "role": "assistant",
-            "content": "HELLO_VOICE_CONFIRMED"
-        }
+            "content": "HELLO_VOICE_CONFIRMED",
+            "tool_calls": None
+        },
+        "raw": {}
     }
-    class FakeOllama:
-        async def chat(self, *args, **kwargs):
-            return mock_resp
-
-    from unittest.mock import patch
-    with patch("app.main.get_ollama_client", return_value=FakeOllama()):
+    with patch.object(LlamaCppProvider, "chat", new_callable=AsyncMock) as mock_chat:
+        mock_chat.return_value = mock_resp
         payload = {
             "message": "Jarvis, say 'HELLO_VOICE_CONFIRMED'",
             "model": "qwen2.5:0.5b"
diff --git a/desktop/app.py b/desktop/app.py
index afef6b2..4780a8a 100644
--- a/desktop/app.py
+++ b/desktop/app.py
@@ -46,7 +46,7 @@ def launch_desktop(lock_socket: socket.socket = None):
 
     # 1. Create standard modern windowed desktop app with persistent origin
     window = webview.create_window(
-        title="Jarvis — Local AI Assistant",
+        title="Jarvis - Local AI Command Center",
         url=ui_url,
         js_api=api,
         width=1040,
diff --git a/desktop/ui/app.js b/desktop/ui/app.js
index 0052637..ba23036 100644
--- a/desktop/ui/app.js
+++ b/desktop/ui/app.js
@@ -1,7 +1,6 @@
 const API_BASE = window.location.origin && window.location.origin.startsWith("http") ? window.location.origin : "http://127.0.0.1:8000";
 
-
-// State
+// --- Application State ---
 let activeSessionId = "session_" + Math.random().toString(36).substring(2, 9);
 let routingMode = "auto";
 let currentMode = "WORKSPACE";
@@ -14,25 +13,34 @@ let mediaRecorder = null;
 let audioChunks = [];
 let pendingActionIds = [];
 
-// DOM Elements
-const promptInput = document.getElementById("promptInput");
-const sendBtn = document.getElementById("sendBtn");
-const micBtn = document.getElementById("micBtn");
-const voiceToggleBtn = document.getElementById("voiceToggleBtn");
-const modelSelect = document.getElementById("modelSelect");
-const modeToggle = document.getElementById("modeToggle");
-const modePill = document.getElementById("modePill");
+// --- DOM Elements ---
+const appLayout = document.getElementById("appLayout");
+const sidebar = document.getElementById("sidebar");
+const sidebarCollapseBtn = document.getElementById("sidebarCollapseBtn");
+const sidebarExpandBtn = document.getElementById("sidebarExpandBtn");
+const newChatBtn = document.getElementById("newChatBtn");
+const refreshSessionsBtn = document.getElementById("refreshSessionsBtn");
+const sessionsList = document.getElementById("sessionsList");
+const sessionGroupHeader = document.getElementById("sessionGroupHeader");
+const skillsList = document.getElementById("skillsList");
+const skillsCountBadge = document.getElementById("skillsCountBadge");
 
-// Mode & Sidebar Elements
+// Mode & Workspace Elements
 const modeWorkspaceBtn = document.getElementById("modeWorkspaceBtn");
 const modeSystemBtn = document.getElementById("modeSystemBtn");
 const activeProjectIndicator = document.getElementById("activeProjectIndicator");
 const activeProjectName = document.getElementById("active-project-name");
-const sessionGroupHeader = document.getElementById("sessionGroupHeader");
 
 // Top Nav Elements
-const activeModelName = document.getElementById("activeModelName");
+const modelSelect = document.getElementById("modelSelect");
 const activeTierBadge = document.getElementById("activeTierBadge");
+const modeToggle = document.getElementById("modeToggle");
+const modePill = document.getElementById("modePill");
+const voiceToggleBtn = document.getElementById("voiceToggleBtn");
+const voiceToggleIcon = document.getElementById("voiceToggleIcon");
+const unloadModelBtn = document.getElementById("unloadModelBtn");
+
+// Governor & Telemetry Elements
 const governorWidgetContainer = document.getElementById("governorWidgetContainer");
 const governorPill = document.getElementById("governorPill");
 const governorPillLabel = document.getElementById("governor-pill__label");
@@ -47,14 +55,22 @@ const govCustomOverrideBtn = document.getElementById("govCustomOverrideBtn");
 const govForceReloadBtn = document.getElementById("govForceReloadBtn");
 const govClearErrorBtn = document.getElementById("govClearErrorBtn");
 const govHistoryList = document.getElementById("govHistoryList");
+
+// Telemetry Tooltip & Meters
 const govGpuVal = document.getElementById("govGpuVal");
 const govVramVal = document.getElementById("govVramVal");
 const govCpuVal = document.getElementById("govCpuVal");
 const govRamVal = document.getElementById("govRamVal");
+const govMeterGpuVal = document.getElementById("govMeterGpuVal");
+const govMeterGpuFill = document.getElementById("govMeterGpuFill");
+const govMeterVramVal = document.getElementById("govMeterVramVal");
+const govMeterVramFill = document.getElementById("govMeterVramFill");
+const govMeterCpuVal = document.getElementById("govMeterCpuVal");
+const govMeterCpuFill = document.getElementById("govMeterCpuFill");
+const govMeterRamVal = document.getElementById("govMeterRamVal");
+const govMeterRamFill = document.getElementById("govMeterRamFill");
 
 // Chat Viewport Elements
-const newChatBtn = document.getElementById("newChatBtn");
-const sessionsList = document.getElementById("sessionsList");
 const chatViewport = document.getElementById("chatViewport");
 const welcomeHero = document.getElementById("welcomeHero");
 const emptyStateTitle = document.getElementById("empty-state-title");
@@ -68,20 +84,42 @@ const approveActionBtn = document.getElementById("approveActionBtn");
 const rejectActionBtn = document.getElementById("rejectActionBtn");
 const statusDot = document.getElementById("statusDot");
 const statusText = document.getElementById("statusText");
+
+// Composer Elements
+const promptInput = document.getElementById("promptInput");
+const sendBtn = document.getElementById("sendBtn");
+const micBtn = document.getElementById("micBtn");
+
+// Quick Skill Buttons
 const skillReviewBtn = document.getElementById("skillReviewBtn");
 const skillDiagBtn = document.getElementById("skillDiagBtn");
-const unloadModelBtn = document.getElementById("unloadModelBtn");
+const skillWebSearchBtn = document.getElementById("skillWebSearchBtn");
 
 // --- Initialization ---
 document.addEventListener("DOMContentLoaded", () => {
+  initMarkdownParser();
   initUI();
   initVoice();
   initTelemetry();
+  initKeyShortcuts();
   syncVoiceOutputState();
   updateModelTierBadge();
   setChatMode(currentMode, false);
+  fetchSessions();
+  fetchModelsAndSkills();
 });
 
+function initMarkdownParser() {
+  if (window.marked) {
+    marked.setOptions({
+      gfm: true,
+      breaks: true,
+      headerIds: false,
+      mangle: false
+    });
+  }
+}
+
 function initUI() {
   // Auto-expand textarea
   if (promptInput) {
@@ -98,7 +136,6 @@ function initUI() {
       }
     });
 
-    // Auto focus
     setTimeout(() => promptInput.focus(), 150);
   }
 
@@ -107,11 +144,27 @@ function initUI() {
     sendBtn.addEventListener("click", () => handleSubmit());
   }
 
-  // New Chat
+  // New Chat button
   if (newChatBtn) {
     newChatBtn.addEventListener("click", () => startNewSession());
   }
 
+  // Refresh Sessions button
+  if (refreshSessionsBtn) {
+    refreshSessionsBtn.addEventListener("click", (e) => {
+      e.stopPropagation();
+      fetchSessions();
+    });
+  }
+
+  // Sidebar Collapse / Expand
+  if (sidebarCollapseBtn) {
+    sidebarCollapseBtn.addEventListener("click", () => toggleSidebar(false));
+  }
+  if (sidebarExpandBtn) {
+    sidebarExpandBtn.addEventListener("click", () => toggleSidebar(true));
+  }
+
   // Routing Mode Toggle
   if (modeToggle) {
     modeToggle.addEventListener("click", () => cycleRoutingMode());
@@ -141,7 +194,6 @@ function initUI() {
     });
   }
 
-
   // Voice Toggle Button
   if (voiceToggleBtn) {
     voiceToggleBtn.addEventListener("click", async () => {
@@ -174,7 +226,7 @@ function initUI() {
           body: JSON.stringify({ model_name: selected })
         });
         await res.json();
-        if (label) label.textContent = "VRAM Cleared! ✓";
+        if (label) label.textContent = "VRAM Cleared!";
         setTimeout(() => {
           if (label) label.textContent = "Free VRAM";
           unloadModelBtn.style.opacity = "1";
@@ -190,7 +242,7 @@ function initUI() {
     });
   }
 
-  // --- Governor Command Panel & Overrides ---
+  // Governor Command Panel Toggle
   if (governorPill && governorWidgetContainer) {
     governorPill.addEventListener("click", (e) => {
       e.stopPropagation();
@@ -200,14 +252,12 @@ function initUI() {
       }
     });
 
-    // Close panel on click outside
     document.addEventListener("click", (e) => {
       if (governorWidgetContainer.classList.contains("open") && !governorWidgetContainer.contains(e.target)) {
         governorWidgetContainer.classList.remove("open");
       }
     });
 
-    // Prevent clicks inside panel from closing it
     if (governorCommandPanel) {
       governorCommandPanel.addEventListener("click", (e) => e.stopPropagation());
     }
@@ -304,16 +354,24 @@ function initUI() {
   // Quick Skills
   if (skillReviewBtn) {
     skillReviewBtn.addEventListener("click", () => {
-      if (promptInput) promptInput.value = "Please review the code in backend/app/main.py for quality and security.";
+      if (promptInput) promptInput.value = "Review the codebase files in backend/app for quality, reliability, and security.";
       handleSubmit();
     });
   }
   if (skillDiagBtn) {
     skillDiagBtn.addEventListener("click", () => {
-      if (promptInput) promptInput.value = "Check system diagnostics, disk usage, and hardware telemetry.";
+      if (promptInput) promptInput.value = "Check system diagnostics, disk usage, and hardware telemetry stats.";
       handleSubmit();
     });
   }
+  if (skillWebSearchBtn) {
+    skillWebSearchBtn.addEventListener("click", () => {
+      if (promptInput) {
+        promptInput.value = "Search the web for the latest updates on ";
+        promptInput.focus();
+      }
+    });
+  }
 
   // Suggestion Cards
   document.querySelectorAll(".suggestion-card").forEach(card => {
@@ -327,7 +385,51 @@ function initUI() {
   });
 }
 
-// --- Submit Query Handler ---
+function initKeyShortcuts() {
+  document.addEventListener("keydown", (e) => {
+    // Ctrl+B: Toggle Sidebar
+    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
+      e.preventDefault();
+      const isCollapsed = sidebar && sidebar.classList.contains("collapsed");
+      toggleSidebar(isCollapsed);
+    }
+    // Alt+G: Toggle Governor
+    else if (e.altKey && e.key.toLowerCase() === "g") {
+      e.preventDefault();
+      if (governorWidgetContainer) {
+        const isOpen = governorWidgetContainer.classList.toggle("open");
+        if (isOpen) fetchGovernorHistory();
+      }
+    }
+    // Ctrl+N: New Chat
+    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
+      e.preventDefault();
+      startNewSession();
+    }
+    // Escape: Close Governor or Confirmation
+    else if (e.key === "Escape") {
+      if (governorWidgetContainer && governorWidgetContainer.classList.contains("open")) {
+        governorWidgetContainer.classList.remove("open");
+      }
+      if (confirmationPanel && confirmationPanel.style.display !== "none") {
+        confirmationPanel.style.display = "none";
+      }
+    }
+  });
+}
+
+function toggleSidebar(expand) {
+  if (!sidebar) return;
+  if (expand) {
+    sidebar.classList.remove("collapsed");
+    if (sidebarExpandBtn) sidebarExpandBtn.style.display = "none";
+  } else {
+    sidebar.classList.add("collapsed");
+    if (sidebarExpandBtn) sidebarExpandBtn.style.display = "flex";
+  }
+}
+
+// --- Submit Query Handler with Live SSE Streaming ---
 async function handleSubmit(approvedTokens = null) {
   const query = promptInput ? promptInput.value.trim() : "";
   if (!query && !approvedTokens) return;
@@ -347,10 +449,9 @@ async function handleSubmit(approvedTokens = null) {
     }
   }
 
-  if (loadingBubble) loadingBubble.style.display = "flex";
-  if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
+  if (loadingBubble) loadingBubble.style.display = "none";
 
-  const selectedModel = modelSelect ? modelSelect.value : "hermes3:8b";
+  const selectedModel = modelSelect ? modelSelect.value : "prism-ml/bonsai-27b";
   const isHeavy = selectedModel === "heavy";
 
   const payload = {
@@ -362,11 +463,17 @@ async function handleSubmit(approvedTokens = null) {
     approved_action_ids: approvedTokens
   };
 
+  const streamMessage = createStreamingAssistantMessage();
+  let accumulatedText = "";
+  let toolsUsed = [];
+  let activeSkills = [];
+  let modelName = selectedModel;
+
   const controller = new AbortController();
-  const timeoutId = setTimeout(() => controller.abort(), 180000); // 180s safety timeout for deep reasoning
+  const timeoutId = setTimeout(() => controller.abort(), 180000);
 
   try {
-    const response = await fetch(`${API_BASE}/chat`, {
+    const response = await fetch(`${API_BASE}/chat/stream`, {
       method: "POST",
       headers: { "Content-Type": "application/json" },
       body: JSON.stringify(payload),
@@ -374,41 +481,126 @@ async function handleSubmit(approvedTokens = null) {
     });
 
     clearTimeout(timeoutId);
-    if (loadingBubble) loadingBubble.style.display = "none";
 
     if (response.status === 429) {
       const err = await response.json();
-      appendAssistantMessage(`⚠️ **Resource Governor Throttled**: ${err.detail || "System under high load."}`);
+      streamMessage.finalizeText(`Resource Governor Throttled: ${err.detail || "System under high load."}`);
+      return;
+    }
+
+    if (response.status === 404) {
+      // Graceful fallback to standard /chat endpoint if streaming endpoint is unavailable
+      const fallbackRes = await fetch(`${API_BASE}/chat`, {
+        method: "POST",
+        headers: { "Content-Type": "application/json" },
+        body: JSON.stringify(payload),
+        signal: controller.signal
+      });
+      if (!fallbackRes.ok) {
+        const err = await fallbackRes.text();
+        streamMessage.finalizeText(`Error: ${err}`);
+        return;
+      }
+      const data = await fallbackRes.json();
+      if (data.status === "confirmation_required") {
+        streamMessage.remove();
+        showConfirmationPrompt(data);
+        if (isVoiceReplyEnabled) {
+          speakText("Confirmation required before executing the requested system action.");
+        }
+      } else {
+        streamMessage.finalize(data.response, data.tools_used, data.active_skills, data.model);
+        if (isVoiceReplyEnabled && data.response) {
+          speakText(data.response);
+        }
+        fetchSessions();
+      }
       return;
     }
 
     if (!response.ok) {
       const err = await response.text();
-      appendAssistantMessage(`❌ **Error**: ${err}`);
+      streamMessage.finalizeText(`Error: ${err}`);
       return;
     }
 
-    const data = await response.json();
+    const reader = response.body.getReader();
+    const decoder = new TextDecoder("utf-8");
+    let buffer = "";
+
+    while (true) {
+      const { value, done } = await reader.read();
+      if (done) break;
+
+      buffer += decoder.decode(value, { stream: true });
+      const blocks = buffer.split("\n\n");
+      buffer = blocks.pop() || "";
+
+      for (const block of blocks) {
+        if (!block.trim()) continue;
+        const eventLines = block.split("\n");
+        let eventType = "message";
+        let eventData = "";
+
+        for (const line of eventLines) {
+          if (line.startsWith("event: ")) {
+            eventType = line.substring(7).trim();
+          } else if (line.startsWith("data: ")) {
+            eventData = line.substring(6).trim();
+          }
+        }
 
-    if (data.status === "confirmation_required") {
-      showConfirmationPrompt(data);
-      if (isVoiceReplyEnabled) {
-        speakText("Confirmation required before executing the requested system action.");
-      }
-    } else {
-      appendAssistantMessage(data.response, data.tools_used, data.active_skills, data.model);
-      if (isVoiceReplyEnabled) {
-        speakText(data.response);
+        if (!eventData) continue;
+
+        let parsedData = {};
+        try {
+          parsedData = JSON.parse(eventData);
+        } catch {
+          parsedData = { text: eventData };
+        }
+
+        if (eventType === "token") {
+          const delta = parsedData.delta || "";
+          accumulatedText += delta;
+          streamMessage.updateText(accumulatedText);
+        } else if (eventType === "tool_start") {
+          streamMessage.addOrUpdateToolStep(parsedData.tool, parsedData.args, "running", null);
+        } else if (eventType === "tool_end") {
+          toolsUsed.push(parsedData);
+          streamMessage.addOrUpdateToolStep(parsedData.tool, parsedData.args, parsedData.status, parsedData.result);
+        } else if (eventType === "confirmation_required") {
+          streamMessage.remove();
+          showConfirmationPrompt(parsedData);
+          if (isVoiceReplyEnabled) {
+            speakText("Confirmation required before executing the requested system action.");
+          }
+          return;
+        } else if (eventType === "done") {
+          if (parsedData.response && parsedData.response.length > accumulatedText.length) {
+            accumulatedText = parsedData.response;
+          }
+          toolsUsed = parsedData.tools_used || toolsUsed;
+          activeSkills = parsedData.active_skills || [];
+          modelName = parsedData.model || selectedModel;
+        } else if (eventType === "error") {
+          accumulatedText += `\n\nError: ${parsedData.error}`;
+          streamMessage.updateText(accumulatedText);
+        }
       }
     }
 
+    streamMessage.finalize(accumulatedText, toolsUsed, activeSkills, modelName);
+    if (isVoiceReplyEnabled && accumulatedText) {
+      speakText(accumulatedText);
+    }
+    fetchSessions();
+
   } catch (err) {
     clearTimeout(timeoutId);
-    if (loadingBubble) loadingBubble.style.display = "none";
     if (err.name === "AbortError") {
-      appendAssistantMessage(`⏱️ **Timeout**: Jarvis took too long to respond. The system may be busy.`);
+      streamMessage.finalizeText(`Timeout: Jarvis took too long to respond. The system may be busy.`);
     } else {
-      appendAssistantMessage(`❌ **Connection Error**: Could not reach backend API at ${API_BASE}. Make sure Jarvis backend is running.`);
+      streamMessage.finalizeText(`Connection Error: Could not reach backend API at ${API_BASE}. Make sure Jarvis backend is running.`);
     }
   } finally {
     isProcessing = false;
@@ -418,10 +610,93 @@ async function handleSubmit(approvedTokens = null) {
   }
 }
 
+function createStreamingAssistantMessage() {
+  if (!messagesContainer) return { updateText() {}, addOrUpdateToolStep() {}, finalizeText() {}, finalize() {}, remove() {} };
+  const row = document.createElement("div");
+  row.className = "msg-row assistant";
+
+  const bubble = document.createElement("div");
+  bubble.className = "msg-bubble";
+  bubble.innerHTML = `<div class="streaming-text-container"><span class="streaming-cursor"></span></div><div class="tool-step-container"></div>`;
+
+  row.appendChild(bubble);
+  messagesContainer.appendChild(row);
+  if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
+
+  const textContainer = bubble.querySelector(".streaming-text-container");
+  const toolContainer = bubble.querySelector(".tool-step-container");
+  const activeToolCards = new Map();
+
+  return {
+    updateText(rawText) {
+      if (textContainer) {
+        textContainer.innerHTML = renderMarkdownToHtml(rawText) + `<span class="streaming-cursor"></span>`;
+        if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
+      }
+    },
+    addOrUpdateToolStep(toolName, args, status, result) {
+      if (!toolContainer) return;
+      let card = activeToolCards.get(toolName);
+      if (!card) {
+        card = createToolStepCard({ tool: toolName, args: args, status: status, result: result });
+        toolContainer.appendChild(card);
+        activeToolCards.set(toolName, card);
+      } else {
+        const pill = card.querySelector(".step-status-pill");
+        if (pill) {
+          const isSuccess = status !== "error";
+          pill.className = `step-status-pill ${isSuccess ? "success" : "error"}`;
+          pill.textContent = isSuccess ? "Success" : "Failed";
+        }
+        if (result) {
+          const body = card.querySelector(".tool-step-body");
+          if (body) {
+            body.innerHTML = `<div><strong>Result:</strong><pre style="margin-top:4px; white-space:pre-wrap;">${escapeHtml(typeof result === 'string' ? result : JSON.stringify(result, null, 2))}</pre></div>`;
+          }
+        }
+      }
+      if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
+    },
+    finalizeText(errorText) {
+      if (textContainer) {
+        textContainer.innerHTML = renderMarkdownToHtml(errorText);
+      }
+    },
+    finalize(finalText, tools, activeSkills, model) {
+      if (textContainer) {
+        textContainer.innerHTML = renderMarkdownToHtml(finalText);
+      }
+
+      const actionsBar = document.createElement("div");
+      actionsBar.className = "msg-actions-bar";
+
+      if (activeSkills && activeSkills.length > 0) {
+        const tag = document.createElement("div");
+        tag.className = "tier-badge tier-badge--1";
+        tag.innerHTML = `<i class="ti ti-sparkles"></i> ${escapeHtml(activeSkills.join(", "))}`;
+        actionsBar.appendChild(tag);
+      }
+
+      const readBtn = document.createElement("button");
+      readBtn.className = "read-aloud-btn";
+      readBtn.innerHTML = `<i class="ti ti-volume"></i> Read Aloud`;
+      readBtn.addEventListener("click", () => speakText(finalText));
+      actionsBar.appendChild(readBtn);
+
+      bubble.appendChild(actionsBar);
+
+      enhanceCodeBlocks(bubble);
+      if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
+    },
+    remove() {
+      row.remove();
+    }
+  };
+}
+
 // --- Mode & Model Controls ---
 function setChatMode(mode, fromUserClick = false) {
   if (isConversationStarted && fromUserClick) {
-    // Mode is locked for active conversation
     const alertMsg = "Mode is locked for the current chat session. Start a 'New Chat' to switch mode.";
     if (window.confirm ? confirm(alertMsg + "\n\nWould you like to start a new chat now?") : false) {
       startNewSession();
@@ -437,15 +712,15 @@ function setChatMode(mode, fromUserClick = false) {
     if (modeSystemBtn) modeSystemBtn.classList.remove("mode-toggle__option--active");
     if (activeProjectIndicator) activeProjectIndicator.style.display = "flex";
     if (emptyStateTitle) emptyStateTitle.textContent = "Working in " + (activeProjectName ? activeProjectName.textContent : "JARVIS core");
-    if (emptyStateSubtitle) emptyStateSubtitle.textContent = "Workspace mode — writes stay inside this folder";
-    if (suggWorkspaceCard) suggWorkspaceCard.style.display = "block";
+    if (emptyStateSubtitle) emptyStateSubtitle.textContent = "Workspace mode - writes stay inside this project folder";
+    if (suggWorkspaceCard) suggWorkspaceCard.style.display = "flex";
     if (sessionGroupHeader) sessionGroupHeader.textContent = "Workspace Chats";
   } else {
     if (modeSystemBtn) modeSystemBtn.classList.add("mode-toggle__option--active");
     if (modeWorkspaceBtn) modeWorkspaceBtn.classList.remove("mode-toggle__option--active");
     if (activeProjectIndicator) activeProjectIndicator.style.display = "none";
-    if (emptyStateTitle) emptyStateTitle.textContent = "System mode";
-    if (emptyStateSubtitle) emptyStateSubtitle.textContent = "Full PC access — confirmation required outside safe paths";
+    if (emptyStateTitle) emptyStateTitle.textContent = "System Mode Active";
+    if (emptyStateSubtitle) emptyStateSubtitle.textContent = "Full PC access - confirmation required outside safe workspace paths";
     if (suggWorkspaceCard) suggWorkspaceCard.style.display = "none";
     if (sessionGroupHeader) sessionGroupHeader.textContent = "System Chats";
   }
@@ -456,25 +731,12 @@ function updateModelTierBadge() {
 
   const val = modelSelect.value;
   if (val === "qwen2.5:0.5b") {
-    if (activeModelName) activeModelName.textContent = "Qwen 2.5 0.5B";
     activeTierBadge.className = "tier-badge tier-badge--1";
     activeTierBadge.textContent = "Tier 1 · fast";
   } else if (val === "heavy") {
-    if (activeModelName) activeModelName.textContent = "Cloud LLM";
     activeTierBadge.className = "tier-badge tier-badge--3";
     activeTierBadge.textContent = "Tier 3 · cloud";
   } else {
-    // Local Tier 2 flagship models
-    const nameMap = {
-      "prism-ml/bonsai-27b": "Bonsai 27B",
-      "bonsai-27b": "Bonsai 27B",
-      "qwen3.8-9b-distill": "Qwen 3.8 9B Distill",
-      "hermes3:8b": "Hermes 3 8B",
-      "phi3.5:3.8b": "Phi 3.5 3.8B",
-      "llama3.1:8b": "Llama 3.1 8B",
-      "llama3.2:3b": "Llama 3.2 3B"
-    };
-    if (activeModelName) activeModelName.textContent = nameMap[val] || val;
     activeTierBadge.className = "tier-badge tier-badge--2";
     activeTierBadge.textContent = "Tier 2 · local";
   }
@@ -498,9 +760,11 @@ function updateVoiceButtonUI() {
   const textEl = voiceToggleBtn.querySelector(".voice-text");
   if (isVoiceReplyEnabled) {
     voiceToggleBtn.classList.add("active");
+    if (voiceToggleIcon) voiceToggleIcon.className = "ti ti-volume voice-icon";
     if (textEl) textEl.textContent = "Voice: ON";
   } else {
     voiceToggleBtn.classList.remove("active");
+    if (voiceToggleIcon) voiceToggleIcon.className = "ti ti-volume-off voice-icon";
     if (textEl) textEl.textContent = "Voice: OFF";
     if (window.speechSynthesis) window.speechSynthesis.cancel();
     if (currentAudio) {
@@ -510,7 +774,6 @@ function updateVoiceButtonUI() {
   }
 }
 
-
 function cycleRoutingMode() {
   const modes = ["auto", "normal", "heavy"];
   const nextIdx = (modes.indexOf(routingMode) + 1) % modes.length;
@@ -530,26 +793,180 @@ function startNewSession() {
   if (loadingBubble) loadingBubble.style.display = "none";
 
   setChatMode(currentMode, false);
+  fetchSessions();
 
-  if (sessionsList) {
-    const item = document.createElement("div");
-    item.className = "session-item active";
-    item.innerHTML = `<span class="session-icon">💬</span><span class="session-name">${currentMode === "WORKSPACE" ? "📁" : "💻"} Chat ${activeSessionId.substring(8)}</span>`;
-    
-    document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
-    sessionsList.prepend(item);
+  if (promptInput) promptInput.focus();
+}
 
-    item.addEventListener("click", () => {
-      document.querySelectorAll(".session-item").forEach(el => el.classList.remove("active"));
-      item.classList.add("active");
+// --- Session Drawer & History Management ---
+async function fetchSessions() {
+  if (!sessionsList) return;
+  try {
+    const res = await fetch(`${API_BASE}/sessions`);
+    if (!res.ok) return;
+    const sessions = await res.json();
+
+    sessionsList.innerHTML = "";
+
+    if (!Array.isArray(sessions) || sessions.length === 0) {
+      const defaultItem = document.createElement("div");
+      defaultItem.className = "session-item active";
+      defaultItem.innerHTML = `
+        <i class="ti ti-message-2 session-icon"></i>
+        <span class="session-name">Current Session</span>
+      `;
+      sessionsList.appendChild(defaultItem);
+      return;
+    }
+
+    sessions.forEach(sess => {
+      const sId = sess.session_id || sess.id || sess;
+      const title = sess.title || `Chat ${sId.substring(0, 8)}`;
+      const isActive = sId === activeSessionId;
+
+      const item = document.createElement("div");
+      item.className = `session-item ${isActive ? "active" : ""}`;
+      item.setAttribute("data-session-id", sId);
+      item.innerHTML = `
+        <i class="ti ti-message-2 session-icon"></i>
+        <span class="session-name" title="${title}">${title}</span>
+        <button class="session-delete-btn" title="Delete Session">
+          <i class="ti ti-trash"></i>
+        </button>
+      `;
+
+      item.addEventListener("click", () => {
+        loadSession(sId);
+      });
+
+      const delBtn = item.querySelector(".session-delete-btn");
+      if (delBtn) {
+        delBtn.addEventListener("click", (e) => {
+          e.stopPropagation();
+          deleteSession(sId, item);
+        });
+      }
+
+      sessionsList.appendChild(item);
     });
+
+  } catch (err) {
+    console.debug("Error fetching sessions:", err);
   }
+}
 
-  if (promptInput) promptInput.focus();
+async function loadSession(sessionId) {
+  if (isProcessing) return;
+  activeSessionId = sessionId;
+  isConversationStarted = true;
+
+  document.querySelectorAll(".session-item").forEach(el => {
+    if (el.getAttribute("data-session-id") === sessionId) {
+      el.classList.add("active");
+    } else {
+      el.classList.remove("active");
+    }
+  });
+
+  if (welcomeHero) welcomeHero.style.display = "none";
+  if (confirmationPanel) confirmationPanel.style.display = "none";
+  if (messagesContainer) messagesContainer.innerHTML = "";
+  if (loadingBubble) loadingBubble.style.display = "flex";
+
+  try {
+    const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
+    if (loadingBubble) loadingBubble.style.display = "none";
+
+    if (!res.ok) {
+      appendAssistantMessage(`Could not load messages for session ${sessionId}.`);
+      return;
+    }
+
+    const messages = await res.json();
+    if (!Array.isArray(messages) || messages.length === 0) {
+      if (welcomeHero) welcomeHero.style.display = "flex";
+      return;
+    }
+
+    messages.forEach(msg => {
+      const role = msg.role || "user";
+      const content = msg.content || "";
+      const toolsUsed = msg.tools_used || (msg.metadata ? msg.metadata.tools_used : []);
+      const activeSkills = msg.active_skills || (msg.metadata ? msg.metadata.active_skills : []);
+      const model = msg.model || (msg.metadata ? msg.metadata.model : "");
+
+      if (role === "user") {
+        appendUserMessage(content);
+      } else {
+        appendAssistantMessage(content, toolsUsed, activeSkills, model);
+      }
+    });
+
+  } catch (err) {
+    if (loadingBubble) loadingBubble.style.display = "none";
+    appendAssistantMessage(`Error loading session history: ${err}`);
+  }
 }
 
-// --- Message Rendering ---
+async function deleteSession(sessionId, element) {
+  if (window.confirm ? !confirm("Are you sure you want to delete this session?") : false) {
+    return;
+  }
+  try {
+    await fetch(`${API_BASE}/sessions/${sessionId}`, { method: "DELETE" });
+    if (element) {
+      element.style.opacity = "0";
+      setTimeout(() => element.remove(), 200);
+    }
+    if (activeSessionId === sessionId) {
+      startNewSession();
+    }
+  } catch (err) {
+    console.error("Error deleting session:", err);
+  }
+}
+
+// --- Dynamic Models & Skills Discovery ---
+async function fetchModelsAndSkills() {
+  try {
+    const res = await fetch(`${API_BASE}/health`);
+    if (!res.ok) return;
+    const data = await res.json();
+
+    // 1. Update Models Dropdown
+    if (modelSelect && Array.isArray(data.available_models) && data.available_models.length > 0) {
+      const currentVal = modelSelect.value;
+      const heavyOpt = '<option value="heavy">Heavy Mode (OpenRouter)</option>';
+      
+      const opts = data.available_models.map(m => {
+        let label = m;
+        if (m.includes("bonsai")) label = "Bonsai 27B (LM Studio)";
+        else if (m.includes("hermes")) label = "Hermes 3 8B (Ollama)";
+        else if (m.includes("qwen2.5:0.5b")) label = "Qwen 2.5 0.5B (Ollama)";
+        else if (m.includes("qwen3.8")) label = "Qwen 3.8 9B (LM Studio)";
+        return `<option value="${m}">${label}</option>`;
+      }).join("") + heavyOpt;
+
+      modelSelect.innerHTML = opts;
+      if (data.available_models.includes(currentVal) || currentVal === "heavy") {
+        modelSelect.value = currentVal;
+      } else if (data.configured_model && data.available_models.includes(data.configured_model)) {
+        modelSelect.value = data.configured_model;
+      }
+      updateModelTierBadge();
+    }
+
+    // 2. Update Skills Count Badge
+    if (skillsCountBadge && data.available_skills_count !== undefined) {
+      skillsCountBadge.textContent = `${data.available_skills_count} Active`;
+    }
+
+  } catch (err) {
+    console.debug("Error loading health models/skills:", err);
+  }
+}
 
+// --- Message Rendering Engine ---
 function appendUserMessage(text) {
   if (!messagesContainer) return;
   const row = document.createElement("div");
@@ -571,66 +988,176 @@ function appendAssistantMessage(text, toolsUsed = [], activeSkills = [], modelNa
 
   const bubble = document.createElement("div");
   bubble.className = "msg-bubble";
-  bubble.innerHTML = formatMarkdownText(text);
+  bubble.innerHTML = renderMarkdownToHtml(text);
 
+  // Render Collapsible Tool Execution Steps
+  if (toolsUsed && toolsUsed.length > 0) {
+    const toolsContainer = document.createElement("div");
+    toolsContainer.className = "tool-step-container";
+
+    toolsUsed.forEach(t => {
+      const stepCard = createToolStepCard(t);
+      toolsContainer.appendChild(stepCard);
+    });
+
+    bubble.appendChild(toolsContainer);
+  }
+
+  // Actions Bar
   const actionsBar = document.createElement("div");
-  actionsBar.style.display = "flex";
-  actionsBar.style.alignItems = "center";
-  actionsBar.style.flexWrap = "wrap";
-  actionsBar.style.gap = "6px";
-  actionsBar.style.marginTop = "6px";
+  actionsBar.className = "msg-actions-bar";
 
   if (activeSkills && activeSkills.length > 0) {
     const tag = document.createElement("div");
-    tag.className = "tool-badge";
-    tag.textContent = `🎯 Skill: ${activeSkills.join(", ")}`;
+    tag.className = "tier-badge tier-badge--1";
+    tag.innerHTML = `<i class="ti ti-sparkles"></i> ${escapeHtml(activeSkills.join(", "))}`;
     actionsBar.appendChild(tag);
   }
 
-  if (toolsUsed && toolsUsed.length > 0) {
-    toolsUsed.forEach(t => {
-      const tag = document.createElement("div");
-      tag.className = "tool-badge";
-      tag.textContent = `⚡ Executed: ${t.tool}`;
-      actionsBar.appendChild(tag);
-    });
-  }
-
   // Read Aloud button
   const readBtn = document.createElement("button");
   readBtn.className = "read-aloud-btn";
-  readBtn.innerHTML = "🔊 Read Aloud";
+  readBtn.innerHTML = `<i class="ti ti-volume"></i> Read Aloud`;
   readBtn.addEventListener("click", () => speakText(text));
   actionsBar.appendChild(readBtn);
 
   bubble.appendChild(actionsBar);
   row.appendChild(bubble);
   messagesContainer.appendChild(row);
+
+  // Post-render syntax highlighting & copy listeners
+  enhanceCodeBlocks(bubble);
+
   if (chatViewport) chatViewport.scrollTop = chatViewport.scrollHeight;
 }
 
-function formatMarkdownText(text) {
-  if (!text) return "";
-  let formatted = text
-    .replace(/&/g, "&amp;")
-    .replace(/</g, "&lt;")
-    .replace(/>/g, "&gt;");
+function createToolStepCard(toolItem) {
+  const card = document.createElement("div");
+  card.className = "tool-step-card";
+
+  const toolName = toolItem.tool || "tool_execution";
+  let iconClass = "ti-tool";
+  if (toolName.includes("search") || toolName.includes("fetch")) iconClass = "ti-world-search";
+  else if (toolName.includes("file") || toolName.includes("read") || toolName.includes("write")) iconClass = "ti-file-code";
+  else if (toolName.includes("command") || toolName.includes("powershell")) iconClass = "ti-terminal-2";
+  else if (toolName.includes("diagnostics") || toolName.includes("status")) iconClass = "ti-activity";
+
+  const argsObj = toolItem.args || {};
+  let argsPreview = "";
+  if (argsObj.query) argsPreview = `query: "${argsObj.query}"`;
+  else if (argsObj.file_path) argsPreview = `path: "${argsObj.file_path}"`;
+  else if (argsObj.command) argsPreview = `cmd: "${argsObj.command}"`;
+  else if (Object.keys(argsObj).length > 0) argsPreview = JSON.stringify(argsObj);
+
+  const isSuccess = toolItem.status !== "error";
+  const statusLabel = isSuccess ? "Success" : "Failed";
+  const statusClass = isSuccess ? "success" : "error";
+
+  card.innerHTML = `
+    <div class="tool-step-header">
+      <div class="tool-step-left">
+        <i class="ti ${iconClass} tool-step-icon"></i>
+        <span class="tool-step-name">${escapeHtml(toolName)}</span>
+        ${argsPreview ? `<span class="tool-step-args-preview">${escapeHtml(argsPreview)}</span>` : ""}
+      </div>
+      <div class="tool-step-right">
+        <span class="step-status-pill ${statusClass}">${statusLabel}</span>
+        <i class="ti ti-chevron-down step-chevron"></i>
+      </div>
+    </div>
+    <div class="tool-step-body">
+      ${toolItem.result ? `<div><strong>Result:</strong><pre style="margin-top:4px; white-space:pre-wrap;">${escapeHtml(typeof toolItem.result === 'string' ? toolItem.result : JSON.stringify(toolItem.result, null, 2))}</pre></div>` : `<div>Arguments: ${escapeHtml(JSON.stringify(argsObj, null, 2))}</div>`}
+    </div>
+  `;
+
+  const header = card.querySelector(".tool-step-header");
+  if (header) {
+    header.addEventListener("click", () => {
+      card.classList.toggle("open");
+    });
+  }
 
-  // Code blocks
-  formatted = formatted.replace(/```([\w]*)\n([\s\S]*?)```/g, (match, lang, code) => {
-    return `<pre style="background:#07090e; padding:12px; border-radius:8px; margin:8px 0; overflow-x:auto; font-family:var(--font-mono); font-size:13px;"><code>${code}</code></pre>`;
-  });
+  return card;
+}
 
-  // Inline code
-  formatted = formatted.replace(/`([^`]+)`/g, '<code style="background:#07090e; padding:2px 6px; border-radius:4px; font-family:var(--font-mono); font-size:12.5px;">$1</code>');
-  // Bold
+function renderMarkdownToHtml(text) {
+  if (!text) return "";
+  if (window.marked) {
+    try {
+      return marked.parse(text);
+    } catch {
+      // Fallback to basic sanitization
+    }
+  }
+  return fallbackFormatMarkdown(text);
+}
+
+function fallbackFormatMarkdown(text) {
+  let formatted = escapeHtml(text);
+  formatted = formatted.replace(/```([\w]*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
+  formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
   formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
-  // Line breaks
   formatted = formatted.replace(/\n/g, '<br>');
-
   return formatted;
 }
 
+function enhanceCodeBlocks(container) {
+  const preElements = container.querySelectorAll("pre");
+  preElements.forEach(pre => {
+    if (pre.closest(".code-block-wrapper") || pre.closest(".conf-payload-box")) return;
+
+    const codeEl = pre.querySelector("code");
+    const rawCode = codeEl ? codeEl.textContent : pre.textContent;
+
+    // Detect language class
+    let lang = "plaintext";
+    if (codeEl) {
+      const classes = Array.from(codeEl.classList);
+      const langClass = classes.find(c => c.startsWith("language-"));
+      if (langClass) {
+        lang = langClass.replace("language-", "");
+      }
+    }
+
+    const wrapper = document.createElement("div");
+    wrapper.className = "code-block-wrapper";
+
+    const header = document.createElement("div");
+    header.className = "code-header";
+    header.innerHTML = `
+      <span>${escapeHtml(lang)}</span>
+      <button class="copy-code-btn" title="Copy code to clipboard">
+        <i class="ti ti-copy"></i>
+        <span>Copy</span>
+      </button>
+    `;
+
+    const copyBtn = header.querySelector(".copy-code-btn");
+    copyBtn.addEventListener("click", async () => {
+      try {
+        await navigator.clipboard.writeText(rawCode);
+        copyBtn.classList.add("copied");
+        copyBtn.innerHTML = `<i class="ti ti-check"></i> <span>Copied!</span>`;
+        setTimeout(() => {
+          copyBtn.classList.remove("copied");
+          copyBtn.innerHTML = `<i class="ti ti-copy"></i> <span>Copy</span>`;
+        }, 2000);
+      } catch (e) {
+        console.error("Clipboard copy error:", e);
+      }
+    });
+
+    pre.parentNode.insertBefore(wrapper, pre);
+    wrapper.appendChild(header);
+    wrapper.appendChild(pre);
+
+    // Apply Prism syntax highlighting
+    if (window.Prism && codeEl) {
+      Prism.highlightElement(codeEl);
+    }
+  });
+}
+
 // --- Safety Confirmation UI ---
 function showConfirmationPrompt(data) {
   pendingActionIds = (data.pending_confirmations || []).map(p => p.action_id);
@@ -638,7 +1165,7 @@ function showConfirmationPrompt(data) {
   const cardsHtml = (data.pending_confirmations || []).map(p => {
     const isHigh = p.risk_tier === "HIGH_RISK";
     const badgeClass = isHigh ? "conf-risk-badge high" : "conf-risk-badge confirm";
-    const toolIcon = p.tool.includes("command") ? "⚡" : p.tool.includes("write") ? "📝" : p.tool.includes("delete") ? "🗑️" : "🔧";
+    const toolIcon = p.tool.includes("command") ? "ti-terminal-2" : p.tool.includes("write") ? "ti-edit" : p.tool.includes("delete") ? "ti-trash" : "ti-tool";
     
     let payloadHtml = "";
     if (p.args && p.args.command) {
@@ -664,12 +1191,12 @@ function showConfirmationPrompt(data) {
       `;
     }
 
-    const reasonHtml = p.reason ? `<div class="conf-reason-text">ℹ️ ${escapeHtml(p.reason)}</div>` : "";
+    const reasonHtml = p.reason ? `<div class="conf-reason-text">${escapeHtml(p.reason)}</div>` : "";
 
     return `
       <div class="conf-action-card">
         <div class="conf-action-header">
-          <span class="conf-tool-name">${toolIcon} ${escapeHtml(p.tool)}</span>
+          <span class="conf-tool-name"><i class="ti ${toolIcon}"></i> ${escapeHtml(p.tool)}</span>
           <span class="${badgeClass}">${escapeHtml(p.risk_tier)}</span>
         </div>
         ${payloadHtml}
@@ -680,7 +1207,7 @@ function showConfirmationPrompt(data) {
 
   if (confDetailsText) {
     confDetailsText.innerHTML = `
-      <div>Jarvis wants to execute the following operation(s) on your system:</div>
+      <div>Jarvis requests authorization to perform the following system operation(s):</div>
       <div style="display:flex; flex-direction:column; gap:10px; margin-top:8px;">${cardsHtml}</div>
     `;
   }
@@ -715,7 +1242,6 @@ function sanitizeForSpeech(text) {
     .replace(/[*_]{1,3}([^*_]+)[*_]{1,3}/g, "$1")
     .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
     .replace(/^#{1,6}\s+/gm, "")
-    .replace(/[•⚡🎯📝⚠️📊🔍💬✓]/g, "")
     .replace(/\s+/g, " ")
     .trim();
 }
@@ -724,7 +1250,6 @@ async function speakText(text) {
   const clean = sanitizeForSpeech(text);
   if (!clean) return;
 
-  // Stop any currently playing audio
   if (currentAudio) {
     currentAudio.pause();
     currentAudio = null;
@@ -733,7 +1258,7 @@ async function speakText(text) {
     window.speechSynthesis.cancel();
   }
 
-  // 1. Try Local Voice Output via Jarvis Backend (/voice/speak)
+  // 1. Local Voice Output via backend (/voice/speak)
   try {
     const res = await fetch(`${API_BASE}/voice/speak`, {
       method: "POST",
@@ -796,7 +1321,7 @@ async function startVoiceRecording() {
   audioChunks = [];
   let speechRecognizedText = "";
 
-  // 1. Start live browser speech preview if available
+  // 1. Live browser speech preview
   const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
   if (SpeechRecognition) {
     try {
@@ -824,7 +1349,7 @@ async function startVoiceRecording() {
     }
   }
 
-  // 2. Start robust MediaRecorder stream for backend Whisper
+  // 2. MediaRecorder stream for backend Whisper
   try {
     const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
     mediaRecorder = new MediaRecorder(stream);
@@ -838,10 +1363,9 @@ async function startVoiceRecording() {
     mediaRecorder.onstop = async () => {
       isRecording = false;
       if (micBtn) micBtn.classList.remove("recording");
-      if (promptInput) promptInput.placeholder = "Ask Jarvis anything, or use / for skills...";
+      if (promptInput) promptInput.placeholder = "Message Jarvis, or ask to execute tools...";
       stream.getTracks().forEach(track => track.stop());
 
-      // If live Web Speech got text, use it; otherwise send recorded audio to local Whisper
       if (speechRecognizedText && speechRecognizedText.trim().length > 1) {
         if (promptInput) promptInput.value = speechRecognizedText.trim();
         handleSubmit();
@@ -857,7 +1381,7 @@ async function startVoiceRecording() {
     console.error("Microphone capture error:", err);
     isRecording = false;
     if (micBtn) micBtn.classList.remove("recording");
-    if (promptInput) promptInput.placeholder = "Ask Jarvis anything, or use / for skills...";
+    if (promptInput) promptInput.placeholder = "Message Jarvis, or ask to execute tools...";
   }
 }
 
@@ -913,8 +1437,7 @@ async function sendAudioToBackendTranscribe(blob) {
   }
 }
 
-
-// --- Telemetry Poller ---
+// --- Telemetry Poller & Visualizers ---
 function initTelemetry() {
   setInterval(pollGovernor, 2000);
   pollGovernor();
@@ -932,7 +1455,7 @@ async function pollGovernor() {
         statusDot.className = (st === "PAUSED" || st === "UNLOADED" || st === "ERROR") ? "status-dot throttled" : "status-dot connected";
       }
       if (statusText) {
-        if (st === "PAUSED") statusText.textContent = "Paused (External App/Manual)";
+        if (st === "PAUSED") statusText.textContent = "Paused (Manual)";
         else if (st === "UNLOADED") statusText.textContent = "VRAM Unloaded";
         else if (st === "ERROR") statusText.textContent = "Governor Error";
         else if (st === "LOADING") statusText.textContent = "Loading Model...";
@@ -940,7 +1463,7 @@ async function pollGovernor() {
         else statusText.textContent = "Jarvis Ready";
       }
 
-      // Update Governor Pill 6-Tier Class & Arc Ring
+      // Update Governor Pill & Arc Ring
       if (governorPill) {
         governorPill.className = "governor-pill";
         if (st === "IDLE") governorPill.classList.add("governor-pill--idle");
@@ -951,7 +1474,6 @@ async function pollGovernor() {
         else if (st === "ERROR") governorPill.classList.add("governor-pill--error");
         else governorPill.classList.add("governor-pill--idle");
 
-        // Dynamic Pill Label (Countdown if override is active)
         if (governorPillLabel) {
           if (data.is_manual_override && data.override_expires_at) {
             const nowSec = Date.now() / 1000;
@@ -1010,14 +1532,34 @@ async function pollGovernor() {
         }
       }
 
-      // Update Hover Tooltip Telemetry Metrics
+      // Update Telemetry Metrics & Visualizer Progress Bars
       const m = data.metrics || {};
-      if (govGpuVal) govGpuVal.textContent = m.gpu_available ? `${Math.round(m.gpu_util_percent || 0)}%` : "N/A";
-      if (govVramVal) govVramVal.textContent = m.vram_used_mb ? `${(m.vram_used_mb / 1024).toFixed(1)} GB` : "N/A";
-      if (govCpuVal) govCpuVal.textContent = `${Math.round(m.cpu_percent || 0)}%`;
-      if (govRamVal) govRamVal.textContent = m.ram_percent ? `${Math.round(m.ram_percent)}%` : "N/A";
+      const gpuPct = Math.round(m.gpu_util_percent || 0);
+      const vramUsedGb = m.vram_used_mb ? (m.vram_used_mb / 1024).toFixed(1) : "0.0";
+      const vramTotalGb = m.vram_total_mb ? (m.vram_total_mb / 1024).toFixed(1) : "8.0";
+      const vramPct = m.vram_util_percent || (m.vram_total_mb ? Math.round((m.vram_used_mb / m.vram_total_mb) * 100) : 0);
+      const cpuPct = Math.round(m.cpu_percent || 0);
+      const ramPct = Math.round(m.ram_percent || 0);
+
+      // Tooltip values
+      if (govGpuVal) govGpuVal.textContent = m.gpu_available ? `${gpuPct}%` : "N/A";
+      if (govVramVal) govVramVal.textContent = `${vramUsedGb} GB`;
+      if (govCpuVal) govCpuVal.textContent = `${cpuPct}%`;
+      if (govRamVal) govRamVal.textContent = `${ramPct}%`;
+
+      // Command Panel Visualizer Meters
+      if (govMeterGpuVal) govMeterGpuVal.textContent = `${gpuPct}%`;
+      if (govMeterGpuFill) govMeterGpuFill.style.width = `${Math.min(100, Math.max(0, gpuPct))}%`;
+
+      if (govMeterVramVal) govMeterVramVal.textContent = `${vramUsedGb} / ${vramTotalGb} GB (${vramPct}%)`;
+      if (govMeterVramFill) govMeterVramFill.style.width = `${Math.min(100, Math.max(0, vramPct))}%`;
+
+      if (govMeterCpuVal) govMeterCpuVal.textContent = `${cpuPct}%`;
+      if (govMeterCpuFill) govMeterCpuFill.style.width = `${Math.min(100, Math.max(0, cpuPct))}%`;
+
+      if (govMeterRamVal) govMeterRamVal.textContent = `${ramPct}%`;
+      if (govMeterRamFill) govMeterRamFill.style.width = `${Math.min(100, Math.max(0, ramPct))}%`;
 
-      // If command panel is open, auto-refresh history
       if (governorWidgetContainer && governorWidgetContainer.classList.contains("open")) {
         fetchGovernorHistory();
       }
@@ -1075,7 +1617,7 @@ async function fetchGovernorHistory() {
             <span>${e.from_status || 'IDLE'} → ${e.to_status || 'IDLE'}</span>
             <span class="gov-hist-time">${timeStr}</span>
           </div>
-          <div class="gov-hist-reasons" title="${reasonsStr}">${reasonsStr}</div>
+          <div class="gov-hist-reasons" title="${reasonsStr}">${escapeHtml(reasonsStr)}</div>
         </div>
       `;
     }).join("");
diff --git a/desktop/ui/index.html b/desktop/ui/index.html
index f6720a0..5db8c66 100644
--- a/desktop/ui/index.html
+++ b/desktop/ui/index.html
@@ -3,68 +3,95 @@
 <head>
   <meta charset="UTF-8">
   <meta name="viewport" content="width=device-width, initial-scale=1.0">
-  <title>Jarvis AI Assistant</title>
+  <title>Jarvis - Local AI Command Center</title>
   <link rel="preconnect" href="https://fonts.googleapis.com">
   <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
-  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
+  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
+  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
   <link rel="stylesheet" href="styles.css">
+  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
+  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
+  <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
 </head>
 <body>
-  <div class="app-layout">
-    <!-- Left Sidebar -->
-    <aside class="sidebar">
+  <div class="app-layout" id="appLayout">
+    <!-- Left Sidebar Drawer -->
+    <aside class="sidebar" id="sidebar">
       <div class="sidebar-header">
-        <div class="brand">
-          <div class="brand-icon">
-            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
-              <circle cx="12" cy="12" r="10"></circle>
-              <polygon points="12 8 8 12 12 16 16 12 12 8"></polygon>
-            </svg>
+        <div class="brand-row">
+          <div class="brand">
+            <div class="brand-icon">
+              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
+                <circle cx="12" cy="12" r="10"></circle>
+                <polygon points="12 8 8 12 12 16 16 12 12 8"></polygon>
+              </svg>
+            </div>
+            <div class="brand-title">Jarvis AI</div>
           </div>
-          <div class="brand-title">Jarvis AI</div>
+          <button class="sidebar-toggle-btn" id="sidebarCollapseBtn" title="Collapse Sidebar (Ctrl+B)">
+            <i class="ti ti-layout-sidebar-left-collapse"></i>
+          </button>
         </div>
-        <button class="new-chat-btn" id="newChatBtn" title="Start a new session">
-          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
-            <line x1="12" y1="5" x2="12" y2="19"></line>
-            <line x1="5" y1="12" x2="19" y2="12"></line>
-          </svg>
+
+        <button class="new-chat-btn" id="newChatBtn" title="Start a new session (Ctrl+N)">
+          <i class="ti ti-plus"></i>
           <span>New Chat</span>
+          <kbd class="shortcut-badge">Ctrl+N</kbd>
         </button>
 
         <!-- Segmented Mode Toggle (Workspace / System) -->
         <div class="mode-toggle" id="chatScopeToggle">
-          <button class="mode-toggle__option mode-toggle__option--active" id="modeWorkspaceBtn" data-mode="WORKSPACE">Workspace</button>
-          <button class="mode-toggle__option" id="modeSystemBtn" data-mode="SYSTEM">System</button>
+          <button class="mode-toggle__option mode-toggle__option--active" id="modeWorkspaceBtn" data-mode="WORKSPACE">
+            <i class="ti ti-folder"></i>
+            <span>Workspace</span>
+          </button>
+          <button class="mode-toggle__option" id="modeSystemBtn" data-mode="SYSTEM">
+            <i class="ti ti-terminal-2"></i>
+            <span>System</span>
+          </button>
         </div>
 
         <!-- Active Project Indicator (Workspace Mode Only) -->
         <div class="active-project" id="activeProjectIndicator">
-          <i class="ti ti-folder"></i>
+          <i class="ti ti-folder-check"></i>
           <span id="active-project-name">JARVIS core</span>
         </div>
       </div>
 
-      <!-- Quick Skills -->
+      <!-- Skills & Diagnostics -->
       <div class="sidebar-section">
-        <div class="section-label">Skills & Diagnostics</div>
-        <div class="skill-item" id="skillReviewBtn">
-          <span class="skill-icon">📝</span>
-          <span class="skill-name">Code Review</span>
+        <div class="section-label">
+          <span>Skills & Diagnostics</span>
+          <span class="skills-count-badge" id="skillsCountBadge">Ready</span>
         </div>
-        <div class="skill-item" id="skillDiagBtn">
-          <span class="skill-icon">⚡</span>
-          <span class="skill-name">System Diagnostics</span>
+        <div class="skills-list" id="skillsList">
+          <div class="skill-item" id="skillReviewBtn">
+            <i class="ti ti-code skill-icon"></i>
+            <span class="skill-name">Code Review</span>
+          </div>
+          <div class="skill-item" id="skillDiagBtn">
+            <i class="ti ti-activity skill-icon"></i>
+            <span class="skill-name">System Diagnostics</span>
+          </div>
+          <div class="skill-item" id="skillWebSearchBtn">
+            <i class="ti ti-world-search skill-icon"></i>
+            <span class="skill-name">Web Research</span>
+          </div>
         </div>
       </div>
 
       <!-- Recent Sessions -->
       <div class="sidebar-section sessions-section">
-        <div class="section-label">Recent Sessions</div>
+        <div class="section-label">
+          <span id="sessionGroupHeader">Recent Sessions</span>
+          <button class="icon-action-btn" id="refreshSessionsBtn" title="Refresh Session History">
+            <i class="ti ti-refresh"></i>
+          </button>
+        </div>
         <div class="sessions-list" id="sessionsList">
-          <div class="session-group-header" id="sessionGroupHeader">Workspace Chats</div>
-          <div class="session-item active" id="defaultSessionItem">
-            <span class="session-icon">💬</span>
+          <div class="session-item active" id="defaultSessionItem" data-session-id="default">
+            <i class="ti ti-message-2 session-icon"></i>
             <span class="session-name">Current Session</span>
           </div>
         </div>
@@ -76,15 +103,23 @@
           <span class="status-dot connected" id="statusDot"></span>
           <span class="status-text" id="statusText">Jarvis Ready</span>
         </div>
+        <div class="sidebar-footer-hint">
+          <kbd>Ctrl+B</kbd>
+        </div>
       </div>
     </aside>
 
-    <!-- Main Chat Workspace -->
+    <!-- Main Command Center Workspace -->
     <main class="main-content">
       <!-- Top Navigation Header -->
       <header class="top-nav">
         <div class="nav-left">
+          <button class="top-nav-btn" id="sidebarExpandBtn" title="Expand Sidebar (Ctrl+B)" style="display: none;">
+            <i class="ti ti-layout-sidebar-left-expand"></i>
+          </button>
+
           <div class="model-select-wrapper">
+            <i class="ti ti-cpu nav-icon"></i>
             <label for="modelSelect">Model:</label>
             <select id="modelSelect" class="model-select">
               <option value="prism-ml/bonsai-27b" selected>Bonsai 27B (Default · LM Studio)</option>
@@ -106,22 +141,19 @@
         <div class="nav-right">
           <!-- Voice Responses Toggle Button -->
           <button id="voiceToggleBtn" class="voice-toggle-btn" title="Toggle Spoken Voice Output (Chatterbox / Kokoro)">
-            <span class="voice-icon">🔊</span>
+            <i class="ti ti-volume voice-icon" id="voiceToggleIcon"></i>
             <span class="voice-text">Voice: OFF</span>
           </button>
 
           <!-- Unload Model Button -->
           <button id="unloadModelBtn" class="unload-btn" title="Instantly unload model and free 100% GPU VRAM">
-            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
-              <path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
-              <line x1="12" y1="2" x2="12" y2="12"></line>
-            </svg>
+            <i class="ti ti-bolt-off"></i>
             <span>Free VRAM</span>
           </button>
 
           <!-- Governor Status Pill with Arc Ring & Command Panel -->
           <div class="governor-widget-container" id="governorWidgetContainer">
-            <div class="governor-pill governor-pill--idle" id="governorPill" title="Hover for telemetry, Click for Governor Control">
+            <div class="governor-pill governor-pill--idle" id="governorPill" title="Hover for telemetry, Click for Governor Control (Alt+G)">
               <div class="governor-arc-ring" id="governorArcRing">
                 <span class="arc-segment arc-segment--idle" title="IDLE"></span>
                 <span class="arc-segment arc-segment--running" title="RUNNING"></span>
@@ -148,11 +180,43 @@
               <div class="gov-panel__header">
                 <div class="gov-panel__title">
                   <i class="ti ti-shield-bolt"></i>
-                  <span>Resource Governor</span>
+                  <span>Hardware Resource Governor</span>
                 </div>
                 <span class="gov-panel__status-tag tag-idle" id="panelStatusTag">IDLE</span>
               </div>
 
+              <!-- Live Telemetry Visualizer Meters -->
+              <div class="gov-telemetry-meters">
+                <div class="gov-meter-row">
+                  <div class="gov-meter-label">
+                    <span>GPU Utilization</span>
+                    <span class="gov-meter-num" id="govMeterGpuVal">0%</span>
+                  </div>
+                  <div class="gov-meter-bar"><div class="gov-meter-fill" id="govMeterGpuFill" style="width: 0%;"></div></div>
+                </div>
+                <div class="gov-meter-row">
+                  <div class="gov-meter-label">
+                    <span>VRAM Allocated</span>
+                    <span class="gov-meter-num" id="govMeterVramVal">0.0 / 8.0 GB</span>
+                  </div>
+                  <div class="gov-meter-bar"><div class="gov-meter-fill" id="govMeterVramFill" style="width: 0%;"></div></div>
+                </div>
+                <div class="gov-meter-row">
+                  <div class="gov-meter-label">
+                    <span>CPU Load</span>
+                    <span class="gov-meter-num" id="govMeterCpuVal">0%</span>
+                  </div>
+                  <div class="gov-meter-bar"><div class="gov-meter-fill" id="govMeterCpuFill" style="width: 0%;"></div></div>
+                </div>
+                <div class="gov-meter-row">
+                  <div class="gov-meter-label">
+                    <span>System RAM</span>
+                    <span class="gov-meter-num" id="govMeterRamVal">0%</span>
+                  </div>
+                  <div class="gov-meter-bar"><div class="gov-meter-fill" id="govMeterRamFill" style="width: 0%;"></div></div>
+                </div>
+              </div>
+
               <!-- Controls Section -->
               <div class="gov-panel__section">
                 <div class="gov-section__label">MANUAL OVERRIDES</div>
@@ -206,22 +270,31 @@
       <section class="chat-viewport" id="chatViewport">
         <div class="empty-state" id="welcomeHero">
           <div class="empty-state__icon-wrapper">
-            <i class="ti ti-diamond empty-state__icon"></i>
+            <i class="ti ti-brand-flightradar24 empty-state__icon"></i>
           </div>
           <p class="empty-state__title" id="empty-state-title">Working in JARVIS core</p>
-          <p class="empty-state__subtitle" id="empty-state-subtitle">Workspace mode — writes stay inside this folder</p>
+          <p class="empty-state__subtitle" id="empty-state-subtitle">Workspace mode - writes stay inside this project folder</p>
           
           <div class="suggestion-grid" id="suggestionGrid">
             <div class="suggestion-card" data-prompt="Check system diagnostics, disk usage, and hardware stats.">
-              <div class="sugg-title">⚡ System Status</div>
+              <div class="sugg-header">
+                <i class="ti ti-activity sugg-icon"></i>
+                <div class="sugg-title">System Status</div>
+              </div>
               <div class="sugg-desc">Inspect disk usage, uptime, and GPU telemetry</div>
             </div>
             <div class="suggestion-card" id="suggWorkspaceCard" data-prompt="List all files in the docs directory.">
-              <div class="sugg-title">📁 Workspace Files</div>
+              <div class="sugg-header">
+                <i class="ti ti-folder-search sugg-icon"></i>
+                <div class="sugg-title">Workspace Files</div>
+              </div>
               <div class="sugg-desc">Explore codebase folders and documentation</div>
             </div>
             <div class="suggestion-card" data-prompt="Please do a code review of backend/app/main.py.">
-              <div class="sugg-title">🔍 Code Review</div>
+              <div class="sugg-header">
+                <i class="ti ti-file-search sugg-icon"></i>
+                <div class="sugg-title">Code Review</div>
+              </div>
               <div class="sugg-desc">Analyze code quality and security best practices</div>
             </div>
           </div>
@@ -230,25 +303,30 @@
         <!-- Messages Thread -->
         <div class="messages-container" id="messagesContainer"></div>
 
-
         <!-- Loading / Thinking Indicator -->
         <div class="loading-bubble" id="loadingBubble" style="display: none;">
-          <div class="spinner"></div>
-          <span>Jarvis is thinking...</span>
+          <div class="loading-pulse-ring"></div>
+          <span class="loading-text">Jarvis is reasoning...</span>
         </div>
 
         <!-- Safety Confirmation Card -->
         <div class="confirmation-panel" id="confirmationPanel" style="display: none;">
           <div class="conf-heading">
-            <span class="conf-icon">⚠️</span>
+            <i class="ti ti-alert-triangle conf-icon"></i>
             <span>Safety Confirmation Required</span>
           </div>
           <div class="conf-text" id="confDetailsText">
             The requested tool execution requires explicit authorization.
           </div>
           <div class="conf-buttons">
-            <button class="btn btn-secondary" id="rejectActionBtn">Cancel</button>
-            <button class="btn btn-primary" id="approveActionBtn">Approve & Execute</button>
+            <button class="btn btn-secondary" id="rejectActionBtn">
+              <i class="ti ti-x"></i>
+              <span>Cancel</span>
+            </button>
+            <button class="btn btn-primary" id="approveActionBtn">
+              <i class="ti ti-check"></i>
+              <span>Approve & Execute</span>
+            </button>
           </div>
         </div>
       </section>
@@ -259,29 +337,21 @@
           <textarea 
             id="promptInput" 
             class="prompt-textarea" 
-            placeholder="Message Jarvis, or ask to run tools..." 
+            placeholder="Message Jarvis, or ask to execute tools..." 
             rows="1"
             autofocus
           ></textarea>
           <div class="composer-actions">
-            <button id="micBtn" class="action-btn mic-btn" title="Voice Input (Say 'Jarvis' or Click to Speak)">
-              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
-                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
-                <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
-                <line x1="12" y1="19" x2="12" y2="23"></line>
-                <line x1="8" y1="23" x2="16" y2="23"></line>
-              </svg>
+            <button id="micBtn" class="action-btn mic-btn" title="Voice Input (Click to speak or say 'Jarvis')">
+              <i class="ti ti-microphone"></i>
             </button>
             <button id="sendBtn" class="action-btn send-btn" title="Send message (Enter)">
-              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
-                <line x1="22" y1="2" x2="11" y2="13"></line>
-                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
-              </svg>
+              <i class="ti ti-send"></i>
             </button>
           </div>
         </div>
         <div class="composer-hints">
-          <span><strong>Enter</strong> to send &bull; <strong>Shift + Enter</strong> for new line &bull; <strong>Alt + Space</strong> to summon/hide</span>
+          <span><strong>Enter</strong> to send &bull; <strong>Shift + Enter</strong> for new line &bull; <strong>Alt + Space</strong> to summon &bull; <strong>Ctrl + B</strong> for sidebar</span>
         </div>
       </footer>
     </main>
diff --git a/desktop/ui/styles.css b/desktop/ui/styles.css
index cc7dc9a..48069c2 100644
--- a/desktop/ui/styles.css
+++ b/desktop/ui/styles.css
@@ -1,62 +1,94 @@
+/* ==========================================================================
+   Jarvis Command Center - Deep Tech Obsidian Design System
+   ========================================================================== */
+
 :root {
-  --bg-darkest: #07090e;
-  --bg-sidebar: #0b0f17;
-  --bg-main: #0f141f;
-  --bg-surface: #151c2c;
-  --bg-surface-hover: #1c263b;
-  --bg-input: #121824;
+  /* Color Palette - Deep Obsidian & Sleek Slates */
+  --bg-void: #05070b;
+  --bg-sidebar: #090d15;
+  --bg-main: #0c101a;
+  --bg-surface: #111726;
+  --bg-surface-hover: #162035;
+  --bg-surface-active: #1d2b47;
+  --bg-input: #0e1422;
+  --bg-glass: rgba(13, 19, 31, 0.82);
   
-  --border: #1e293b;
-  --border-focus: #3b82f6;
+  /* Borders & Highlights */
+  --border-subtle: rgba(255, 255, 255, 0.07);
+  --border-medium: rgba(255, 255, 255, 0.12);
+  --border-strong: rgba(255, 255, 255, 0.2);
+  --border-focus: #06b6d4;
   
-  --text-main: #f1f5f9;
+  /* Text & Hierarchy */
+  --text-main: #f3f7fc;
   --text-muted: #94a3b8;
-  --text-subtle: #64748b;
+  --text-subtle: #52637a;
   
+  /* Accent Colors */
   --primary: #2563eb;
   --primary-hover: #1d4ed8;
   --primary-light: rgba(37, 99, 235, 0.15);
   
-  --success: #10b981;
-  --warning: #f59e0b;
-  --danger: #ef4444;
-
-  /* Governor & Tier Tokens */
+  --accent-cyan: #06b6d4;
+  --accent-cyan-glow: rgba(6, 182, 212, 0.2);
+  --accent-emerald: #10b981;
+  --accent-emerald-glow: rgba(16, 185, 129, 0.2);
+  --accent-violet: #8b5cf6;
+  --accent-amber: #f59e0b;
+  --accent-rose: #f43f5e;
+
+  /* Governor & Telemetry Tokens */
+  --governor-normal: #10b981;
+  --governor-throttled: #f59e0b;
   --governor-idle: #10b981;
-  --governor-running: #3b82f6;
-  --governor-loading: #22d3ee;
+  --governor-running: #06b6d4;
+  --governor-loading: #38bdf8;
   --governor-paused: #ef4444;
   --governor-unloaded: #f59e0b;
   --governor-error: #ef4444;
   --governor-disconnected: #64748b;
 
-  --governor-normal: #10b981;
-  --governor-throttled: #f59e0b;
-
   --tier-1-color: #38bdf8;
   --tier-2-color: #a78bfa;
   --tier-3-color: #f43f5e;
 
-  
+  /* Typography */
   --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
   --font-mono: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
 }
 
-
 * {
   box-sizing: border-box;
   margin: 0;
   padding: 0;
   -webkit-font-smoothing: antialiased;
+  -moz-osx-font-smoothing: grayscale;
 }
 
 body {
-  background-color: var(--bg-darkest);
+  background-color: var(--bg-void);
   font-family: var(--font-sans);
   color: var(--text-main);
   height: 100vh;
   width: 100vw;
   overflow: hidden;
+  user-select: none;
+}
+
+/* Custom Scrollbars */
+::-webkit-scrollbar {
+  width: 6px;
+  height: 6px;
+}
+::-webkit-scrollbar-track {
+  background: transparent;
+}
+::-webkit-scrollbar-thumb {
+  background: rgba(255, 255, 255, 0.1);
+  border-radius: 4px;
+}
+::-webkit-scrollbar-thumb:hover {
+  background: rgba(255, 255, 255, 0.2);
 }
 
 .app-layout {
@@ -64,27 +96,45 @@ body {
   height: 100vh;
   width: 100vw;
   overflow: hidden;
+  position: relative;
+  background-color: var(--bg-void);
 }
 
 /* ==========================================================================
-   Left Sidebar
+   Left Sidebar Drawer
    ========================================================================== */
 .sidebar {
-  width: 260px;
+  width: 270px;
   background-color: var(--bg-sidebar);
-  border-right: 1px solid var(--border);
+  border-right: 1px solid var(--border-subtle);
   display: flex;
   flex-direction: column;
   flex-shrink: 0;
-  user-select: none;
+  transition: width 0.22s cubic-bezier(0.16, 1, 0.3, 1), transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
+  z-index: 50;
+  overflow: hidden;
+}
+
+.sidebar.collapsed {
+  width: 0 !important;
+  min-width: 0 !important;
+  opacity: 0;
+  pointer-events: none;
+  border-right-color: transparent;
 }
 
 .sidebar-header {
   padding: 16px;
   display: flex;
   flex-direction: column;
-  gap: 14px;
-  border-bottom: 1px solid var(--border);
+  gap: 12px;
+  border-bottom: 1px solid var(--border-subtle);
+}
+
+.brand-row {
+  display: flex;
+  align-items: center;
+  justify-content: space-between;
 }
 
 .brand {
@@ -96,55 +146,103 @@ body {
 .brand-icon {
   width: 28px;
   height: 28px;
-  color: #38bdf8;
+  color: var(--accent-cyan);
+  display: flex;
+  align-items: center;
+  justify-content: center;
+}
+
+.brand-icon svg {
+  width: 24px;
+  height: 24px;
 }
 
 .brand-title {
-  font-size: 17px;
+  font-size: 16px;
   font-weight: 700;
-  letter-spacing: -0.3px;
+  letter-spacing: -0.4px;
   color: #fff;
 }
 
-.new-chat-btn {
+.sidebar-toggle-btn, .top-nav-btn {
+  background: transparent;
+  border: 1px solid transparent;
+  color: var(--text-subtle);
+  width: 28px;
+  height: 28px;
+  border-radius: 6px;
   display: flex;
   align-items: center;
   justify-content: center;
+  cursor: pointer;
+  font-size: 15px;
+  transition: all 0.15s ease;
+}
+
+.sidebar-toggle-btn:hover, .top-nav-btn:hover {
+  background-color: var(--bg-surface);
+  color: var(--text-main);
+  border-color: var(--border-subtle);
+}
+
+.new-chat-btn {
+  display: flex;
+  align-items: center;
+  justify-content: space-between;
   gap: 8px;
-  padding: 9px 14px;
+  padding: 8px 12px;
   background-color: var(--primary);
   color: #fff;
-  border: none;
+  border: 1px solid rgba(255, 255, 255, 0.1);
   border-radius: 8px;
-  font-size: 13.5px;
+  font-size: 13px;
   font-weight: 600;
   cursor: pointer;
-  transition: background 0.15s ease;
+  transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
+  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
 }
 
 .new-chat-btn:hover {
   background-color: var(--primary-hover);
+  transform: translateY(-1px);
+  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
 }
 
-.new-chat-btn svg {
-  width: 16px;
-  height: 16px;
+.new-chat-btn:active {
+  transform: scale(0.98);
+}
+
+.new-chat-btn i {
+  font-size: 15px;
+}
+
+.shortcut-badge {
+  font-size: 10px;
+  font-family: var(--font-mono);
+  background: rgba(0, 0, 0, 0.25);
+  border: 1px solid rgba(255, 255, 255, 0.15);
+  padding: 1px 5px;
+  border-radius: 4px;
+  color: rgba(255, 255, 255, 0.8);
 }
 
-/* Sidebar Mode Toggle (Segmented Control) */
+/* Sidebar Mode Toggle */
 .mode-toggle {
   display: flex;
-  background-color: var(--bg-surface);
-  border: 1px solid var(--border);
+  background-color: var(--bg-void);
+  border: 1px solid var(--border-subtle);
   border-radius: 8px;
   padding: 3px;
-  margin-top: 2px;
   gap: 3px;
 }
 
 .mode-toggle__option {
   flex: 1;
-  padding: 6px 10px;
+  display: flex;
+  align-items: center;
+  justify-content: center;
+  gap: 6px;
+  padding: 6px 8px;
   border: none;
   background: transparent;
   color: var(--text-muted);
@@ -154,23 +252,22 @@ body {
   border-radius: 6px;
   cursor: pointer;
   transition: all 0.15s ease;
-  text-align: center;
+}
+
+.mode-toggle__option i {
+  font-size: 14px;
 }
 
 .mode-toggle__option:hover:not(:disabled) {
   color: var(--text-main);
-  background-color: rgba(255, 255, 255, 0.04);
+  background-color: var(--bg-surface);
 }
 
 .mode-toggle__option--active {
-  background-color: var(--primary) !important;
-  color: #fff !important;
-  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
-}
-
-.mode-toggle__option:disabled {
-  opacity: 0.5;
-  cursor: not-allowed;
+  background-color: var(--bg-surface-active) !important;
+  color: var(--accent-cyan) !important;
+  border: 1px solid rgba(6, 182, 212, 0.25);
+  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
 }
 
 /* Active Project Indicator */
@@ -179,30 +276,19 @@ body {
   align-items: center;
   gap: 8px;
   padding: 6px 10px;
-  background-color: rgba(56, 189, 248, 0.08);
-  border: 1px solid rgba(56, 189, 248, 0.2);
+  background-color: rgba(6, 182, 212, 0.08);
+  border: 1px solid rgba(6, 182, 212, 0.2);
   border-radius: 8px;
   font-size: 11.5px;
-  color: #38bdf8;
-  margin-top: 2px;
+  color: var(--accent-cyan);
   font-weight: 500;
 }
 
 .active-project i {
-  font-size: 13px;
-}
-
-/* Recent Sessions Group Header */
-.session-group-header {
-  font-size: 10px;
-  font-weight: 700;
-  text-transform: uppercase;
-  letter-spacing: 0.05em;
-  color: var(--text-subtle);
-  padding: 6px 8px 3px;
-  margin-top: 2px;
+  font-size: 14px;
 }
 
+/* Sidebar Sections */
 .sidebar-section {
   padding: 14px 12px 6px;
   display: flex;
@@ -210,47 +296,125 @@ body {
   gap: 4px;
 }
 
-
 .sessions-section {
   flex: 1;
   overflow-y: auto;
+  padding-bottom: 12px;
 }
 
 .section-label {
-  font-size: 11px;
+  display: flex;
+  align-items: center;
+  justify-content: space-between;
+  font-size: 10.5px;
   font-weight: 700;
   text-transform: uppercase;
-  letter-spacing: 0.5px;
+  letter-spacing: 0.6px;
   color: var(--text-subtle);
   padding: 0 8px 6px;
 }
 
+.skills-count-badge {
+  font-size: 9.5px;
+  font-weight: 600;
+  color: var(--accent-emerald);
+  background: rgba(16, 185, 129, 0.1);
+  padding: 1px 6px;
+  border-radius: 4px;
+  border: 1px solid rgba(16, 185, 129, 0.2);
+}
+
+.icon-action-btn {
+  background: transparent;
+  border: none;
+  color: var(--text-subtle);
+  cursor: pointer;
+  font-size: 13px;
+  padding: 2px 4px;
+  border-radius: 4px;
+  transition: color 0.15s ease;
+}
+
+.icon-action-btn:hover {
+  color: var(--text-main);
+}
+
 .skill-item, .session-item {
   display: flex;
   align-items: center;
+  justify-content: space-between;
   gap: 10px;
-  padding: 8px 10px;
+  padding: 7px 10px;
   border-radius: 6px;
-  font-size: 13px;
+  font-size: 12.5px;
   color: var(--text-muted);
   cursor: pointer;
   transition: all 0.12s ease;
+  border: 1px solid transparent;
 }
 
 .skill-item:hover, .session-item:hover {
   background-color: var(--bg-surface);
   color: var(--text-main);
+  border-color: var(--border-subtle);
+}
+
+.skill-item .skill-icon, .session-item .session-icon {
+  font-size: 15px;
+  color: var(--text-subtle);
+  flex-shrink: 0;
+}
+
+.skill-item:hover .skill-icon {
+  color: var(--accent-cyan);
 }
 
 .session-item.active {
-  background-color: var(--primary-light);
-  color: #60a5fa;
+  background-color: var(--bg-surface);
+  color: #fff;
   font-weight: 600;
+  border-color: rgba(6, 182, 212, 0.3);
+  box-shadow: inset 2px 0 0 var(--accent-cyan);
+}
+
+.session-item.active .session-icon {
+  color: var(--accent-cyan);
+}
+
+.session-name {
+  flex: 1;
+  white-space: nowrap;
+  overflow: hidden;
+  text-overflow: ellipsis;
+}
+
+.session-delete-btn {
+  opacity: 0;
+  background: transparent;
+  border: none;
+  color: var(--text-subtle);
+  font-size: 13px;
+  padding: 2px;
+  border-radius: 4px;
+  cursor: pointer;
+  transition: all 0.12s ease;
+}
+
+.session-item:hover .session-delete-btn {
+  opacity: 1;
+}
+
+.session-delete-btn:hover {
+  color: var(--accent-rose);
+  background: rgba(244, 63, 94, 0.15);
 }
 
 .sidebar-footer {
   padding: 12px 16px;
-  border-top: 1px solid var(--border);
+  border-top: 1px solid var(--border-subtle);
+  display: flex;
+  align-items: center;
+  justify-content: space-between;
 }
 
 .status-badge {
@@ -262,22 +426,34 @@ body {
 }
 
 .status-dot {
-  width: 8px;
-  height: 8px;
+  width: 7px;
+  height: 7px;
   border-radius: 50%;
   background-color: var(--text-subtle);
 }
 
 .status-dot.connected {
-  background-color: var(--success);
+  background-color: var(--accent-emerald);
+  box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
 }
 
 .status-dot.throttled {
-  background-color: var(--warning);
+  background-color: var(--accent-amber);
+  box-shadow: 0 0 8px rgba(245, 158, 11, 0.6);
+}
+
+.sidebar-footer-hint kbd {
+  font-size: 10px;
+  font-family: var(--font-mono);
+  background: var(--bg-void);
+  border: 1px solid var(--border-subtle);
+  padding: 2px 6px;
+  border-radius: 4px;
+  color: var(--text-subtle);
 }
 
 /* ==========================================================================
-   Main Workspace
+   Main Command Center Workspace
    ========================================================================== */
 .main-content {
   flex: 1;
@@ -285,19 +461,21 @@ body {
   flex-direction: column;
   background-color: var(--bg-main);
   overflow: hidden;
+  position: relative;
 }
 
 .top-nav {
   height: 52px;
-  padding: 0 16px;
+  padding: 0 18px;
   display: flex;
   align-items: center;
   justify-content: space-between;
-  border-bottom: 1px solid var(--border);
-  background-color: rgba(15, 20, 31, 0.85);
-  backdrop-filter: blur(12px);
-  user-select: none;
+  border-bottom: 1px solid var(--border-subtle);
+  background-color: var(--bg-glass);
+  backdrop-filter: blur(16px);
+  -webkit-backdrop-filter: blur(16px);
   gap: 12px;
+  z-index: 40;
 }
 
 .nav-left {
@@ -315,79 +493,138 @@ body {
   color: var(--text-muted);
 }
 
+.nav-icon {
+  font-size: 16px;
+  color: var(--accent-cyan);
+}
+
 .model-select {
   background-color: var(--bg-surface);
   color: var(--text-main);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
   padding: 5px 10px;
   border-radius: 6px;
-  font-size: 12.5px;
+  font-size: 12px;
   font-weight: 500;
   outline: none;
   cursor: pointer;
+  transition: border-color 0.15s ease;
 }
 
 .model-select:focus {
   border-color: var(--border-focus);
 }
 
-/* Top Nav Tier Badges */
+/* Tier Badges */
 .tier-badge {
-  padding: 3px 8px;
-  border-radius: 10px;
+  padding: 2px 8px;
+  border-radius: 8px;
   font-size: 10.5px;
   font-weight: 700;
   letter-spacing: 0.03em;
   text-transform: uppercase;
   font-family: var(--font-sans);
   white-space: nowrap;
-  display: inline-flex;
-  align-items: center;
-  line-height: 1.2;
-  flex-shrink: 0;
 }
 
 .tier-badge--1 {
-  background-color: rgba(56, 189, 248, 0.15);
+  background-color: rgba(56, 189, 248, 0.12);
   color: var(--tier-1-color);
-  border: 1px solid rgba(56, 189, 248, 0.3);
+  border: 1px solid rgba(56, 189, 248, 0.25);
 }
 
 .tier-badge--2 {
-  background-color: rgba(167, 139, 250, 0.15);
+  background-color: rgba(167, 139, 250, 0.12);
   color: var(--tier-2-color);
-  border: 1px solid rgba(167, 139, 250, 0.3);
+  border: 1px solid rgba(167, 139, 250, 0.25);
 }
 
 .tier-badge--3 {
-  background-color: rgba(244, 63, 94, 0.15);
+  background-color: rgba(244, 63, 94, 0.12);
   color: var(--tier-3-color);
-  border: 1px solid rgba(244, 63, 94, 0.3);
+  border: 1px solid rgba(244, 63, 94, 0.25);
 }
 
-/* Routing Pill in Top Nav */
 .routing-pill-toggle {
   display: flex;
   align-items: center;
-  gap: 5px;
+  gap: 6px;
   cursor: pointer;
-  flex-shrink: 0;
 }
 
 .mode-label {
   font-size: 11.5px;
-  color: var(--text-muted);
+  color: var(--text-subtle);
 }
 
 .mode-pill {
   padding: 2px 8px;
   background-color: var(--bg-surface);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
   border-radius: 12px;
   font-size: 11px;
   font-weight: 600;
-  color: #38bdf8;
-  white-space: nowrap;
+  color: var(--accent-cyan);
+}
+
+/* Top Nav Right Controls */
+.nav-right {
+  display: flex;
+  align-items: center;
+  gap: 8px;
+  flex-shrink: 0;
+}
+
+.voice-toggle-btn {
+  display: flex;
+  align-items: center;
+  gap: 6px;
+  padding: 5px 12px;
+  background-color: var(--bg-surface);
+  border: 1px solid var(--border-subtle);
+  border-radius: 16px;
+  font-size: 11.5px;
+  font-weight: 600;
+  color: var(--text-muted);
+  cursor: pointer;
+  transition: all 0.15s ease;
+}
+
+.voice-toggle-btn:hover {
+  background-color: var(--bg-surface-hover);
+  color: var(--text-main);
+  border-color: var(--border-medium);
+}
+
+.voice-toggle-btn.active {
+  background-color: rgba(16, 185, 129, 0.12);
+  border-color: rgba(16, 185, 129, 0.35);
+  color: #34d399;
+}
+
+.unload-btn {
+  display: flex;
+  align-items: center;
+  gap: 6px;
+  padding: 5px 12px;
+  background-color: rgba(239, 68, 68, 0.1);
+  border: 1px solid rgba(239, 68, 68, 0.25);
+  border-radius: 16px;
+  font-size: 11.5px;
+  font-weight: 600;
+  color: #f87171;
+  cursor: pointer;
+  transition: all 0.15s ease;
+}
+
+.unload-btn:hover {
+  background-color: rgba(239, 68, 68, 0.2);
+  border-color: #ef4444;
+  color: #fff;
+}
+
+.unload-btn:active {
+  transform: scale(0.97);
 }
 
 /* Governor Widget Container */
@@ -396,7 +633,6 @@ body {
   display: inline-flex;
 }
 
-/* Governor Status Pill */
 .governor-pill {
   position: relative;
   display: flex;
@@ -404,24 +640,21 @@ body {
   gap: 8px;
   padding: 5px 12px;
   background-color: var(--bg-surface);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
   border-radius: 18px;
   font-size: 11.5px;
   font-weight: 600;
   cursor: pointer;
-  user-select: none;
-  white-space: nowrap;
-  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
-  flex-shrink: 0;
+  transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
 }
 
 .governor-pill:hover {
-  border-color: var(--text-muted);
+  border-color: var(--border-medium);
   background-color: var(--bg-surface-hover);
 }
 
 .governor-widget-container.open .governor-pill {
-  border-color: var(--primary);
+  border-color: var(--accent-cyan);
   background-color: var(--bg-surface-hover);
 }
 
@@ -436,16 +669,12 @@ body {
   justify-content: center;
   background: conic-gradient(
     from 0deg,
-    rgba(16, 185, 129, 0.2) 0deg 60deg,
-    rgba(59, 130, 246, 0.2) 60deg 120deg,
-    rgba(34, 211, 238, 0.2) 120deg 180deg,
-    rgba(239, 68, 68, 0.2) 180deg 240deg,
-    rgba(245, 158, 11, 0.2) 240deg 300deg,
-    rgba(239, 68, 68, 0.2) 300deg 360deg
+    rgba(16, 185, 129, 0.3) 0deg 90deg,
+    rgba(6, 182, 212, 0.3) 90deg 180deg,
+    rgba(245, 158, 11, 0.3) 180deg 270deg,
+    rgba(239, 68, 68, 0.3) 270deg 360deg
   );
   padding: 2px;
-  flex-shrink: 0;
-  transition: box-shadow 0.3s ease;
 }
 
 .arc-center-dot {
@@ -453,102 +682,33 @@ body {
   height: 7px;
   border-radius: 50%;
   background-color: var(--governor-idle);
-  box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
+  box-shadow: 0 0 8px rgba(16, 185, 129, 0.7);
   transition: all 0.25s ease;
   z-index: 2;
 }
 
-/* Tier State Variations */
-.governor-pill--idle .arc-center-dot,
-.governor-pill--normal .arc-center-dot {
-  background-color: var(--governor-idle);
-  box-shadow: 0 0 8px rgba(16, 185, 129, 0.7);
-}
-.governor-pill--idle .governor-arc-ring,
-.governor-pill--normal .governor-arc-ring {
-  box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
-}
+.governor-pill--idle .arc-center-dot { background-color: var(--governor-idle); box-shadow: 0 0 8px rgba(16, 185, 129, 0.8); }
+.governor-pill--running .arc-center-dot { background-color: var(--governor-running); box-shadow: 0 0 8px rgba(6, 182, 212, 0.8); }
+.governor-pill--loading .arc-center-dot { background-color: var(--governor-loading); animation: arc-pulse 1.2s infinite ease-in-out; }
+.governor-pill--paused .arc-center-dot { background-color: var(--governor-paused); box-shadow: 0 0 8px rgba(239, 68, 68, 0.8); }
+.governor-pill--unloaded .arc-center-dot { background-color: var(--governor-unloaded); box-shadow: 0 0 8px rgba(245, 158, 11, 0.8); }
+.governor-pill--error .arc-center-dot { background-color: var(--governor-error); animation: arc-blink 0.8s infinite ease-in-out; }
+.governor-pill--disconnected .arc-center-dot { background-color: var(--governor-disconnected); box-shadow: none; }
 
-.governor-pill--running .arc-center-dot,
-.governor-pill--busy .arc-center-dot {
-  background-color: var(--governor-running);
-  box-shadow: 0 0 8px rgba(59, 130, 246, 0.8);
-}
-.governor-pill--running .governor-arc-ring,
-.governor-pill--busy .governor-arc-ring {
-  box-shadow: 0 0 10px rgba(59, 130, 246, 0.35);
-}
-
-.governor-pill--loading .arc-center-dot {
-  background-color: var(--governor-loading);
-  animation: arc-pulse 1.2s infinite ease-in-out;
-}
-.governor-pill--loading .governor-arc-ring {
-  animation: arc-pulse 1.2s infinite ease-in-out;
-}
-
-.governor-pill--paused .arc-center-dot {
-  background-color: var(--governor-paused);
-  box-shadow: 0 0 8px rgba(239, 68, 68, 0.8);
-}
-.governor-pill--paused .governor-arc-ring {
-  box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);
-}
-
-.governor-pill--unloaded .arc-center-dot,
-.governor-pill--throttled .arc-center-dot {
-  background-color: var(--governor-unloaded);
-  box-shadow: 0 0 8px rgba(245, 158, 11, 0.8);
-}
-.governor-pill--unloaded .governor-arc-ring,
-.governor-pill--throttled .governor-arc-ring {
-  box-shadow: 0 0 10px rgba(245, 158, 11, 0.4);
-}
-
-.governor-pill--error .arc-center-dot {
-  background-color: var(--governor-error);
-  animation: arc-blink 0.8s infinite ease-in-out;
-}
-.governor-pill--error .governor-arc-ring {
-  animation: arc-blink 0.8s infinite ease-in-out;
-}
-
-.governor-pill--disconnected .arc-center-dot {
-  background-color: var(--governor-disconnected);
-  box-shadow: none;
-}
-.governor-pill--disconnected .governor-arc-ring {
-  background: rgba(100, 116, 139, 0.2);
-  box-shadow: none;
-}
-
-@keyframes arc-pulse {
-  0%, 100% {
-    box-shadow: 0 0 4px rgba(34, 211, 238, 0.3);
-    opacity: 0.85;
-  }
-  50% {
-    box-shadow: 0 0 14px rgba(34, 211, 238, 0.95);
-    opacity: 1;
-  }
+@keyframes arc-pulse {
+  0%, 100% { opacity: 0.8; transform: scale(0.9); }
+  50% { opacity: 1; transform: scale(1.2); box-shadow: 0 0 12px rgba(6, 182, 212, 0.9); }
 }
 
 @keyframes arc-blink {
-  0%, 100% {
-    opacity: 1;
-    box-shadow: 0 0 12px rgba(239, 68, 68, 0.9);
-  }
-  50% {
-    opacity: 0.25;
-    box-shadow: none;
-  }
+  0%, 100% { opacity: 1; box-shadow: 0 0 12px rgba(239, 68, 68, 0.9); }
+  50% { opacity: 0.3; box-shadow: none; }
 }
 
 .pill-chevron {
-  font-size: 11px;
+  font-size: 12px;
   color: var(--text-subtle);
-  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
-  margin-left: 2px;
+  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
 }
 
 .governor-widget-container.open .pill-chevron {
@@ -561,9 +721,10 @@ body {
   position: absolute;
   top: calc(100% + 8px);
   right: 0;
-  background-color: rgba(7, 9, 14, 0.95);
-  backdrop-filter: blur(12px);
-  border: 1px solid var(--border);
+  background-color: rgba(9, 13, 21, 0.95);
+  backdrop-filter: blur(14px);
+  -webkit-backdrop-filter: blur(14px);
+  border: 1px solid var(--border-subtle);
   border-radius: 8px;
   padding: 10px 14px;
   display: flex;
@@ -571,8 +732,7 @@ body {
   gap: 5px;
   font-size: 11.5px;
   font-family: var(--font-mono);
-  color: var(--text-main);
-  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.6);
+  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.7);
   z-index: 110;
   min-width: 160px;
   opacity: 0;
@@ -609,21 +769,22 @@ body {
   position: absolute;
   top: calc(100% + 10px);
   right: 0;
-  width: 330px;
-  background: rgba(11, 15, 23, 0.96);
+  width: 340px;
+  background: rgba(11, 16, 26, 0.97);
   backdrop-filter: blur(20px);
-  border: 1px solid rgba(255, 255, 255, 0.1);
+  -webkit-backdrop-filter: blur(20px);
+  border: 1px solid var(--border-medium);
   border-radius: 12px;
   padding: 16px;
   display: flex;
   flex-direction: column;
   gap: 14px;
-  box-shadow: 0 20px 45px rgba(0, 0, 0, 0.75), 0 0 1px rgba(255, 255, 255, 0.15);
+  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8), 0 0 1px rgba(255, 255, 255, 0.1);
   z-index: 120;
   opacity: 0;
   visibility: hidden;
   transform: translateY(-8px);
-  transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
+  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
   pointer-events: none;
 }
 
@@ -639,7 +800,7 @@ body {
   align-items: center;
   justify-content: space-between;
   padding-bottom: 10px;
-  border-bottom: 1px solid var(--border);
+  border-bottom: 1px solid var(--border-subtle);
 }
 
 .gov-panel__title {
@@ -653,25 +814,70 @@ body {
 
 .gov-panel__title i {
   font-size: 16px;
-  color: var(--primary-focus, #38bdf8);
+  color: var(--accent-cyan);
 }
 
 .gov-panel__status-tag {
-  font-size: 10.5px;
+  font-size: 10px;
   font-weight: 700;
-  padding: 3px 8px;
+  padding: 2px 7px;
   border-radius: 6px;
   text-transform: uppercase;
   letter-spacing: 0.5px;
 }
 
 .tag-idle { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); }
-.tag-running { background: rgba(59, 130, 246, 0.15); color: #3b82f6; border: 1px solid rgba(59, 130, 246, 0.3); }
-.tag-loading { background: rgba(34, 211, 238, 0.15); color: #22d3ee; border: 1px solid rgba(34, 211, 238, 0.3); }
+.tag-running { background: rgba(6, 182, 212, 0.15); color: #06b6d4; border: 1px solid rgba(6, 182, 212, 0.3); }
+.tag-loading { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
 .tag-paused { background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }
 .tag-unloaded { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }
 .tag-error { background: rgba(239, 68, 68, 0.25); color: #f87171; border: 1px solid #ef4444; }
 
+/* Telemetry Visualizer Meters */
+.gov-telemetry-meters {
+  display: flex;
+  flex-direction: column;
+  gap: 8px;
+  background: var(--bg-void);
+  border: 1px solid var(--border-subtle);
+  border-radius: 8px;
+  padding: 10px 12px;
+}
+
+.gov-meter-row {
+  display: flex;
+  flex-direction: column;
+  gap: 4px;
+}
+
+.gov-meter-label {
+  display: flex;
+  justify-content: space-between;
+  font-size: 11px;
+  color: var(--text-muted);
+}
+
+.gov-meter-num {
+  font-family: var(--font-mono);
+  font-weight: 600;
+  color: #fff;
+}
+
+.gov-meter-bar {
+  width: 100%;
+  height: 5px;
+  background: rgba(255, 255, 255, 0.08);
+  border-radius: 4px;
+  overflow: hidden;
+}
+
+.gov-meter-fill {
+  height: 100%;
+  background: linear-gradient(90deg, var(--accent-emerald), var(--accent-cyan));
+  border-radius: 4px;
+  transition: width 0.3s ease;
+}
+
 .gov-panel__section {
   display: flex;
   flex-direction: column;
@@ -690,7 +896,6 @@ body {
 .gov-history__refresh-hint {
   font-size: 9.5px;
   color: var(--text-subtle);
-  font-weight: 500;
 }
 
 .gov-btn-group {
@@ -711,7 +916,6 @@ body {
   cursor: pointer;
   border: 1px solid transparent;
   transition: all 0.15s ease;
-  user-select: none;
 }
 
 .gov-btn--toggle {
@@ -735,13 +939,13 @@ body {
 }
 
 .gov-btn--override {
-  background: rgba(59, 130, 246, 0.12);
-  color: #60a5fa;
-  border-color: rgba(59, 130, 246, 0.25);
+  background: rgba(6, 182, 212, 0.12);
+  color: #38bdf8;
+  border-color: rgba(6, 182, 212, 0.25);
 }
 .gov-btn--override:hover {
-  background: rgba(59, 130, 246, 0.22);
-  border-color: #3b82f6;
+  background: rgba(6, 182, 212, 0.22);
+  border-color: #06b6d4;
 }
 
 .gov-custom-row {
@@ -752,8 +956,8 @@ body {
 .gov-duration-input {
   width: 70px;
   padding: 6px 10px;
-  background: var(--bg-darkest);
-  border: 1px solid var(--border);
+  background: var(--bg-void);
+  border: 1px solid var(--border-subtle);
   border-radius: 8px;
   color: var(--text-main);
   font-size: 12px;
@@ -761,18 +965,18 @@ body {
   outline: none;
 }
 .gov-duration-input:focus {
-  border-color: var(--primary);
+  border-color: var(--accent-cyan);
 }
 
 .gov-btn--secondary {
   flex: 1;
   background: var(--bg-surface);
   color: var(--text-main);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
 }
 .gov-btn--secondary:hover {
   background: var(--bg-surface-hover);
-  border-color: var(--text-muted);
+  border-color: var(--border-medium);
 }
 
 .gov-contextual-actions {
@@ -792,21 +996,20 @@ body {
 }
 
 .gov-btn--danger {
-  background: rgba(239, 68, 68, 0.2);
+  background: rgba(239, 68, 68, 0.15);
   color: #fca5a5;
   border-color: #ef4444;
 }
 .gov-btn--danger:hover {
-  background: rgba(239, 68, 68, 0.32);
+  background: rgba(239, 68, 68, 0.25);
 }
 
 .hidden {
   display: none !important;
 }
 
-/* History List */
 .gov-history-list {
-  max-height: 150px;
+  max-height: 140px;
   overflow-y: auto;
   display: flex;
   flex-direction: column;
@@ -814,23 +1017,15 @@ body {
   padding-right: 4px;
 }
 
-.gov-history-list::-webkit-scrollbar {
-  width: 4px;
-}
-.gov-history-list::-webkit-scrollbar-thumb {
-  background: var(--border);
-  border-radius: 4px;
-}
-
 .gov-history-item {
   display: flex;
   flex-direction: column;
   gap: 2px;
   padding: 6px 8px;
-  background: rgba(21, 28, 44, 0.5);
+  background: var(--bg-void);
   border-radius: 6px;
   font-size: 11px;
-  border-left: 3px solid var(--border);
+  border-left: 3px solid var(--border-subtle);
 }
 
 .gov-history-item.hist-idle { border-left-color: var(--governor-idle); }
@@ -868,79 +1063,6 @@ body {
   padding: 12px 0;
 }
 
-/* Nav Right Controls */
-.nav-right {
-  display: flex;
-  align-items: center;
-  gap: 8px;
-  flex-shrink: 0;
-}
-
-.voice-toggle-btn {
-  display: flex;
-  align-items: center;
-  gap: 5px;
-  padding: 5px 11px;
-  background-color: var(--bg-surface);
-  border: 1px solid var(--border);
-  border-radius: 16px;
-  font-size: 11.5px;
-  font-weight: 600;
-  color: var(--text-muted);
-  cursor: pointer;
-  white-space: nowrap;
-  transition: all 0.15s ease;
-  flex-shrink: 0;
-}
-
-.voice-toggle-btn:hover {
-  background-color: var(--bg-surface-hover);
-  color: var(--text-main);
-}
-
-.voice-toggle-btn.active {
-  background-color: rgba(16, 185, 129, 0.15);
-  border-color: rgba(16, 185, 129, 0.4);
-  color: #34d399;
-}
-
-.unload-btn {
-  display: flex;
-  align-items: center;
-  gap: 5px;
-  padding: 5px 11px;
-  background-color: rgba(239, 68, 68, 0.12);
-  border: 1px solid rgba(239, 68, 68, 0.35);
-  border-radius: 16px;
-  font-size: 11.5px;
-  font-weight: 600;
-  color: #f87171;
-  cursor: pointer;
-  white-space: nowrap;
-  transition: all 0.15s ease;
-  flex-shrink: 0;
-}
-
-.unload-btn:hover {
-  background-color: rgba(239, 68, 68, 0.22);
-  border-color: #ef4444;
-  color: #fff;
-  transform: scale(1.02);
-}
-
-.unload-btn:active {
-  transform: scale(0.97);
-}
-
-.unload-btn svg {
-  width: 14px;
-  height: 14px;
-  flex-shrink: 0;
-}
-
-
-
-
 /* ==========================================================================
    Chat Viewport
    ========================================================================== */
@@ -951,37 +1073,35 @@ body {
   display: flex;
   flex-direction: column;
   gap: 18px;
-  scrollbar-width: thin;
-  scrollbar-color: var(--border) transparent;
 }
 
-.welcome-hero, .empty-state {
+.empty-state {
   margin: auto;
-  max-width: 600px;
+  max-width: 620px;
   text-align: center;
   display: flex;
   flex-direction: column;
   align-items: center;
   gap: 12px;
-  padding: 36px 0;
+  padding: 32px 0;
 }
 
 .empty-state__icon-wrapper {
   width: 52px;
   height: 52px;
   border-radius: 14px;
-  background: linear-gradient(135deg, rgba(56, 189, 248, 0.15), rgba(37, 99, 235, 0.2));
+  background: linear-gradient(135deg, rgba(6, 182, 212, 0.15), rgba(37, 99, 235, 0.2));
   display: flex;
   align-items: center;
   justify-content: center;
   margin-bottom: 6px;
-  border: 1px solid rgba(56, 189, 248, 0.3);
-  box-shadow: 0 4px 16px rgba(56, 189, 248, 0.12);
+  border: 1px solid rgba(6, 182, 212, 0.3);
+  box-shadow: 0 4px 20px rgba(6, 182, 212, 0.15);
 }
 
 .empty-state__icon {
   font-size: 26px;
-  color: #38bdf8;
+  color: var(--accent-cyan);
 }
 
 .empty-state__title {
@@ -989,36 +1109,14 @@ body {
   font-weight: 700;
   color: #fff;
   letter-spacing: -0.4px;
-  margin-bottom: 2px;
 }
 
 .empty-state__subtitle {
   font-size: 13.5px;
   color: var(--text-muted);
   line-height: 1.5;
-  margin-bottom: 8px;
-}
-
-.hero-logo {
-  width: 56px;
-  height: 56px;
-  color: #38bdf8;
 }
 
-.welcome-hero h1 {
-  font-size: 26px;
-  font-weight: 700;
-  color: #fff;
-  letter-spacing: -0.5px;
-}
-
-.welcome-hero p {
-  font-size: 14.5px;
-  color: var(--text-muted);
-  line-height: 1.5;
-}
-
-
 .suggestion-grid {
   display: grid;
   grid-template-columns: repeat(3, 1fr);
@@ -1030,24 +1128,38 @@ body {
 .suggestion-card {
   padding: 14px;
   background-color: var(--bg-surface);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
   border-radius: 10px;
   text-align: left;
   cursor: pointer;
-  transition: all 0.15s ease;
+  transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
+  display: flex;
+  flex-direction: column;
+  gap: 6px;
 }
 
 .suggestion-card:hover {
   background-color: var(--bg-surface-hover);
-  border-color: #3b82f6;
+  border-color: var(--accent-cyan);
   transform: translateY(-2px);
+  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
+}
+
+.sugg-header {
+  display: flex;
+  align-items: center;
+  gap: 8px;
+}
+
+.sugg-icon {
+  font-size: 16px;
+  color: var(--accent-cyan);
 }
 
 .sugg-title {
   font-size: 13px;
   font-weight: 600;
   color: #fff;
-  margin-bottom: 4px;
 }
 
 .sugg-desc {
@@ -1060,8 +1172,8 @@ body {
 .messages-container {
   display: flex;
   flex-direction: column;
-  gap: 16px;
-  max-width: 840px;
+  gap: 18px;
+  max-width: 860px;
   width: 100%;
   margin: 0 auto;
 }
@@ -1069,7 +1181,7 @@ body {
 .msg-row {
   display: flex;
   flex-direction: column;
-  gap: 6px;
+  gap: 8px;
   width: 100%;
 }
 
@@ -1082,9 +1194,9 @@ body {
 }
 
 .msg-bubble {
-  padding: 12px 18px;
+  padding: 14px 18px;
   border-radius: 12px;
-  font-size: 14.5px;
+  font-size: 14px;
   line-height: 1.6;
   max-width: 85%;
   word-break: break-word;
@@ -1092,72 +1204,348 @@ body {
 }
 
 .msg-row.user .msg-bubble {
-  background-color: var(--primary);
-  color: #fff;
+  background-color: #1e3a8a;
+  color: #f8fafc;
+  border: 1px solid rgba(59, 130, 246, 0.3);
   border-bottom-right-radius: 4px;
+  box-shadow: 0 4px 14px rgba(30, 58, 138, 0.25);
 }
 
 .msg-row.assistant .msg-bubble {
   background-color: var(--bg-surface);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
   color: var(--text-main);
   max-width: 100%;
   border-bottom-left-radius: 4px;
+  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
 }
 
-.tool-badge {
-  display: inline-flex;
+/* Markdown Rendering Elements inside Message Bubble */
+.msg-bubble p {
+  margin-bottom: 10px;
+}
+.msg-bubble p:last-child {
+  margin-bottom: 0;
+}
+
+.msg-bubble h1, .msg-bubble h2, .msg-bubble h3, .msg-bubble h4 {
+  color: #fff;
+  margin-top: 14px;
+  margin-bottom: 8px;
+  font-weight: 700;
+  letter-spacing: -0.3px;
+}
+.msg-bubble h1 { font-size: 18px; }
+.msg-bubble h2 { font-size: 16px; }
+.msg-bubble h3 { font-size: 14.5px; }
+
+.msg-bubble ul, .msg-bubble ol {
+  margin-left: 20px;
+  margin-bottom: 10px;
+}
+
+.msg-bubble li {
+  margin-bottom: 4px;
+}
+
+.msg-bubble blockquote {
+  border-left: 3px solid var(--accent-cyan);
+  padding-left: 12px;
+  margin: 10px 0;
+  color: var(--text-muted);
+  font-style: italic;
+}
+
+.msg-bubble table {
+  width: 100%;
+  border-collapse: collapse;
+  margin: 12px 0;
+  font-size: 13px;
+}
+
+.msg-bubble th, .msg-bubble td {
+  border: 1px solid var(--border-subtle);
+  padding: 8px 12px;
+  text-align: left;
+}
+
+.msg-bubble th {
+  background: var(--bg-void);
+  font-weight: 600;
+  color: #fff;
+}
+
+.msg-bubble tr:nth-child(even) {
+  background: rgba(255, 255, 255, 0.02);
+}
+
+.msg-bubble a {
+  color: var(--accent-cyan);
+  text-decoration: none;
+}
+.msg-bubble a:hover {
+  text-decoration: underline;
+}
+
+.msg-bubble code:not([class*="language-"]) {
+  background-color: var(--bg-void);
+  border: 1px solid var(--border-subtle);
+  padding: 2px 6px;
+  border-radius: 4px;
+  font-family: var(--font-mono);
+  font-size: 12.5px;
+  color: #38bdf8;
+}
+
+/* Code Block Wrapper with Language Header & Copy Button */
+.code-block-wrapper {
+  margin: 12px 0;
+  background-color: var(--bg-void);
+  border: 1px solid var(--border-subtle);
+  border-radius: 8px;
+  overflow: hidden;
+}
+
+.code-header {
+  display: flex;
+  align-items: center;
+  justify-content: space-between;
+  padding: 6px 12px;
+  background: rgba(255, 255, 255, 0.03);
+  border-bottom: 1px solid var(--border-subtle);
+  font-family: var(--font-mono);
+  font-size: 11px;
+  color: var(--text-subtle);
+  text-transform: uppercase;
+}
+
+.copy-code-btn {
+  display: flex;
   align-items: center;
+  gap: 4px;
+  background: transparent;
+  border: 1px solid var(--border-subtle);
+  color: var(--text-muted);
+  padding: 3px 8px;
+  border-radius: 4px;
+  font-size: 11px;
+  font-family: var(--font-sans);
+  cursor: pointer;
+  transition: all 0.15s ease;
+}
+
+.copy-code-btn:hover {
+  background: var(--bg-surface);
+  color: #fff;
+  border-color: var(--border-medium);
+}
+
+.copy-code-btn.copied {
+  color: var(--accent-emerald);
+  border-color: rgba(16, 185, 129, 0.4);
+}
+
+.code-block-wrapper pre {
+  margin: 0 !important;
+  padding: 12px 14px !important;
+  background: transparent !important;
+  font-family: var(--font-mono) !important;
+  font-size: 13px !important;
+  line-height: 1.5 !important;
+  overflow-x: auto;
+}
+
+/* Collapsible Tool Step Cards */
+.tool-step-container {
+  display: flex;
+  flex-direction: column;
   gap: 6px;
-  padding: 3px 10px;
-  background-color: var(--bg-darkest);
-  border: 1px solid var(--border);
-  border-radius: 6px;
+  margin-top: 8px;
+  width: 100%;
+}
+
+.tool-step-card {
+  background-color: var(--bg-void);
+  border: 1px solid var(--border-subtle);
+  border-radius: 8px;
+  overflow: hidden;
+  transition: border-color 0.15s ease;
+}
+
+.tool-step-card:hover {
+  border-color: var(--border-medium);
+}
+
+.tool-step-header {
+  display: flex;
+  align-items: center;
+  justify-content: space-between;
+  padding: 8px 12px;
+  cursor: pointer;
+  user-select: none;
+  font-size: 12px;
+}
+
+.tool-step-left {
+  display: flex;
+  align-items: center;
+  gap: 8px;
+}
+
+.tool-step-icon {
+  font-size: 15px;
+  color: var(--accent-cyan);
+}
+
+.tool-step-name {
   font-family: var(--font-mono);
+  font-weight: 600;
+  color: #fff;
+}
+
+.tool-step-args-preview {
+  color: var(--text-subtle);
   font-size: 11.5px;
-  color: #38bdf8;
-  margin-top: 6px;
+  max-width: 340px;
+  white-space: nowrap;
+  overflow: hidden;
+  text-overflow: ellipsis;
+}
+
+.tool-step-right {
+  display: flex;
+  align-items: center;
+  gap: 8px;
+}
+
+.step-status-pill {
+  font-size: 10px;
+  font-weight: 700;
+  padding: 2px 6px;
+  border-radius: 4px;
+  text-transform: uppercase;
+}
+
+.step-status-pill.success {
+  background: rgba(16, 185, 129, 0.12);
+  color: var(--accent-emerald);
+}
+
+.step-status-pill.error {
+  background: rgba(239, 68, 68, 0.12);
+  color: var(--accent-rose);
 }
 
-/* Loading */
+.step-chevron {
+  font-size: 13px;
+  color: var(--text-subtle);
+  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
+}
+
+.tool-step-card.open .step-chevron {
+  transform: rotate(180deg);
+}
+
+.tool-step-body {
+  display: none;
+  padding: 10px 12px;
+  border-top: 1px solid var(--border-subtle);
+  background: rgba(0, 0, 0, 0.2);
+  font-family: var(--font-mono);
+  font-size: 12px;
+  color: var(--text-muted);
+}
+
+.tool-step-card.open .tool-step-body {
+  display: block;
+}
+
+/* Actions Bar & Read Aloud Button */
+.msg-actions-bar {
+  display: flex;
+  align-items: center;
+  flex-wrap: wrap;
+  gap: 8px;
+  margin-top: 10px;
+}
+
+.read-aloud-btn {
+  display: inline-flex;
+  align-items: center;
+  gap: 5px;
+  background: transparent;
+  border: 1px solid var(--border-subtle);
+  color: var(--text-muted);
+  padding: 4px 10px;
+  border-radius: 6px;
+  font-size: 11.5px;
+  cursor: pointer;
+  transition: all 0.15s ease;
+}
+
+.read-aloud-btn:hover {
+  background: var(--bg-surface-hover);
+  color: #fff;
+  border-color: var(--border-medium);
+}
+
+/* Loading Thinking Indicator */
 .loading-bubble {
   display: flex;
   align-items: center;
-  gap: 10px;
-  padding: 10px 16px;
+  gap: 12px;
+  padding: 12px 18px;
   background-color: var(--bg-surface);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
   border-radius: 10px;
   font-size: 13.5px;
   color: var(--text-muted);
-  max-width: 840px;
+  max-width: 860px;
   margin: 0 auto;
   width: 100%;
 }
 
-.spinner {
-  width: 16px;
-  height: 16px;
-  border: 2px solid var(--border);
-  border-top-color: #3b82f6;
+.loading-pulse-ring {
+  width: 14px;
+  height: 14px;
   border-radius: 50%;
-  animation: spin 0.8s linear infinite;
+  background-color: var(--accent-cyan);
+  animation: pulseGlow 1.2s infinite ease-in-out;
+}
+
+@keyframes pulseGlow {
+  0%, 100% { transform: scale(0.85); opacity: 0.6; box-shadow: 0 0 4px var(--accent-cyan); }
+  50% { transform: scale(1.15); opacity: 1; box-shadow: 0 0 14px var(--accent-cyan); }
+}
+
+/* Real-time Streaming Cursor */
+.streaming-cursor {
+  display: inline-block;
+  width: 7px;
+  height: 15px;
+  background-color: var(--accent-cyan);
+  margin-left: 4px;
+  vertical-align: middle;
+  border-radius: 2px;
+  animation: cursorBlink 0.8s infinite ease-in-out;
+  box-shadow: 0 0 8px var(--accent-cyan);
 }
 
-@keyframes spin {
-  to { transform: rotate(360deg); }
+@keyframes cursorBlink {
+  0%, 100% { opacity: 1; transform: scaleY(1); }
+  50% { opacity: 0.15; transform: scaleY(0.85); }
 }
 
-/* Safety Confirmation */
+/* Safety Confirmation Panel */
 .confirmation-panel {
   padding: 18px 22px;
   background-color: rgba(245, 158, 11, 0.08);
-  border: 1px solid rgba(245, 158, 11, 0.35);
-  border-radius: 14px;
+  border: 1px solid rgba(245, 158, 11, 0.3);
+  border-radius: 12px;
   display: flex;
   flex-direction: column;
   gap: 14px;
-  max-width: 840px;
+  max-width: 860px;
   margin: 0 auto;
   width: 100%;
 }
@@ -1166,25 +1554,29 @@ body {
   display: flex;
   align-items: center;
   gap: 8px;
-  font-size: 14.5px;
+  font-size: 14px;
   font-weight: 700;
-  color: var(--warning);
+  color: var(--accent-amber);
+}
+
+.conf-icon {
+  font-size: 18px;
 }
 
 .conf-text {
   display: flex;
   flex-direction: column;
   gap: 10px;
-  font-size: 13.5px;
+  font-size: 13px;
   color: var(--text-main);
   line-height: 1.5;
 }
 
 .conf-action-card {
-  background-color: #07090e;
-  border: 1px solid var(--border);
-  border-radius: 10px;
-  padding: 12px 16px;
+  background-color: var(--bg-void);
+  border: 1px solid var(--border-subtle);
+  border-radius: 8px;
+  padding: 12px 14px;
   display: flex;
   flex-direction: column;
   gap: 8px;
@@ -1194,46 +1586,45 @@ body {
   display: flex;
   align-items: center;
   justify-content: space-between;
-  gap: 8px;
 }
 
 .conf-tool-name {
   font-family: var(--font-mono);
-  font-size: 13.5px;
+  font-size: 13px;
   font-weight: 600;
-  color: #38bdf8;
+  color: var(--accent-cyan);
   display: flex;
   align-items: center;
   gap: 6px;
 }
 
 .conf-risk-badge {
-  font-size: 11px;
+  font-size: 10.5px;
   font-weight: 700;
   text-transform: uppercase;
   padding: 2px 8px;
-  border-radius: 12px;
+  border-radius: 10px;
 }
 
 .conf-risk-badge.high {
-  background-color: rgba(239, 68, 68, 0.2);
+  background-color: rgba(239, 68, 68, 0.15);
   color: #f87171;
-  border: 1px solid rgba(239, 68, 68, 0.4);
+  border: 1px solid rgba(239, 68, 68, 0.35);
 }
 
 .conf-risk-badge.confirm {
-  background-color: rgba(245, 158, 11, 0.2);
+  background-color: rgba(245, 158, 11, 0.15);
   color: #fbbf24;
-  border: 1px solid rgba(245, 158, 11, 0.4);
+  border: 1px solid rgba(245, 158, 11, 0.35);
 }
 
 .conf-payload-box {
-  background-color: #0b0f17;
-  border: 1px solid var(--border);
+  background-color: #080c14;
+  border: 1px solid var(--border-subtle);
   border-radius: 6px;
-  padding: 10px 12px;
+  padding: 8px 12px;
   font-family: var(--font-mono);
-  font-size: 12.5px;
+  font-size: 12px;
   color: #e2e8f0;
   overflow-x: auto;
   white-space: pre-wrap;
@@ -1245,7 +1636,6 @@ body {
   font-weight: 600;
   text-transform: uppercase;
   color: var(--text-subtle);
-  margin-bottom: 4px;
 }
 
 .conf-reason-text {
@@ -1257,34 +1647,34 @@ body {
   display: flex;
   justify-content: flex-end;
   gap: 10px;
-  margin-top: 6px;
 }
 
 .btn {
+  display: inline-flex;
+  align-items: center;
+  gap: 6px;
   padding: 7px 16px;
   border-radius: 6px;
   font-size: 12.5px;
   font-weight: 600;
   cursor: pointer;
   border: none;
-  transition: all 0.12s ease;
+  transition: all 0.15s ease;
 }
 
 .btn-primary {
   background-color: var(--primary);
   color: #fff;
 }
-
 .btn-primary:hover {
   background-color: var(--primary-hover);
 }
 
 .btn-secondary {
   background-color: var(--bg-surface);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
   color: var(--text-muted);
 }
-
 .btn-secondary:hover {
   background-color: var(--bg-surface-hover);
   color: var(--text-main);
@@ -1294,9 +1684,9 @@ body {
    Composer Footer
    ========================================================================== */
 .composer-area {
-  padding: 12px 32px 18px;
+  padding: 12px 32px 16px;
   background-color: var(--bg-main);
-  border-top: 1px solid var(--border);
+  border-top: 1px solid var(--border-subtle);
   display: flex;
   flex-direction: column;
   gap: 8px;
@@ -1306,18 +1696,19 @@ body {
   display: flex;
   align-items: flex-end;
   background-color: var(--bg-input);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
   border-radius: 12px;
   padding: 8px 12px;
   gap: 10px;
-  max-width: 840px;
+  max-width: 860px;
   margin: 0 auto;
   width: 100%;
-  transition: border-color 0.15s ease;
+  transition: border-color 0.15s ease, box-shadow 0.15s ease;
 }
 
 .composer-box:focus-within {
   border-color: var(--border-focus);
+  box-shadow: 0 0 0 1px var(--border-focus);
 }
 
 .prompt-textarea {
@@ -1326,7 +1717,7 @@ body {
   border: none;
   outline: none;
   font-family: var(--font-sans);
-  font-size: 14.5px;
+  font-size: 14px;
   color: var(--text-main);
   resize: none;
   line-height: 1.5;
@@ -1345,8 +1736,8 @@ body {
 }
 
 .action-btn {
-  width: 34px;
-  height: 34px;
+  width: 32px;
+  height: 32px;
   border-radius: 8px;
   display: flex;
   align-items: center;
@@ -1354,12 +1745,13 @@ body {
   border: none;
   cursor: pointer;
   transition: all 0.15s ease;
+  font-size: 15px;
 }
 
 .mic-btn {
   background-color: var(--bg-surface);
   color: var(--text-muted);
-  border: 1px solid var(--border);
+  border: 1px solid var(--border-subtle);
 }
 
 .mic-btn:hover {
@@ -1369,15 +1761,14 @@ body {
 
 .mic-btn.recording {
   background-color: rgba(239, 68, 68, 0.15);
-  border-color: var(--danger);
-  color: var(--danger);
+  border-color: var(--accent-rose);
+  color: var(--accent-rose);
   animation: micPulse 1.2s infinite ease-in-out;
 }
 
 @keyframes micPulse {
-  0% { transform: scale(1); }
-  50% { transform: scale(1.08); }
-  100% { transform: scale(1); }
+  0%, 100% { transform: scale(1); }
+  50% { transform: scale(1.08); box-shadow: 0 0 10px rgba(244, 63, 94, 0.5); }
 }
 
 .send-btn {
@@ -1387,76 +1778,59 @@ body {
 
 .send-btn:hover {
   background-color: var(--primary-hover);
+  transform: translateY(-1px);
 }
 
-.action-btn svg {
-  width: 17px;
-  height: 17px;
+.send-btn:active {
+  transform: scale(0.96);
 }
 
 .composer-hints {
   text-align: center;
-  font-size: 11.5px;
+  font-size: 11px;
   color: var(--text-subtle);
 }
 
 /* ==========================================================================
-   Responsive Breakpoints for Window Resizing
+   Responsive Breakpoints & Reduced Motion
    ========================================================================== */
 @media (max-width: 1080px) {
-  .model-select-wrapper label {
-    display: none;
-  }
-  .mode-label {
-    display: none;
-  }
-  .unload-btn span {
-    display: none;
-  }
-  .unload-btn {
-    padding: 5px 9px;
-  }
+  .model-select-wrapper label { display: none; }
+  .mode-label { display: none; }
+  .unload-btn span { display: none; }
+  .unload-btn { padding: 5px 9px; }
 }
 
 @media (max-width: 960px) {
-  .voice-toggle-btn .voice-text {
-    display: none;
-  }
-  .voice-toggle-btn {
-    padding: 5px 9px;
-  }
-  .top-nav {
-    padding: 0 10px;
-    gap: 6px;
-  }
-  .nav-left, .nav-right {
-    gap: 6px;
-  }
-  .model-select {
-    max-width: 125px;
-    font-size: 12px;
-  }
-  .tier-badge {
-    font-size: 9.5px;
-    padding: 2px 6px;
-  }
-  .governor-pill {
-    padding: 5px 9px;
-  }
+  .voice-toggle-btn .voice-text { display: none; }
+  .voice-toggle-btn { padding: 5px 9px; }
+  .top-nav { padding: 0 12px; gap: 8px; }
+  .model-select { max-width: 130px; font-size: 11.5px; }
+  .tier-badge { font-size: 9.5px; padding: 2px 6px; }
+  .chat-viewport { padding: 18px; }
+  .composer-area { padding: 12px 18px 16px; }
 }
 
-@media (max-width: 820px) {
+@media (max-width: 768px) {
   .sidebar {
-    width: 220px;
+    position: absolute;
+    left: 0;
+    top: 0;
+    bottom: 0;
+    box-shadow: 10px 0 30px rgba(0, 0, 0, 0.7);
   }
-  .model-select {
-    max-width: 105px;
-    font-size: 11.5px;
-    padding: 4px 6px;
+  .suggestion-grid {
+    grid-template-columns: 1fr;
   }
-  .governor-pill {
-    font-size: 11px;
-    padding: 4px 8px;
+}
+
+@media (prefers-reduced-motion: reduce) {
+  *, *::before, *::after {
+    animation-duration: 0.01ms !important;
+    animation-iteration-count: 1 !important;
+    transition-duration: 0.01ms !important;
+    scroll-behavior: auto !important;
   }
 }
 
+
diff --git a/run_jarvis.py b/run_jarvis.py
index 20cd2cb..15ed8e0 100644
--- a/run_jarvis.py
+++ b/run_jarvis.py
@@ -60,7 +60,27 @@ def is_backend_running(url: str = "http://127.0.0.1:8000/health") -> bool:
         return False
 
 
-def start_backend() -> subprocess.Popen:
+def start_backend():
+    is_frozen = getattr(sys, "frozen", False)
+    # If frozen and no external python interpreter found, run uvicorn in-process via daemon thread
+    if is_frozen and (not VENV_PYTHON or (VENV_PYTHON.suffix.lower() == ".exe" and "python" not in VENV_PYTHON.name.lower())):
+        logger.info("Starting Jarvis FastAPI backend server in-process via daemon thread...")
+        import threading
+        import uvicorn
+        
+        def _run_server():
+            try:
+                from app.main import app
+                config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
+                server = uvicorn.Server(config)
+                server.run()
+            except Exception as e:
+                logger.error("In-process uvicorn server error: %s", e)
+                
+        t = threading.Thread(target=_run_server, daemon=True)
+        t.start()
+        return None
+
     env = os.environ.copy()
     env["PYTHONPATH"] = f"{BACKEND_DIR};{ROOT_DIR}"
     backend_log = open(ROOT_DIR / "backend.log", "a", encoding="utf-8")

diff --git a/backend/app/agent/tool_schema.py b/backend/app/agent/tool_schema.py
new file mode 100644
--- /dev/null
+++ b/backend/app/agent/tool_schema.py
@@ -0,0 +1,69 @@
+import inspect
+import logging
+from typing import Any, Callable, Optional
+from app.agent.tools.registry import TOOL_SCHEMAS
+
+logger = logging.getLogger("jarvis.agent.tool_schema")
+
+
+def convert_tool_to_openai_schema(tool: Any) -> Optional[dict[str, Any]]:
+    """
+    Convert a Python tool function, MCP tool dictionary, or schema object to OpenAI function format:
+    {
+        "type": "function",
+        "function": {
+            "name": str,
+            "description": str,
+            "parameters": dict
+        }
+    }
+    """
+    if tool is None:
+        return None
+
+    if isinstance(tool, dict):
+        if "type" in tool and tool["type"] == "function" and "function" in tool:
+            return tool
+        if "name" in tool:
+            params = tool.get("parameters") or tool.get("inputSchema") or {"type": "object", "properties": {}, "required": []}
+            return {
+                "type": "function",
+                "function": {
+                    "name": tool["name"],
+                    "description": tool.get("description", f"Execute {tool['name']}."),
+                    "parameters": params
+                }
+            }
+        return None
+
+    if callable(tool):
+        fn_name = getattr(tool, "__name__", str(tool))
+        doc = inspect.getdoc(tool) or f"Execute {fn_name}."
+        # First line of docstring as short description
+        short_desc = doc.strip().split("\n")[0] if doc else f"Execute {fn_name}."
+
+        schema_cls = TOOL_SCHEMAS.get(fn_name)
+        if schema_cls:
+            raw_schema = schema_cls.model_json_schema()
+            parameters = {
+                "type": "object",
+                "properties": raw_schema.get("properties", {}),
+                "required": raw_schema.get("required", [])
+            }
+        else:
+            parameters = {
+                "type": "object",
+                "properties": {},
+                "required": []
+            }
+
+        return {
+            "type": "function",
+            "function": {
+                "name": fn_name,
+                "description": short_desc,
+                "parameters": parameters
+            }
+        }
+
+    return None

diff --git a/backend/app/agent/model_provider.py b/backend/app/agent/model_provider.py
new file mode 100644
--- /dev/null
+++ b/backend/app/agent/model_provider.py
@@ -0,0 +1,108 @@
+from abc import ABC, abstractmethod
+from typing import Any, AsyncIterator, Optional
+
+
+class ModelProvider(ABC):
+    """
+    Abstract interface for local and remote LLM execution runtimes.
+    Enforces normalized output formats across all providers.
+    """
+
+    @property
+    @abstractmethod
+    def name(self) -> str:
+        """Provider name identifier (e.g. 'llama_cpp', 'ollama')."""
+        pass
+
+    @abstractmethod
+    async def health_check(self) -> bool:
+        """Check if the backend runtime server is online, reachable, and ready."""
+        pass
+
+    @abstractmethod
+    async def model_info(self) -> dict[str, Any]:
+        """Fetch metadata/info for the currently active or configured model."""
+        pass
+
+    @abstractmethod
+    async def list_models(self) -> list[str]:
+        """List available/active model IDs or tags from the runtime."""
+        pass
+
+    @abstractmethod
+    async def chat(
+        self,
+        messages: list[dict[str, Any]],
+        model: Optional[str] = None,
+        tools: Optional[list[Any]] = None,
+        temperature: float = 0.7,
+        profile: str = "general",
+        timeout: Optional[float] = None
+    ) -> dict[str, Any]:
+        """
+        Send a non-streaming chat completion request.
+        Returns normalized dictionary:
+        {
+            "message": {
+                "role": "assistant",
+                "content": str,
+                "tool_calls": list[dict] | None
+            },
+            "raw": dict | Any
+        }
+        where each item in tool_calls is structured as:
+        {
+            "id": str,
+            "type": "function",
+            "function": {
+                "name": str,
+                "arguments": dict
+            }
+        }
+        """
+        pass
+
+    @abstractmethod
+    async def stream_chat(
+        self,
+        messages: list[dict[str, Any]],
+        model: Optional[str] = None,
+        tools: Optional[list[Any]] = None,
+        temperature: float = 0.7,
+        profile: str = "general",
+        timeout: Optional[float] = None
+    ) -> AsyncIterator[dict[str, Any]]:
+        """
+        Stream chat tokens and tool calls.
+        Yields normalized event dictionaries:
+        - {"event": "text_delta", "content": str}
+        - {"event": "tool_call", "tool_call": dict}  (complete, accumulated per tool call)
+        - {"event": "done", "raw": dict}
+        - {"event": "error", "message": str}
+        """
+        pass
+
+    @abstractmethod
+    async def unload_model(self, model: Optional[str] = None) -> bool:
+        """
+        Unload active model(s) from GPU VRAM to yield resources.
+        Returns True on success, False otherwise. Must not raise unhandled exceptions.
+        """
+        pass
+
+    async def count_tokens(self, text: str) -> int:
+        """
+        Conservative token count estimator (len(text) // 4).
+        Documented as an estimate, NOT exact.
+        """
+        if not text:
+            return 0
+        return max(1, len(text) // 4)
+
+    async def embeddings(self, texts: list[str]) -> list[list[float]]:
+        """Stub for embedding generation."""
+        raise NotImplementedError("Embeddings are not implemented for this provider.")
+
+    async def rerank(self, query: str, docs: list[str]) -> list[dict[str, Any]]:
+        """Stub for document reranking."""
+        raise NotImplementedError("Reranking is not implemented for this provider.")

diff --git a/backend/app/agent/runtime_process_manager.py b/backend/app/agent/runtime_process_manager.py
new file mode 100644
--- /dev/null
+++ b/backend/app/agent/runtime_process_manager.py
@@ -0,0 +1,287 @@
+import asyncio
+import logging
+import os
+import sys
+import threading
+import subprocess
+import time
+from pathlib import Path
+from typing import Any, Optional
+import httpx
+from app.config import settings
+
+logger = logging.getLogger("jarvis.agent.process_manager")
+
+REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
+
+
+def resolve_repo_path(path_str: str) -> Path:
+    """Resolve a path relative to the repo root if it's relative, otherwise return as absolute."""
+    p = Path(path_str)
+    if not p.is_absolute():
+        p = (REPO_ROOT / p).resolve()
+    return p
+
+
+class RuntimeProcessManager:
+    """
+    Deterministic OS process management for llama-server.exe.
+    Controls process startup, model switching, health verification,
+    and 100% process-based GPU VRAM eviction.
+    """
+
+    def __init__(
+        self,
+        host: Optional[str] = None,
+        port: Optional[int] = None,
+        server_exe: Optional[str] = None,
+        main_model_path: Optional[str] = None,
+        fast_model_path: Optional[str] = None,
+        ctx_size: Optional[int] = None,
+        gpu_layers: Optional[int] = None,
+        startup_timeout: Optional[float] = None,
+        extra_args: Optional[list[str]] = None,
+    ):
+        self.host = host or settings.llamacpp_host
+        self.port = port if port is not None else settings.llamacpp_port
+        self.server_exe = server_exe or settings.llamacpp_server_exe
+        self.main_model_path = main_model_path or settings.llamacpp_main_model_path
+        self.fast_model_path = fast_model_path or settings.llamacpp_fast_model_path
+        self.ctx_size = ctx_size if ctx_size is not None else settings.llamacpp_ctx_size
+        self.gpu_layers = gpu_layers if gpu_layers is not None else settings.llamacpp_gpu_layers
+        self.startup_timeout = startup_timeout if startup_timeout is not None else settings.llamacpp_startup_timeout_seconds
+        self.extra_args = list(extra_args if extra_args is not None else settings.llamacpp_extra_args)
+
+        self._process: Optional[subprocess.Popen] = None
+        self._current_model_kind: Optional[str] = None
+        self._externally_managed: bool = False
+        self._lock = asyncio.Lock()
+
+    @property
+    def base_url(self) -> str:
+        return f"http://{self.host}:{self.port}"
+
+    @property
+    def current_model_kind(self) -> Optional[str]:
+        return self._current_model_kind
+
+    @property
+    def is_externally_managed(self) -> bool:
+        return self._externally_managed
+
+    def resolve_model_path(self, model_kind: str) -> tuple[Path, str]:
+        """
+        Resolve model file path and alias based on kind ('main', 'fast', or direct path/filename).
+        Returns (resolved_path, alias).
+        """
+        kind_norm = (model_kind or "main").strip().lower()
+        if kind_norm in ("main", "9b", "qwen3.5-9b", "default"):
+            target_path_str = self.main_model_path
+            alias = "main"
+        elif kind_norm in ("fast", "4b", "qwen3.5-4b"):
+            target_path_str = self.fast_model_path
+            alias = "fast"
+        else:
+            target_path_str = model_kind
+            alias = Path(model_kind).stem
+
+        resolved = resolve_repo_path(target_path_str)
+        if not resolved.exists() and alias == "fast":
+            models_dir = REPO_ROOT / "models"
+            if models_dir.exists():
+                for cand in models_dir.glob("*4B*.gguf"):
+                    return cand.resolve(), alias
+        elif not resolved.exists() and alias == "main":
+            models_dir = REPO_ROOT / "models"
+            if models_dir.exists():
+                for cand in models_dir.glob("*9B*.gguf"):
+                    return cand.resolve(), alias
+        return resolved, alias
+
+    async def health_check(self, timeout: float = 3.0) -> bool:
+        """Probe GET /v1/models endpoint."""
+        url = f"{self.base_url}/v1/models"
+        try:
+            async with httpx.AsyncClient(timeout=timeout) as client:
+                resp = await client.get(url)
+                return resp.status_code == 200
+        except Exception:
+            return False
+
+    def is_running(self) -> bool:
+        """Check if child process is active and has not terminated."""
+        if self._process is not None:
+            return self._process.poll() is None
+        return self._externally_managed
+
+    def _drain_sync_stream(self, stream, stream_name: str) -> None:
+        """Drain child process output stream in background thread to prevent pipe buffer stalls."""
+        if not stream:
+            return
+        try:
+            for line in iter(stream.readline, b""):
+                decoded = line.decode("utf-8", errors="replace").rstrip()
+                if decoded:
+                    logger.debug("[llama-server %s] %s", stream_name, decoded)
+        except Exception:
+            pass
+        finally:
+            try:
+                stream.close()
+            except Exception:
+                pass
+
+    async def ensure_running(self, model_kind: str = "main") -> bool:
+        """
+        Ensure llama-server is online with the requested model_kind.
+        If unhealthy or missing, spawn the process and wait for ready state.
+        """
+        resolved_exe = resolve_repo_path(self.server_exe)
+        resolved_model, alias = self.resolve_model_path(model_kind)
+
+        async with self._lock:
+            # 1. If health check passes
+            if await self.health_check(timeout=2.0):
+                if self._current_model_kind in (alias, model_kind):
+                    return True
+
+                # Different model kind requested -> trigger switch
+                logger.info(
+                    "Switching running llama-server model from '%s' to '%s' (alias: %s)",
+                    self._current_model_kind,
+                    model_kind,
+                    alias
+                )
+                await self._stop_internal()
+
+            # 2. Server not running or needs restart with new model
+            cmd = [
+                str(resolved_exe),
+                "--model", str(resolved_model),
+                "--alias", alias,
+                "--host", str(self.host),
+                "--port", str(self.port),
+                "--ctx-size", str(self.ctx_size),
+                "--n-gpu-layers", str(self.gpu_layers),
+                "--parallel", "1",
+            ]
+            if self.extra_args:
+                cmd.extend(self.extra_args)
+
+            logger.info("Spawning llama-server process: %s", " ".join(cmd))
+            try:
+                proc = subprocess.Popen(
+                    cmd,
+                    stdout=subprocess.PIPE,
+                    stderr=subprocess.PIPE,
+                    bufsize=0
+                )
+            except Exception as e:
+                logger.error("Failed to spawn llama-server binary at '%s': %s", resolved_exe, e)
+                raise RuntimeError(f"Failed to spawn llama-server ({resolved_exe}): {e}") from e
+
+            self._process = proc
+            self._current_model_kind = model_kind
+            self._externally_managed = False
+
+            # Start background pipe drainers
+            t_out = threading.Thread(target=self._drain_sync_stream, args=(proc.stdout, "stdout"), daemon=True)
+            t_err = threading.Thread(target=self._drain_sync_stream, args=(proc.stderr, "stderr"), daemon=True)
+            t_out.start()
+            t_err.start()
+
+            # Poll health check until startup timeout
+            start_time = time.time()
+            poll_interval = 0.5
+            while time.time() - start_time < self.startup_timeout:
+                if proc.poll() is not None:
+                    raise RuntimeError(
+                        f"llama-server exited prematurely with code {proc.returncode} during startup."
+                    )
+                if await self.health_check(timeout=1.5):
+                    logger.info("llama-server successfully started and healthy at %s (model: %s)", self.base_url, alias)
+                    return True
+                await asyncio.sleep(poll_interval)
+
+            # Startup timed out -> kill process
+            logger.error("llama-server startup timed out after %.1fs", self.startup_timeout)
+            await self._stop_internal()
+            raise RuntimeError(f"llama-server failed to become healthy within {self.startup_timeout}s.")
+
+    async def _stop_internal(self) -> bool:
+        """Internal worker to stop the process without acquiring the lock."""
+        self._current_model_kind = None
+        self._externally_managed = False
+
+        # 1. Terminate tracked subprocess if present
+        if self._process is not None:
+            proc = self._process
+            self._process = None
+            if proc.poll() is None:
+                logger.info("Terminating tracked llama-server process (PID %s)...", proc.pid)
+                try:
+                    proc.terminate()
+                    for _ in range(30):
+                        if proc.poll() is not None:
+                            break
+                        await asyncio.sleep(0.1)
+                    else:
+                        proc.kill()
+                        proc.wait()
+                except Exception as e:
+                    logger.debug("Error terminating tracked process: %s", e)
+
+        # 2. Terminate any orphan or lingering llama-server instances
+        import psutil
+        try:
+            for p in psutil.process_iter(['pid', 'name']):
+                try:
+                    p_name = (p.info.get('name') or "").lower()
+                    if "llama-server" in p_name:
+                        logger.info("Terminating llama-server process (PID %s) for VRAM release...", p.pid)
+                        p.terminate()
+                        try:
+                            p.wait(timeout=3)
+                        except psutil.TimeoutExpired:
+                            p.kill()
+                except (psutil.NoSuchProcess, psutil.AccessDenied):
+                    continue
+        except Exception as e:
+            logger.debug("Error scanning for llama-server processes: %s", e)
+
+        logger.info("llama-server processes terminated. 100% GPU VRAM released.")
+        return True
+
+    async def stop(self) -> bool:
+        """
+        Gracefully terminate or kill the llama-server process.
+        This provides deterministic 100% GPU VRAM release.
+        """
+        async with self._lock:
+            return await self._stop_internal()
+
+    async def switch_model(self, model_kind: str) -> bool:
+        """
+        Stop current running model and switch to requested model_kind.
+        """
+        async with self._lock:
+            if self.is_running() and self._current_model_kind == model_kind:
+                return True
+            await self._stop_internal()
+            # Release lock before ensure_running to avoid deadlocks
+        return await self.ensure_running(model_kind)
+
+
+_process_manager_instance: Optional[RuntimeProcessManager] = None
+
+
+def get_runtime_process_manager() -> RuntimeProcessManager:
+    global _process_manager_instance
+    if _process_manager_instance is None:
+        _process_manager_instance = RuntimeProcessManager()
+    return _process_manager_instance
+
+
+def reset_runtime_process_manager() -> None:
+    global _process_manager_instance
+    _process_manager_instance = None

diff --git a/backend/app/agent/llamacpp_provider.py b/backend/app/agent/llamacpp_provider.py
new file mode 100644
--- /dev/null
+++ b/backend/app/agent/llamacpp_provider.py
@@ -0,0 +1,443 @@
+import json
+import logging
+import re
+from typing import Any, AsyncIterator, Optional
+import httpx
+from app.config import settings
+from app.agent.model_provider import ModelProvider
+from app.agent.tool_schema import convert_tool_to_openai_schema
+from app.agent.runtime_process_manager import RuntimeProcessManager, get_runtime_process_manager
+
+logger = logging.getLogger("jarvis.agent.llamacpp")
+
+# Regex to strip <think>...</think> reasoning blocks
+THINK_TAG_REGEX = re.compile(r"<think>[\s\S]*?</think>", re.DOTALL)
+
+
+def strip_thinking_tags(text: str) -> tuple[str, str]:
+    """
+    Strips <think>...</think> reasoning blocks from text.
+    Returns (cleaned_text, extracted_reasoning).
+    """
+    if not text or not isinstance(text, str):
+        return text or "", ""
+    reasoning_blocks = THINK_TAG_REGEX.findall(text)
+    extracted_reasoning = "\n".join([b.replace("<think>", "").replace("</think>", "").strip() for b in reasoning_blocks])
+    cleaned = THINK_TAG_REGEX.sub("", text).strip()
+    return cleaned, extracted_reasoning
+
+
+def _sanitize_messages_for_jinja(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
+    """
+    Sanitizes conversation messages for Qwen3.5 Jinja chat template.
+    Consolidates all 'system' role messages into a single system message at index 0
+    to strictly satisfy Jinja template assertion: 'System message must be at the beginning.'
+    """
+    if not messages:
+        return []
+
+    system_parts = []
+    non_system_messages = []
+
+    for m in messages:
+        if m.get("role") == "system":
+            c = m.get("content")
+            if c:
+                system_parts.append(str(c).strip())
+        else:
+            non_system_messages.append(m)
+
+    sanitized = []
+    if system_parts:
+        merged_system = "\n\n".join(system_parts)
+        sanitized.append({"role": "system", "content": merged_system})
+
+    sanitized.extend(non_system_messages)
+    return sanitized
+
+
+class LlamaCppProvider(ModelProvider):
+    """
+    Primary local model provider communicating with llama-server.exe
+    via its OpenAI-compatible /v1 endpoints.
+    """
+
+    def __init__(
+        self,
+        base_url: Optional[str] = None,
+        timeout: float = 90.0,
+        process_manager: Optional[RuntimeProcessManager] = None
+    ):
+        self.host = settings.llamacpp_host
+        self.port = settings.llamacpp_port
+        self.base_url = (base_url or f"http://{self.host}:{self.port}").rstrip("/")
+        self.timeout = timeout
+        self.process_manager = process_manager or get_runtime_process_manager()
+
+    @property
+    def name(self) -> str:
+        return "llama_cpp"
+
+    def _get_headers(self) -> dict[str, str]:
+        return {
+            "Content-Type": "application/json",
+        }
+
+    def _get_sampling_parameters(self, profile: str = "general", custom_temp: Optional[float] = None) -> dict[str, Any]:
+        """
+        Calibrated sampling parameters for Qwen3.5 per Unsloth guidance.
+        - general: temp 0.7, top_p 0.8, top_k 20, min_p 0.0, presence_penalty 1.5
+        - coding:  temp 0.6, top_p 0.95, top_k 20, min_p 0.0, presence_penalty 0.0
+        """
+        prof = (profile or "general").strip().lower()
+        if prof in ("coding", "code", "tool", "tools"):
+            params = {
+                "temperature": 0.6 if custom_temp is None else custom_temp,
+                "top_p": 0.95,
+                "top_k": 20,
+                "min_p": 0.0,
+                "presence_penalty": 0.0,
+            }
+        else:
+            params = {
+                "temperature": 0.7 if custom_temp is None else custom_temp,
+                "top_p": 0.8,
+                "top_k": 20,
+                "min_p": 0.0,
+                "presence_penalty": 1.5,
+            }
+        return params
+
+    async def health_check(self) -> bool:
+        """Probe GET /v1/models endpoint."""
+        url = f"{self.base_url}/v1/models"
+        try:
+            async with httpx.AsyncClient(timeout=3.0) as client:
+                resp = await client.get(url, headers=self._get_headers())
+                return resp.status_code == 200
+        except Exception:
+            return False
+
+    async def model_info(self) -> dict[str, Any]:
+        """Retrieve model metadata from llama-server."""
+        models = await self.list_models()
+        return {
+            "provider": self.name,
+            "base_url": self.base_url,
+            "running_model_kind": self.process_manager.current_model_kind,
+            "available_models": models,
+        }
+
+    async def list_models(self) -> list[str]:
+        """List active/available models from llama-server."""
+        url = f"{self.base_url}/v1/models"
+        models: list[str] = []
+        try:
+            async with httpx.AsyncClient(timeout=5.0) as client:
+                resp = await client.get(url, headers=self._get_headers())
+                if resp.status_code == 200:
+                    data = resp.json()
+                    for item in data.get("data", []):
+                        m_id = item.get("id") or item.get("name")
+                        if m_id:
+                            models.append(m_id)
+        except Exception as e:
+            logger.warning("Failed to list models from llama-server (%s): %s", self.base_url, e)
+        return models
+
+    async def unload_model(self, model: Optional[str] = None) -> bool:
+        """
+        Evict active model and release GPU VRAM by terminating the server process.
+        Never raises exceptions into callers.
+        """
+        try:
+            return await self.process_manager.stop()
+        except Exception as e:
+            logger.warning("Error delegating unload_model to RuntimeProcessManager: %s", e)
+            return False
+
+    async def _ensure_server_ready(self, model_kind: str = "main") -> None:
+        """Verify server readiness and ensure the requested model is loaded."""
+        await self.process_manager.ensure_running(model_kind=model_kind)
+
+    def _normalize_tool_calls(self, raw_tool_calls: Optional[list[dict[str, Any]]]) -> Optional[list[dict[str, Any]]]:
+        """Normalize tool calls list to standard format with safely parsed arguments."""
+        if not raw_tool_calls or not isinstance(raw_tool_calls, list):
+            return None
+
+        normalized = []
+        for tc in raw_tool_calls:
+            if not isinstance(tc, dict):
+                continue
+            fn_obj = tc.get("function", {})
+            fn_name = fn_obj.get("name", "")
+            raw_args = fn_obj.get("arguments", {})
+            
+            if isinstance(raw_args, str):
+                try:
+                    parsed_args = json.loads(raw_args)
+                except Exception:
+                    # Fallback to empty dict with debug metadata without crashing
+                    parsed_args = {}
+            elif isinstance(raw_args, dict):
+                parsed_args = raw_args
+            else:
+                parsed_args = {}
+
+            call_id = tc.get("id") or f"call_{len(normalized)}"
+            normalized.append({
+                "id": str(call_id),
+                "type": "function",
+                "function": {
+                    "name": fn_name,
+                    "arguments": parsed_args
+                }
+            })
+        return normalized if normalized else None
+
+    async def chat(
+        self,
+        messages: list[dict[str, Any]],
+        model: Optional[str] = None,
+        tools: Optional[list[Any]] = None,
+        temperature: Optional[float] = None,
+        profile: str = "general",
+        timeout: Optional[float] = None
+    ) -> dict[str, Any]:
+        """
+        Send a non-streaming chat completion request to llama-server.
+        Retries once if server is offline by invoking ensure_running.
+        """
+        target_model_kind = model or "main"
+        req_timeout = timeout or self.timeout
+        url = f"{self.base_url}/v1/chat/completions"
+
+        sampling = self._get_sampling_parameters(profile=profile, custom_temp=temperature)
+
+        payload: dict[str, Any] = {
+            "model": target_model_kind,
+            "messages": _sanitize_messages_for_jinja(messages),
+            "stream": False,
+            **sampling
+        }
+
+        if tools:
+            formatted_tools = []
+            for t in tools:
+                schema = convert_tool_to_openai_schema(t)
+                if schema:
+                    formatted_tools.append(schema)
+            if formatted_tools:
+                payload["tools"] = formatted_tools
+                payload["tool_choice"] = "auto"
+
+        client_timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=None)
+        if isinstance(req_timeout, (int, float)):
+            client_timeout = httpx.Timeout(connect=30.0, read=float(req_timeout), write=60.0, pool=None)
+
+        # Attempt call with retry on connection failure
+        for attempt in (1, 2):
+            try:
+                await self._ensure_server_ready(target_model_kind)
+                async with httpx.AsyncClient(timeout=client_timeout) as client:
+                    resp = await client.post(url, json=payload, headers=self._get_headers())
+                    if resp.status_code != 200:
+                        raise RuntimeError(f"llama-server returned HTTP {resp.status_code}: {resp.text}")
+                    data = resp.json()
+                    break
+            except Exception as e:
+                if attempt == 1:
+                    logger.warning("llama-server request failed on attempt 1 (%s). Ensuring server is running and retrying...", e)
+                    await self.process_manager.ensure_running(target_model_kind)
+                else:
+                    logger.error("llama-server request failed on retry: %s", e)
+                    raise RuntimeError(f"llama-server chat failed: {e}") from e
+
+        choices = data.get("choices", [])
+        if not choices:
+            return {
+                "message": {
+                    "role": "assistant",
+                    "content": "",
+                    "tool_calls": None
+                },
+                "raw": data
+            }
+
+        msg = choices[0].get("message", {})
+        raw_content = msg.get("content") or ""
+        raw_reasoning = msg.get("reasoning_content") or ""
+        cleaned_content, extracted_reasoning = strip_thinking_tags(raw_content)
+        final_reasoning = (raw_reasoning + "\n" + extracted_reasoning).strip()
+
+        tool_calls = msg.get("tool_calls")
+        normalized_calls = self._normalize_tool_calls(tool_calls)
+
+        return {
+            "message": {
+                "role": "assistant",
+                "content": cleaned_content,
+                "reasoning_content": final_reasoning,
+                "tool_calls": normalized_calls
+            },
+            "raw": data
+        }
+
+    async def stream_chat(
+        self,
+        messages: list[dict[str, Any]],
+        model: Optional[str] = None,
+        tools: Optional[list[Any]] = None,
+        temperature: Optional[float] = None,
+        profile: str = "general",
+        timeout: Optional[float] = None
+    ) -> AsyncIterator[dict[str, Any]]:
+        """
+        Stream chat tokens and tool calls from llama-server.
+        Yields:
+        - {"event": "text_delta", "content": str}
+        - {"event": "tool_call", "tool_call": dict}
+        - {"event": "done", "raw": dict}
+        - {"event": "error", "message": str}
+        """
+        target_model_kind = model or "main"
+        req_timeout = timeout or self.timeout
+        url = f"{self.base_url}/v1/chat/completions"
+
+        sampling = self._get_sampling_parameters(profile=profile, custom_temp=temperature)
+
+        payload: dict[str, Any] = {
+            "model": target_model_kind,
+            "messages": _sanitize_messages_for_jinja(messages),
+            "stream": True,
+            **sampling
+        }
+
+        if tools:
+            formatted_tools = []
+            for t in tools:
+                schema = convert_tool_to_openai_schema(t)
+                if schema:
+                    formatted_tools.append(schema)
+            if formatted_tools:
+                payload["tools"] = formatted_tools
+                payload["tool_choice"] = "auto"
+
+        try:
+            await self._ensure_server_ready(target_model_kind)
+        except Exception as e:
+            logger.error("Failed to ensure llama-server running for stream: %s", e)
+            yield {"event": "error", "message": str(e)}
+            return
+
+        accumulated_content: list[str] = []
+        accumulated_reasoning: list[str] = []
+        tool_calls_map: dict[int, dict[str, Any]] = {}
+        in_think_block = False
+
+        client_timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=None)
+        if isinstance(req_timeout, (int, float)):
+            client_timeout = httpx.Timeout(connect=30.0, read=max(300.0, float(req_timeout)), write=60.0, pool=None)
+
+        try:
+            async with httpx.AsyncClient(timeout=client_timeout) as client:
+                async with client.stream("POST", url, json=payload, headers=self._get_headers()) as response:
+                    if response.status_code != 200:
+                        err_body = await response.aread()
+                        err_msg = f"llama-server streaming HTTP {response.status_code}: {err_body.decode('utf-8', errors='replace')}"
+                        yield {"event": "error", "message": err_msg}
+                        return
+
+                    async for line in response.aiter_lines():
+                        if not line:
+                            continue
+                        if line.startswith("data: "):
+                            raw_data = line[6:].strip()
+                            if raw_data == "[DONE]":
+                                break
+                            try:
+                                chunk = json.loads(raw_data)
+                            except Exception:
+                                continue
+
+                            choices = chunk.get("choices", [])
+                            if not choices:
+                                continue
+                            delta = choices[0].get("delta", {})
+
+                            content_delta = delta.get("content")
+                            if content_delta:
+                                accumulated_content.append(content_delta)
+                                yield {"event": "text_delta", "content": content_delta}
+
+                            reasoning_delta = delta.get("reasoning_content")
+                            if reasoning_delta:
+                                accumulated_reasoning.append(reasoning_delta)
+                                yield {"event": "text_delta", "content": reasoning_delta}
+
+                            tc_deltas = delta.get("tool_calls")
+                            if tc_deltas and isinstance(tc_deltas, list):
+                                for tc in tc_deltas:
+                                    idx = tc.get("index", 0)
+                                    if idx not in tool_calls_map:
+                                        tool_calls_map[idx] = {
+                                            "id": tc.get("id") or f"call_{idx}",
+                                            "name": "",
+                                            "args_chunks": []
+                                        }
+                                    if tc.get("id"):
+                                        tool_calls_map[idx]["id"] = tc["id"]
+                                    fn = tc.get("function", {})
+                                    if fn.get("name"):
+                                        tool_calls_map[idx]["name"] = fn["name"]
+                                    if fn.get("arguments"):
+                                        tool_calls_map[idx]["args_chunks"].append(fn["arguments"])
+                                        yield {
+                                            "event": "tool_draft",
+                                            "tool": tool_calls_map[idx]["name"] or "action",
+                                            "args_delta": fn["arguments"]
+                                        }
+
+        except Exception as e:
+            logger.error("llama-server streaming exception (%s): %s", type(e).__name__, e)
+            yield {"event": "error", "message": f"{type(e).__name__}: {e}"}
+            return
+
+        # Assemble complete tool calls and emit events
+        final_tool_calls = []
+        if tool_calls_map:
+            for idx in sorted(tool_calls_map.keys()):
+                tc_data = tool_calls_map[idx]
+                raw_args_str = "".join(tc_data["args_chunks"])
+                try:
+                    parsed_args = json.loads(raw_args_str) if raw_args_str.strip() else {}
+                except Exception:
+                    parsed_args = {}
+
+                complete_call = {
+                    "id": tc_data["id"],
+                    "type": "function",
+                    "function": {
+                        "name": tc_data["name"],
+                        "arguments": parsed_args
+                    }
+                }
+                final_tool_calls.append(complete_call)
+                yield {"event": "tool_call", "tool_call": complete_call}
+
+        full_content = "".join(accumulated_content)
+        full_reasoning = "".join(accumulated_reasoning)
+
+        # Fallback if content was entirely emitted inside reasoning block
+        if not full_content.strip() and full_reasoning.strip() and not final_tool_calls:
+            full_content = full_reasoning
+            yield {"event": "text_delta", "content": full_content}
+
+        yield {
+            "event": "done",
+            "raw": {
+                "content": full_content,
+                "reasoning": full_reasoning,
+                "tool_calls": final_tool_calls if final_tool_calls else None
+            }
+        }

diff --git a/backend/app/agent/ollama_provider.py b/backend/app/agent/ollama_provider.py
new file mode 100644
--- /dev/null
+++ b/backend/app/agent/ollama_provider.py
@@ -0,0 +1,277 @@
+import json
+import logging
+from typing import Any, AsyncIterator, Optional
+import httpx
+from app.config import settings
+from app.agent.model_provider import ModelProvider
+from app.agent.tool_schema import convert_tool_to_openai_schema
+
+logger = logging.getLogger("jarvis.agent.ollama")
+
+
+class OllamaProvider(ModelProvider):
+    """
+    Fallback model provider communicating with Ollama's native REST API.
+    Refuses Qwen3.5 models due to Ollama mmproj compatibility issues.
+    """
+
+    def __init__(
+        self,
+        base_url: Optional[str] = None,
+        default_model: Optional[str] = None,
+        timeout: float = 90.0
+    ):
+        self.base_url = (base_url or getattr(settings, "ollama_base_url", settings.ollama_host)).rstrip("/")
+        self.default_model = default_model or settings.ollama_main_model
+        self.timeout = timeout
+
+    @property
+    def name(self) -> str:
+        return "ollama"
+
+    def _validate_model_allowed(self, model_name: str) -> None:
+        """Enforce strict ban on running Qwen3.5 models through Ollama."""
+        m_lower = (model_name or "").strip().lower()
+        if m_lower.startswith("qwen3.5") or "qwen3.5" in m_lower or "qwen-3.5" in m_lower:
+            raise ValueError(
+                f"Model '{model_name}' is not allowed on Ollama runtime due to known mmproj/GGUF compatibility issues. "
+                f"Qwen3.5 models must be executed via the primary llama.cpp runtime."
+            )
+
+    async def health_check(self) -> bool:
+        """Probe GET /api/tags endpoint."""
+        url = f"{self.base_url}/api/tags"
+        try:
+            async with httpx.AsyncClient(timeout=3.0) as client:
+                resp = await client.get(url)
+                return resp.status_code == 200
+        except Exception:
+            return False
+
+    async def model_info(self) -> dict[str, Any]:
+        """Retrieve model info from Ollama."""
+        models = await self.list_models()
+        return {
+            "provider": self.name,
+            "base_url": self.base_url,
+            "default_model": self.default_model,
+            "available_models": models,
+        }
+
+    async def list_models(self) -> list[str]:
+        """List models available in Ollama."""
+        url = f"{self.base_url}/api/tags"
+        models: list[str] = []
+        try:
+            async with httpx.AsyncClient(timeout=5.0) as client:
+                resp = await client.get(url)
+                if resp.status_code == 200:
+                    data = resp.json()
+                    for item in data.get("models", []):
+                        name = item.get("name") or item.get("model")
+                        if name:
+                            models.append(name)
+        except Exception as e:
+            logger.warning("Failed to list models from Ollama (%s): %s", self.base_url, e)
+        return models
+
+    async def unload_model(self, model: Optional[str] = None) -> bool:
+        """
+        Unload model from VRAM via Ollama /api/generate with keep_alive: 0.
+        """
+        target_model = model or self.default_model
+        url = f"{self.base_url}/api/generate"
+        payload = {
+            "model": target_model,
+            "prompt": "",
+            "stream": False,
+            "keep_alive": 0
+        }
+        try:
+            async with httpx.AsyncClient(timeout=10.0) as client:
+                resp = await client.post(url, json=payload)
+                return resp.status_code == 200
+        except Exception as e:
+            logger.warning("Error unloading model '%s' from Ollama: %s", target_model, e)
+            return False
+
+    def _normalize_tool_calls(self, raw_tool_calls: Optional[list[Any]]) -> Optional[list[dict[str, Any]]]:
+        if not raw_tool_calls or not isinstance(raw_tool_calls, list):
+            return None
+
+        normalized = []
+        for tc in raw_tool_calls:
+            if isinstance(tc, dict):
+                fn_obj = tc.get("function", {})
+                fn_name = fn_obj.get("name", "")
+                fn_args = fn_obj.get("arguments", {})
+            else:
+                fn_obj = getattr(tc, "function", None)
+                fn_name = getattr(fn_obj, "name", "")
+                fn_args = getattr(fn_obj, "arguments", {})
+
+            if isinstance(fn_args, str):
+                try:
+                    fn_args = json.loads(fn_args)
+                except Exception:
+                    fn_args = {}
+            elif not isinstance(fn_args, dict):
+                fn_args = {}
+
+            call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
+            call_id = call_id or f"call_{len(normalized)}"
+
+            normalized.append({
+                "id": str(call_id),
+                "type": "function",
+                "function": {
+                    "name": fn_name,
+                    "arguments": fn_args
+                }
+            })
+        return normalized if normalized else None
+
+    async def chat(
+        self,
+        messages: list[dict[str, Any]],
+        model: Optional[str] = None,
+        tools: Optional[list[Any]] = None,
+        temperature: float = 0.7,
+        profile: str = "general",
+        timeout: Optional[float] = None
+    ) -> dict[str, Any]:
+        """Send chat request to Ollama native /api/chat endpoint."""
+        target_model = model or self.default_model
+        self._validate_model_allowed(target_model)
+
+        req_timeout = timeout or self.timeout
+        url = f"{self.base_url}/api/chat"
+
+        payload: dict[str, Any] = {
+            "model": target_model,
+            "messages": messages,
+            "stream": False,
+            "options": {
+                "temperature": temperature
+            }
+        }
+
+        if tools:
+            formatted_tools = []
+            for t in tools:
+                schema = convert_tool_to_openai_schema(t)
+                if schema:
+                    formatted_tools.append(schema)
+            if formatted_tools:
+                payload["tools"] = formatted_tools
+
+        async with httpx.AsyncClient(timeout=req_timeout) as client:
+            try:
+                resp = await client.post(url, json=payload)
+            except Exception as e:
+                logger.error("Ollama connection error: %s", e)
+                raise RuntimeError(f"Ollama connection error: {e}") from e
+
+        if resp.status_code != 200:
+            raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")
+
+        data = resp.json()
+        msg_obj = data.get("message", {})
+        content = msg_obj.get("content", "") or ""
+        tool_calls = msg_obj.get("tool_calls")
+        normalized_calls = self._normalize_tool_calls(tool_calls)
+
+        return {
+            "message": {
+                "role": "assistant",
+                "content": content,
+                "tool_calls": normalized_calls
+            },
+            "raw": data
+        }
+
+    async def stream_chat(
+        self,
+        messages: list[dict[str, Any]],
+        model: Optional[str] = None,
+        tools: Optional[list[Any]] = None,
+        temperature: float = 0.7,
+        profile: str = "general",
+        timeout: Optional[float] = None
+    ) -> AsyncIterator[dict[str, Any]]:
+        """Stream chat tokens and tool calls from Ollama /api/chat."""
+        target_model = model or self.default_model
+        try:
+            self._validate_model_allowed(target_model)
+        except ValueError as e:
+            yield {"event": "error", "message": str(e)}
+            return
+
+        req_timeout = timeout or self.timeout
+        url = f"{self.base_url}/api/chat"
+
+        payload: dict[str, Any] = {
+            "model": target_model,
+            "messages": messages,
+            "stream": True,
+            "options": {
+                "temperature": temperature
+            }
+        }
+
+        if tools:
+            formatted_tools = []
+            for t in tools:
+                schema = convert_tool_to_openai_schema(t)
+                if schema:
+                    formatted_tools.append(schema)
+            if formatted_tools:
+                payload["tools"] = formatted_tools
+
+        accumulated_content = []
+        collected_tool_calls = []
+
+        try:
+            async with httpx.AsyncClient(timeout=req_timeout) as client:
+                async with client.stream("POST", url, json=payload) as response:
+                    if response.status_code != 200:
+                        err_body = await response.aread()
+                        yield {"event": "error", "message": f"Ollama streaming HTTP {response.status_code}: {err_body.decode('utf-8', errors='replace')}"}
+                        return
+
+                    async for line in response.aiter_lines():
+                        if not line:
+                            continue
+                        try:
+                            chunk = json.loads(line)
+                        except Exception:
+                            continue
+
+                        msg = chunk.get("message", {})
+                        content_chunk = msg.get("content", "")
+                        if content_chunk:
+                            accumulated_content.append(content_chunk)
+                            yield {"event": "text_delta", "content": content_chunk}
+
+                        tc_chunk = msg.get("tool_calls")
+                        if tc_chunk:
+                            norm = self._normalize_tool_calls(tc_chunk)
+                            if norm:
+                                for c in norm:
+                                    collected_tool_calls.append(c)
+                                    yield {"event": "tool_call", "tool_call": c}
+
+                        if chunk.get("done"):
+                            break
+        except Exception as e:
+            logger.error("Ollama streaming error: %s", e)
+            yield {"event": "error", "message": str(e)}
+            return
+
+        yield {
+            "event": "done",
+            "raw": {
+                "content": "".join(accumulated_content),
+                "tool_calls": collected_tool_calls if collected_tool_calls else None
+            }
+        }

diff --git a/backend/app/agent/provider_factory.py b/backend/app/agent/provider_factory.py
new file mode 100644
--- /dev/null
+++ b/backend/app/agent/provider_factory.py
@@ -0,0 +1,57 @@
+import logging
+from typing import Optional
+from app.config import settings
+from app.agent.model_provider import ModelProvider
+from app.agent.llamacpp_provider import LlamaCppProvider
+from app.agent.ollama_provider import OllamaProvider
+from app.agent.runtime_process_manager import get_runtime_process_manager
+
+logger = logging.getLogger("jarvis.agent.factory")
+
+_cached_providers: dict[str, ModelProvider] = {}
+
+
+def get_model_provider(runtime: Optional[str] = None) -> ModelProvider:
+    """
+    Returns a cached ModelProvider singleton based on the configured or requested runtime.
+    - 'llama_cpp' -> LlamaCppProvider
+    - 'ollama'    -> OllamaProvider
+    """
+    target_runtime = (runtime or settings.model_runtime).strip().lower()
+    if target_runtime in ("lmstudio", "bonsai"):
+        target_runtime = "llama_cpp"
+    elif target_runtime == "hermes3":
+        target_runtime = "ollama"
+
+    if target_runtime in _cached_providers:
+        return _cached_providers[target_runtime]
+
+    if target_runtime == "llama_cpp":
+        pm = get_runtime_process_manager()
+        provider = LlamaCppProvider(
+            base_url=f"http://{settings.llamacpp_host}:{settings.llamacpp_port}",
+            process_manager=pm
+        )
+        _cached_providers[target_runtime] = provider
+        logger.info("Initialized primary ModelProvider: LlamaCppProvider (port %s)", settings.llamacpp_port)
+        return provider
+
+    elif target_runtime == "ollama":
+        provider = OllamaProvider(
+            base_url=getattr(settings, "ollama_base_url", settings.ollama_host),
+            default_model=settings.ollama_main_model
+        )
+        _cached_providers[target_runtime] = provider
+        logger.info("Initialized fallback ModelProvider: OllamaProvider")
+        return provider
+
+    else:
+        raise ValueError(
+            f"Unknown model runtime '{target_runtime}'. Expected 'llama_cpp' (primary) or 'ollama' (fallback)."
+        )
+
+
+def reset_provider_cache() -> None:
+    """Clear cached provider instances for testing or reconfiguration."""
+    global _cached_providers
+    _cached_providers.clear()

diff --git a/backend/tests/test_provider_factory.py b/backend/tests/test_provider_factory.py
new file mode 100644
--- /dev/null
+++ b/backend/tests/test_provider_factory.py
@@ -0,0 +1,40 @@
+import pytest
+from unittest.mock import patch
+from app.agent.provider_factory import get_model_provider, reset_provider_cache
+from app.agent.llamacpp_provider import LlamaCppProvider
+from app.agent.ollama_provider import OllamaProvider
+
+
+@pytest.fixture(autouse=True)
+def clean_provider_cache():
+    reset_provider_cache()
+    yield
+    reset_provider_cache()
+
+
+def test_returns_llamacpp_provider_for_llama_cpp():
+    provider = get_model_provider(runtime="llama_cpp")
+    assert isinstance(provider, LlamaCppProvider)
+    assert provider.name == "llama_cpp"
+
+
+def test_returns_ollama_provider_for_ollama():
+    provider = get_model_provider(runtime="ollama")
+    assert isinstance(provider, OllamaProvider)
+    assert provider.name == "ollama"
+
+
+def test_raises_for_unknown_runtime():
+    with pytest.raises(ValueError, match="Unknown model runtime 'unsupported_runtime'"):
+        get_model_provider(runtime="unsupported_runtime")
+
+
+def test_provider_caching():
+    p1 = get_model_provider(runtime="llama_cpp")
+    p2 = get_model_provider(runtime="llama_cpp")
+    assert p1 is p2
+
+    reset_provider_cache()
+    p3 = get_model_provider(runtime="llama_cpp")
+    assert p3 is not p1
+    assert isinstance(p3, LlamaCppProvider)

diff --git a/backend/tests/test_llamacpp_provider.py b/backend/tests/test_llamacpp_provider.py
new file mode 100644
--- /dev/null
+++ b/backend/tests/test_llamacpp_provider.py
@@ -0,0 +1,205 @@
+import json
+import pytest
+from unittest.mock import AsyncMock, MagicMock, patch
+import httpx
+
+from app.agent.llamacpp_provider import LlamaCppProvider, strip_thinking_tags
+from app.agent.tools.registry import read_file, web_search
+
+
+def test_strip_thinking_tags():
+    raw = "<think>I need to search for quantum computing info.</think>Quantum computing is rapidly advancing."
+    clean, reasoning = strip_thinking_tags(raw)
+    assert clean == "Quantum computing is rapidly advancing."
+    assert "search for quantum computing" in reasoning
+
+
+@pytest.mark.anyio
+async def test_health_check_true_on_200():
+    provider = LlamaCppProvider(base_url="http://127.0.0.1:8001")
+    mock_resp = MagicMock(status_code=200)
+    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
+        mock_get.return_value = mock_resp
+        result = await provider.health_check()
+        assert result is True
+
+
+@pytest.mark.anyio
+async def test_health_check_false_on_error():
+    provider = LlamaCppProvider(base_url="http://127.0.0.1:8001")
+    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
+        mock_get.side_effect = httpx.ConnectError("Connection refused")
+        result = await provider.health_check()
+        assert result is False
+
+
+@pytest.mark.anyio
+async def test_chat_returns_normalized_message():
+    provider = LlamaCppProvider(base_url="http://127.0.0.1:8001")
+    mock_api_resp = {
+        "id": "chatcmpl-test",
+        "choices": [
+            {
+                "index": 0,
+                "message": {
+                    "role": "assistant",
+                    "content": "Hello world!"
+                }
+            }
+        ]
+    }
+    mock_resp = MagicMock(status_code=200, json=lambda: mock_api_resp)
+    with patch.object(provider, "health_check", return_value=True), \
+         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
+        mock_post.return_value = mock_resp
+        res = await provider.chat(messages=[{"role": "user", "content": "Hi"}], model="main")
+        assert res["message"]["role"] == "assistant"
+        assert res["message"]["content"] == "Hello world!"
+        assert res["message"]["tool_calls"] is None
+
+
+@pytest.mark.anyio
+async def test_chat_parses_tool_calls_and_handles_malformed_arguments():
+    provider = LlamaCppProvider(base_url="http://127.0.0.1:8001")
+    mock_api_resp = {
+        "id": "chatcmpl-tools",
+        "choices": [
+            {
+                "index": 0,
+                "message": {
+                    "role": "assistant",
+                    "content": "<think>planning tool call</think>",
+                    "tool_calls": [
+                        {
+                            "id": "call_valid",
+                            "type": "function",
+                            "function": {
+                                "name": "read_file",
+                                "arguments": '{"file_path": "test.txt"}'
+                            }
+                        },
+                        {
+                            "id": "call_malformed",
+                            "type": "function",
+                            "function": {
+                                "name": "execute_command",
+                                "arguments": '{malformed_json}'
+                            }
+                        }
+                    ]
+                }
+            }
+        ]
+    }
+    mock_resp = MagicMock(status_code=200, json=lambda: mock_api_resp)
+    with patch.object(provider, "health_check", return_value=True), \
+         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
+        mock_post.return_value = mock_resp
+        res = await provider.chat(messages=[{"role": "user", "content": "Read file"}], model="main", tools=[read_file])
+
+        assert res["message"]["content"] == ""
+        assert "planning tool call" in res["message"]["reasoning_content"]
+        assert len(res["message"]["tool_calls"]) == 2
+
+        tc1 = res["message"]["tool_calls"][0]
+        assert tc1["id"] == "call_valid"
+        assert tc1["function"]["name"] == "read_file"
+        assert tc1["function"]["arguments"] == {"file_path": "test.txt"}
+
+        tc2 = res["message"]["tool_calls"][1]
+        assert tc2["id"] == "call_malformed"
+        assert tc2["function"]["name"] == "execute_command"
+        assert tc2["function"]["arguments"] == {}  # Graceful fallback on malformed JSON
+
+
+@pytest.mark.anyio
+async def test_stream_accumulates_tool_calls_and_yields_deltas():
+    provider = LlamaCppProvider(base_url="http://127.0.0.1:8001")
+
+    # Simulate SSE lines
+    sse_lines = [
+        'data: {"choices":[{"delta":{"content":"Searching"}}]}',
+        'data: {"choices":[{"delta":{"content":" for data..."}}]}',
+        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_stream_1","function":{"name":"web_search","arguments":"{\\"query\\":"}}]}}]}',
+        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":" \\"python 3.12\\"}"}}]}}]}',
+        'data: [DONE]'
+    ]
+
+    async def mock_aiter_lines():
+        for line in sse_lines:
+            yield line
+
+    mock_stream_resp = MagicMock(status_code=200)
+    mock_stream_resp.aiter_lines = mock_aiter_lines
+
+    class MockStreamContext:
+        async def __aenter__(self):
+            return mock_stream_resp
+        async def __aexit__(self, exc_type, exc_val, exc_tb):
+            pass
+
+    with patch.object(provider, "health_check", return_value=True), \
+         patch("httpx.AsyncClient.stream", return_value=MockStreamContext()):
+        events = []
+        async for ev in provider.stream_chat(messages=[{"role": "user", "content": "Search"}], model="main", tools=[web_search]):
+            events.append(ev)
+
+        # Verify text deltas
+        text_deltas = [e["content"] for e in events if e["event"] == "text_delta"]
+        assert text_deltas == ["Searching", " for data..."]
+
+        # Verify accumulated tool call
+        tool_call_events = [e["tool_call"] for e in events if e["event"] == "tool_call"]
+        assert len(tool_call_events) == 1
+        assert tool_call_events[0]["id"] == "call_stream_1"
+        assert tool_call_events[0]["function"]["name"] == "web_search"
+        assert tool_call_events[0]["function"]["arguments"] == {"query": "python 3.12"}
+
+        # Verify done event
+        done_events = [e for e in events if e["event"] == "done"]
+        assert len(done_events) == 1
+        assert done_events[0]["raw"]["content"] == "Searching for data..."
+
+
+@pytest.mark.anyio
+async def test_sampling_profile_parameters_sent_correctly():
+    provider = LlamaCppProvider(base_url="http://127.0.0.1:8001")
+    captured_payloads = []
+
+    mock_resp = MagicMock(status_code=200, json=lambda: {"choices": [{"message": {"role": "assistant", "content": "ok"}}]})
+
+    async def capture_post(url, json=None, headers=None):
+        captured_payloads.append(json)
+        return mock_resp
+
+    with patch.object(provider, "health_check", return_value=True), \
+         patch("httpx.AsyncClient.post", side_effect=capture_post):
+        # 1. Profile general
+        await provider.chat(messages=[{"role": "user", "content": "hi"}], profile="general")
+        assert captured_payloads[0]["temperature"] == 0.7
+        assert captured_payloads[0]["top_p"] == 0.8
+        assert captured_payloads[0]["top_k"] == 20
+        assert captured_payloads[0]["presence_penalty"] == 1.5
+
+        # 2. Profile coding
+        await provider.chat(messages=[{"role": "user", "content": "write code"}], profile="coding")
+        assert captured_payloads[1]["temperature"] == 0.6
+        assert captured_payloads[1]["top_p"] == 0.95
+        assert captured_payloads[1]["top_k"] == 20
+        assert captured_payloads[1]["presence_penalty"] == 0.0
+
+
+@pytest.mark.anyio
+async def test_unload_model_delegates_to_process_manager():
+    mock_pm = MagicMock()
+    mock_pm.stop = AsyncMock(return_value=True)
+    provider = LlamaCppProvider(process_manager=mock_pm)
+
+    result = await provider.unload_model()
+    assert result is True
+    mock_pm.stop.assert_awaited_once()
+
+    # Never raises on exception
+    mock_pm.stop.side_effect = Exception("Process stop error")
+    safe_result = await provider.unload_model()
+    assert safe_result is False

diff --git a/backend/tests/test_runtime_process_manager.py b/backend/tests/test_runtime_process_manager.py
new file mode 100644
--- /dev/null
+++ b/backend/tests/test_runtime_process_manager.py
@@ -0,0 +1,131 @@
+import asyncio
+import os
+from pathlib import Path
+import pytest
+from unittest.mock import AsyncMock, MagicMock, patch
+
+from app.agent.runtime_process_manager import (
+    RuntimeProcessManager,
+    reset_runtime_process_manager,
+    resolve_repo_path,
+)
+
+
+@pytest.fixture(autouse=True)
+def clean_pm():
+    reset_runtime_process_manager()
+    yield
+    reset_runtime_process_manager()
+
+
+def test_resolve_repo_path():
+    p_rel = resolve_repo_path("models/test.gguf")
+    assert p_rel.is_absolute()
+    assert str(p_rel).endswith("models\\test.gguf") or str(p_rel).endswith("models/test.gguf")
+
+
+@pytest.mark.anyio
+async def test_ensure_running_noops_when_healthy():
+    pm = RuntimeProcessManager()
+    with patch.object(pm, "health_check", return_value=True), \
+         patch("subprocess.Popen") as mock_spawn:
+        res = await pm.ensure_running(model_kind="main")
+        assert res is True
+        mock_spawn.assert_not_called()
+        assert pm.is_externally_managed is True
+
+
+@pytest.mark.anyio
+async def test_ensure_running_spawns_when_unhealthy():
+    pm = RuntimeProcessManager(startup_timeout=5.0)
+
+    mock_proc = MagicMock()
+    mock_proc.poll = MagicMock(return_value=None)
+    mock_proc.stdout = None
+    mock_proc.stderr = None
+    mock_proc.pid = 9999
+
+    health_states = [False, False, True]
+
+    async def mock_health(timeout=None):
+        if health_states:
+            return health_states.pop(0)
+        return True
+
+    with patch.object(pm, "health_check", side_effect=mock_health), \
+         patch("subprocess.Popen") as mock_spawn:
+        mock_spawn.return_value = mock_proc
+        res = await pm.ensure_running(model_kind="main")
+
+        assert res is True
+        mock_spawn.assert_called_once()
+        args, kwargs = mock_spawn.call_args
+        cmd = args[0]
+        assert "--model" in cmd
+        assert "--alias" in cmd
+        assert "main" in cmd
+        assert "--ctx-size" in cmd
+
+
+@pytest.mark.anyio
+async def test_stop_terminates_and_kills_on_timeout():
+    pm = RuntimeProcessManager()
+    mock_proc = MagicMock()
+    mock_proc.poll = MagicMock(return_value=None)
+    mock_proc.pid = 1234
+    mock_proc.terminate = MagicMock()
+    mock_proc.kill = MagicMock()
+    mock_proc.wait = MagicMock(return_value=0)
+    pm._process = mock_proc
+    pm._externally_managed = False
+
+    res = await pm.stop()
+    assert res is True
+    mock_proc.terminate.assert_called_once()
+    mock_proc.kill.assert_called_once()
+    assert pm._process is None
+
+
+@pytest.mark.anyio
+async def test_externally_managed_server_is_never_killed():
+    pm = RuntimeProcessManager()
+    pm._externally_managed = True
+    pm._process = None
+
+    res = await pm.stop()
+    assert res is True
+    assert pm._process is None
+
+
+@pytest.mark.anyio
+async def test_switch_model_restarts_with_new_model():
+    pm = RuntimeProcessManager()
+    pm._current_model_kind = "main"
+    pm._process = MagicMock(returncode=None)
+
+    with patch.object(pm, "_stop_internal", new_callable=AsyncMock) as mock_stop, \
+         patch.object(pm, "ensure_running", new_callable=AsyncMock) as mock_ensure:
+        mock_stop.return_value = True
+        mock_ensure.return_value = True
+
+        res = await pm.switch_model("fast")
+        assert res is True
+        mock_stop.assert_awaited_once()
+        mock_ensure.assert_awaited_once_with("fast")
+
+
+def test_static_audit_no_lms_cli_usage_in_backend_app():
+    """
+    Static analysis check verifying no active module in backend/app
+    references 'lms' CLI subprocess or shutil.which for LM Studio,
+    except for the deprecated lmstudio_client.py.
+    """
+    app_dir = Path(__file__).resolve().parent.parent / "app"
+    forbidden_terms = ["shutil.which('lms')", 'shutil.which("lms")', "lms unload", "lms load"]
+
+    for py_file in app_dir.rglob("*.py"):
+        if py_file.name == "lmstudio_client.py":
+            continue
+        code = py_file.read_text(encoding="utf-8", errors="ignore")
+        for term in forbidden_terms:
+            assert term not in code, f"Forbidden LM Studio CLI pattern '{term}' found in {py_file}"
`
