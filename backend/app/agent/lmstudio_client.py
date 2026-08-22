import inspect
import json
import logging
from typing import Any, Callable, Optional
import httpx
from app.config import settings
from app.agent.tools.registry import TOOL_SCHEMAS, TOOL_FUNCTIONS

logger = logging.getLogger("jarvis.agent.lmstudio")


def convert_tool_to_openai_schema(tool: Any) -> Optional[dict[str, Any]]:
    """
    Convert a Python tool function, MCP tool dictionary, or schema to OpenAI function format.
    """
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
        # First line of docstring as short description
        short_desc = doc.strip().split("\n")[0] if doc else f"Execute {fn_name}."

        schema_cls = TOOL_SCHEMAS.get(fn_name)
        if schema_cls:
            raw_schema = schema_cls.model_json_schema()
            parameters = {
                "type": "object",
                "properties": raw_schema.get("properties", {}),
                "required": raw_schema.get("required", [])
            }
        else:
            parameters = {
                "type": "object",
                "properties": {},
                "required": []
            }

        return {
            "type": "function",
            "function": {
                "name": fn_name,
                "description": short_desc,
                "parameters": parameters
            }
        }

    return None


class LMStudioClient:
    """
    Asynchronous client for LM Studio's local OpenAI-compatible API.
    Supports tool calling, model enumeration, and VRAM unload signals.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 180.0,
        api_key: str = "lm-studio"
    ):
        self.base_url = (base_url or settings.lmstudio_base_url).rstrip("/")
        self.timeout = timeout
        self.api_key = api_key

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def is_available(self) -> bool:
        """
        Check if the LM Studio local server is online and reachable.
        """
        url = f"{self.base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """
        Fetch list of active/available models from LM Studio.
        """
        url = f"{self.base_url}/models"
        models: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("data", []):
                        m_id = item.get("id") or item.get("name")
                        if m_id:
                            models.append(m_id)
        except Exception as e:
            logger.warning("Failed to list models from LM Studio (%s): %s", self.base_url, e)
        return models

    async def unload_model(self, model_name: Optional[str] = None) -> bool:
        """
        Unloads model(s) from GPU VRAM via LM Studio's official `lms` CLI utility.
        Returns True on confirmed eviction, False otherwise.
        """
        import os
        import shutil
        import asyncio

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
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
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

    async def load_model(self, model_name: Optional[str] = None) -> bool:
        """
        Loads model into GPU VRAM via LM Studio's official `lms` CLI utility or HTTP warm-up.
        Returns True on successful load, False otherwise.
        """
        import os
        import shutil
        import asyncio

        target = model_name or settings.lmstudio_model
        lms_bin = shutil.which("lms")
        if not lms_bin:
            default_path = os.path.expanduser(r"~\.lmstudio\bin\lms.exe")
            if os.path.exists(default_path):
                lms_bin = default_path

        if lms_bin:
            try:
                cmd = [lms_bin, "load", target, "-y"]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
                if proc.returncode == 0:
                    out_msg = stdout.decode("utf-8", errors="ignore").strip()
                    logger.info("LM Studio model '%s' loaded via 'lms' CLI: %s", target, out_msg or "OK")
                    return True
                else:
                    err_msg = stderr.decode("utf-8", errors="ignore").strip()
                    logger.warning("LM Studio CLI load failed (exit code %d): %s", proc.returncode, err_msg)
            except Exception as e:
                logger.warning("LM Studio CLI load exception: %s", e)

        # Fallback to HTTP warmup call
        try:
            await self.chat(
                messages=[{"role": "user", "content": "ping"}],
                model=target,
                timeout=60.0
            )
            logger.info("LM Studio model '%s' loaded and warmed up via HTTP.", target)
            return True
        except Exception as e:
            logger.warning("LM Studio HTTP warmup load failed for '%s': %s", target, e)
            return False

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: Optional[list[Any]] = None,
        temperature: float = 0.7,
        timeout: Optional[float] = None
    ) -> dict[str, Any]:
        """
        Send chat completion request to LM Studio with optional OpenAI function tools.
        Returns a dict structured as:
        {
            "message": {
                "role": "assistant",
                "content": str,
                "tool_calls": list[dict] | None
            },
            "raw": dict
        }
        """
        req_timeout = timeout or self.timeout
        url = f"{self.base_url}/chat/completions"

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            formatted_tools = []
            for t in tools:
                schema = convert_tool_to_openai_schema(t)
                if schema:
                    formatted_tools.append(schema)
            if formatted_tools:
                payload["tools"] = formatted_tools
                payload["tool_choice"] = "auto"

        logger.info("Dispatching request to LM Studio model '%s' (tools=%d)", model, len(payload.get("tools", [])))

        async with httpx.AsyncClient(timeout=req_timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=self._get_headers())
            except httpx.TimeoutException:
                logger.error("LM Studio request timed out after %.1fs", req_timeout)
                raise RuntimeError(f"LM Studio request timed out after {req_timeout} seconds.")
            except Exception as e:
                logger.error("LM Studio connection error: %s", e)
                raise RuntimeError(f"LM Studio connection error: {str(e)}")

        if resp.status_code != 200:
            err_text = resp.text
            logger.error("LM Studio error (HTTP %d): %s", resp.status_code, err_text)
            raise RuntimeError(f"LM Studio returned HTTP {resp.status_code}: {err_text}")

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": None
                },
                "raw": data
            }

        msg = choices[0].get("message", {})
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        tool_calls = msg.get("tool_calls")

        # Normalize tool_calls format if present
        normalized_calls = None
        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
            normalized_calls = []
            for tc in tool_calls:
                fn_obj = tc.get("function", {})
                fn_name = fn_obj.get("name", "")
                raw_args = fn_obj.get("arguments", {})
                if isinstance(raw_args, str):
                    try:
                        parsed_args = json.loads(raw_args)
                    except Exception:
                        parsed_args = {"raw": raw_args}
                elif isinstance(raw_args, dict):
                    parsed_args = raw_args
                else:
                    parsed_args = {}

                normalized_calls.append({
                    "id": tc.get("id"),
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "arguments": parsed_args
                    }
                })

        # If content is empty but model produced final text in reasoning_content without tool calls
        if not content and reasoning and not normalized_calls:
            # Check if there's an explicit conclusion at the end of reasoning
            lines = [l.strip() for l in reasoning.strip().split("\n") if l.strip()]
            if lines:
                content = lines[-1].lstrip("#*- ").strip()

        return {
            "message": {
                "role": "assistant",
                "content": content,
                "reasoning_content": reasoning,
                "tool_calls": normalized_calls
            },
            "raw": data
        }
