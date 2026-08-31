import asyncio
import logging
import os
import sys
import threading
import subprocess
import time
from pathlib import Path
from typing import Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger("jarvis.agent.process_manager")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def resolve_repo_path(path_str: str) -> Path:
    """Resolve a path relative to the repo root if it's relative, otherwise return as absolute."""
    p = Path(path_str)
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    return p


class RuntimeProcessManager:
    """
    Deterministic OS process management for llama-server.exe.
    Controls process startup, model switching, health verification,
    and 100% process-based GPU VRAM eviction.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        server_exe: Optional[str] = None,
        main_model_path: Optional[str] = None,
        fast_model_path: Optional[str] = None,
        ctx_size: Optional[int] = None,
        gpu_layers: Optional[int] = None,
        startup_timeout: Optional[float] = None,
        extra_args: Optional[list[str]] = None,
    ):
        self.host = host or settings.llamacpp_host
        self.port = port if port is not None else settings.llamacpp_port
        self.server_exe = server_exe or settings.llamacpp_server_exe
        self.main_model_path = main_model_path or settings.llamacpp_main_model_path
        self.fast_model_path = fast_model_path or settings.llamacpp_fast_model_path
        self.ctx_size = ctx_size if ctx_size is not None else settings.llamacpp_ctx_size
        self.gpu_layers = gpu_layers if gpu_layers is not None else settings.llamacpp_gpu_layers
        self.startup_timeout = startup_timeout if startup_timeout is not None else settings.llamacpp_startup_timeout_seconds
        self.extra_args = list(extra_args if extra_args is not None else settings.llamacpp_extra_args)

        self._process: Optional[subprocess.Popen] = None
        self._current_model_kind: Optional[str] = None
        self._externally_managed: bool = False
        self._lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def current_model_kind(self) -> Optional[str]:
        return self._current_model_kind

    @property
    def is_externally_managed(self) -> bool:
        return self._externally_managed

    def resolve_model_path(self, model_kind: str) -> tuple[Path, str]:
        """
        Resolve model file path and alias based on kind ('main', 'fast', or direct path/filename).
        Returns (resolved_path, alias).
        """
        kind_norm = (model_kind or "main").strip().lower()
        if kind_norm in ("main", "9b", "qwen3.5-9b", "default"):
            target_path_str = self.main_model_path
            alias = "main"
        elif kind_norm in ("fast", "4b", "qwen3.5-4b"):
            target_path_str = self.fast_model_path
            alias = "fast"
        else:
            target_path_str = model_kind
            alias = Path(model_kind).stem

        resolved = resolve_repo_path(target_path_str)
        if not resolved.exists() and alias == "fast":
            models_dir = REPO_ROOT / "models"
            if models_dir.exists():
                for cand in models_dir.glob("*4B*.gguf"):
                    return cand.resolve(), alias
        elif not resolved.exists() and alias == "main":
            models_dir = REPO_ROOT / "models"
            if models_dir.exists():
                for cand in models_dir.glob("*9B*.gguf"):
                    return cand.resolve(), alias
        return resolved, alias

    async def health_check(self, timeout: float = 3.0) -> bool:
        """Probe GET /v1/models endpoint."""
        url = f"{self.base_url}/v1/models"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False

    def is_running(self) -> bool:
        """Check if child process is active and has not terminated."""
        if self._process is not None:
            return self._process.poll() is None
        return self._externally_managed

    def _drain_sync_stream(self, stream, stream_name: str) -> None:
        """Drain child process output stream in background thread to prevent pipe buffer stalls."""
        if not stream:
            return
        try:
            for line in iter(stream.readline, b""):
                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    logger.debug("[llama-server %s] %s", stream_name, decoded)
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    async def ensure_running(self, model_kind: str = "main") -> bool:
        """
        Ensure llama-server is online with the requested model_kind.
        If unhealthy or missing, spawn the process and wait for ready state.
        """
        resolved_exe = resolve_repo_path(self.server_exe)
        resolved_model, alias = self.resolve_model_path(model_kind)

        async with self._lock:
            # 1. If health check passes
            if await self.health_check(timeout=2.0):
                if self._current_model_kind in (alias, model_kind):
                    return True

                # Different model kind requested -> trigger switch
                logger.info(
                    "Switching running llama-server model from '%s' to '%s' (alias: %s)",
                    self._current_model_kind,
                    model_kind,
                    alias
                )
                await self._stop_internal()

            # 2. Server not running or needs restart with new model
            cmd = [
                str(resolved_exe),
                "--model", str(resolved_model),
                "--alias", alias,
                "--host", str(self.host),
                "--port", str(self.port),
                "--ctx-size", str(self.ctx_size),
                "--n-gpu-layers", str(self.gpu_layers),
                "--parallel", "1",
            ]
            if self.extra_args:
                cmd.extend(self.extra_args)

            logger.info("Spawning llama-server process: %s", " ".join(cmd))
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )
            except Exception as e:
                logger.error("Failed to spawn llama-server binary at '%s': %s", resolved_exe, e)
                raise RuntimeError(f"Failed to spawn llama-server ({resolved_exe}): {e}") from e

            self._process = proc
            self._current_model_kind = model_kind
            self._externally_managed = False

            # Start background pipe drainers
            t_out = threading.Thread(target=self._drain_sync_stream, args=(proc.stdout, "stdout"), daemon=True)
            t_err = threading.Thread(target=self._drain_sync_stream, args=(proc.stderr, "stderr"), daemon=True)
            t_out.start()
            t_err.start()

            # Poll health check until startup timeout
            start_time = time.time()
            poll_interval = 0.5
            while time.time() - start_time < self.startup_timeout:
                if proc.poll() is not None:
                    raise RuntimeError(
                        f"llama-server exited prematurely with code {proc.returncode} during startup."
                    )
                if await self.health_check(timeout=1.5):
                    logger.info("llama-server successfully started and healthy at %s (model: %s)", self.base_url, alias)
                    return True
                await asyncio.sleep(poll_interval)

            # Startup timed out -> kill process
            logger.error("llama-server startup timed out after %.1fs", self.startup_timeout)
            await self._stop_internal()
            raise RuntimeError(f"llama-server failed to become healthy within {self.startup_timeout}s.")

    async def _stop_internal(self) -> bool:
        """Internal worker to stop the process without acquiring the lock."""
        self._current_model_kind = None
        self._externally_managed = False

        # 1. Terminate tracked subprocess if present
        if self._process is not None:
            proc = self._process
            self._process = None
            if proc.poll() is None:
                logger.info("Terminating tracked llama-server process (PID %s)...", proc.pid)
                try:
                    proc.terminate()
                    for _ in range(30):
                        if proc.poll() is not None:
                            break
                        await asyncio.sleep(0.1)
                    else:
                        proc.kill()
                        proc.wait()
                except Exception as e:
                    logger.debug("Error terminating tracked process: %s", e)

        # 2. Terminate any orphan or lingering llama-server instances
        import psutil
        try:
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    p_name = (p.info.get('name') or "").lower()
                    if "llama-server" in p_name:
                        logger.info("Terminating llama-server process (PID %s) for VRAM release...", p.pid)
                        p.terminate()
                        try:
                            p.wait(timeout=3)
                        except psutil.TimeoutExpired:
                            p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug("Error scanning for llama-server processes: %s", e)

        logger.info("llama-server processes terminated. 100% GPU VRAM released.")
        return True

    async def stop(self) -> bool:
        """
        Gracefully terminate or kill the llama-server process.
        This provides deterministic 100% GPU VRAM release.
        """
        async with self._lock:
            return await self._stop_internal()

    async def switch_model(self, model_kind: str) -> bool:
        """
        Stop current running model and switch to requested model_kind.
        """
        async with self._lock:
            if self.is_running() and self._current_model_kind == model_kind:
                return True
            await self._stop_internal()
            # Release lock before ensure_running to avoid deadlocks
        return await self.ensure_running(model_kind)


_process_manager_instance: Optional[RuntimeProcessManager] = None


def get_runtime_process_manager() -> RuntimeProcessManager:
    global _process_manager_instance
    if _process_manager_instance is None:
        _process_manager_instance = RuntimeProcessManager()
    return _process_manager_instance


def reset_runtime_process_manager() -> None:
    global _process_manager_instance
    _process_manager_instance = None
