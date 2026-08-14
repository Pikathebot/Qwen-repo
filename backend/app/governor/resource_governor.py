import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
import psutil

logger = logging.getLogger("jarvis.governor")

import warnings

# Use official nvidia-ml-py SDK
HAS_NVML = False
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        import nvidia_ml_py as pynvml
    HAS_NVML = True
except ImportError:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            import pynvml
        HAS_NVML = True
    except ImportError:
        HAS_NVML = False


@dataclass
class SystemMetrics:
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_mb: float = 0.0
    ram_total_mb: float = 0.0
    gpu_available: bool = False
    gpu_name: Optional[str] = None
    gpu_util_percent: float = 0.0
    vram_util_percent: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0
    vram_free_mb: float = 0.0
    gpu_temp_c: Optional[float] = None
    throttled: bool = False
    throttle_reasons: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class ResourceGovernor:
    """
    Background resource governor monitoring GPU, VRAM, CPU, and RAM load
    to safeguard host performance and prevent system stalls during intensive tasks.
    """

    def __init__(
        self,
        enabled: bool = True,
        poll_interval: float = 1.0,
        gpu_threshold: float = 85.0,
        vram_threshold: float = 90.0,
        cpu_threshold: float = 90.0,
        ram_threshold: float = 92.0,
        auto_unload_on_throttle: bool = True,
        on_throttle_unload: Optional[Any] = None,
    ):
        self.enabled = enabled
        self.poll_interval = poll_interval
        self.gpu_threshold = gpu_threshold
        self.vram_threshold = vram_threshold
        self.cpu_threshold = cpu_threshold
        self.ram_threshold = ram_threshold
        self.auto_unload_on_throttle = auto_unload_on_throttle
        self.on_throttle_unload = on_throttle_unload

        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._nvml_initialized = False
        self._nvml_handle: Any = None
        self._current_metrics = SystemMetrics()
        self._lock = asyncio.Lock()
        self._throttle_streak = 0
        self._has_auto_unloaded = False
        self._is_inferencing = False

        self._init_nvml()

    def set_inferencing(self, state: bool) -> None:
        """Inform governor whether Jarvis is actively generating a response."""
        self._is_inferencing = state
        if state:
            self._throttle_streak = 0

    @property
    def is_inferencing(self) -> bool:
        return self._is_inferencing

    def _init_nvml(self) -> None:
        if not HAS_NVML:
            logger.info("PyNVML not installed. GPU hardware metrics will be disabled.")
            return

        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                self._nvml_initialized = True
                name = pynvml.nvmlDeviceGetName(self._nvml_handle)
                logger.info("Initialized NVML for GPU: %s", name)
        except Exception as e:
            logger.warning("Failed to initialize NVML: %s. Continuing with CPU/RAM metrics only.", e)
            self._nvml_initialized = False

    def collect_metrics(self) -> SystemMetrics:
        """
        Poll real-time hardware telemetry and evaluate threshold breaches.
        """
        metrics = SystemMetrics(timestamp=time.time())

        # 1. CPU & RAM Telemetry
        try:
            metrics.cpu_percent = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            metrics.ram_percent = ram.percent
            metrics.ram_used_mb = round(ram.used / (1024 * 1024), 1)
            metrics.ram_total_mb = round(ram.total / (1024 * 1024), 1)
        except Exception as e:
            logger.error("Error reading CPU/RAM metrics: %s", e)

        # 2. GPU & VRAM Telemetry
        if self._nvml_initialized and self._nvml_handle:
            try:
                metrics.gpu_available = True
                metrics.gpu_name = pynvml.nvmlDeviceGetName(self._nvml_handle)
                
                # GPU Core Utilization
                util_rates = pynvml.nvmlDeviceGetUtilizationRates(self._nvml_handle)
                metrics.gpu_util_percent = float(util_rates.gpu)

                # VRAM Usage
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
                metrics.vram_total_mb = round(mem_info.total / (1024 * 1024), 1)
                metrics.vram_used_mb = round(mem_info.used / (1024 * 1024), 1)
                metrics.vram_free_mb = round(mem_info.free / (1024 * 1024), 1)
                if mem_info.total > 0:
                    metrics.vram_util_percent = round((mem_info.used / mem_info.total) * 100.0, 1)

                # GPU Temperature
                try:
                    metrics.gpu_temp_c = float(pynvml.nvmlDeviceGetTemperature(self._nvml_handle, pynvml.NVML_TEMPERATURE_GPU))
                except Exception:
                    pass

            except Exception as e:
                logger.warning("Error reading GPU metrics: %s", e)

        # 3. Evaluate Threshold Breaches
        reasons = []
        if self.enabled:
            if metrics.gpu_available and metrics.gpu_util_percent >= self.gpu_threshold:
                reasons.append(
                    f"GPU utilization ({metrics.gpu_util_percent}%) exceeds threshold ({self.gpu_threshold}%)"
                )
            if metrics.gpu_available and metrics.vram_util_percent >= self.vram_threshold:
                reasons.append(
                    f"VRAM utilization ({metrics.vram_util_percent}%) exceeds threshold ({self.vram_threshold}%)"
                )
            if metrics.cpu_percent >= self.cpu_threshold:
                reasons.append(
                    f"CPU utilization ({metrics.cpu_percent}%) exceeds threshold ({self.cpu_threshold}%)"
                )
            if metrics.ram_percent >= self.ram_threshold:
                reasons.append(
                    f"System RAM utilization ({metrics.ram_percent}%) exceeds threshold ({self.ram_threshold}%)"
                )

        metrics.throttled = len(reasons) > 0
        metrics.throttle_reasons = reasons

        return metrics

    async def _poll_loop(self) -> None:
        logger.info("Resource Governor polling loop started (interval=%.1fs)", self.poll_interval)
        while self._running:
            try:
                metrics = self.collect_metrics()
                async with self._lock:
                    self._current_metrics = metrics

                # If Jarvis itself is generating tokens, GPU load is expected and normal
                if self._is_inferencing:
                    self._throttle_streak = 0
                elif metrics.throttled:
                    self._throttle_streak += 1
                    logger.warning(
                        "Resource Governor ACTIVE THROTTLE (streak=%d): %s",
                        self._throttle_streak,
                        "; ".join(metrics.throttle_reasons)
                    )

                    # Trigger auto-unload on sustained external load (4 consecutive idle polls = ~4 seconds)
                    if (
                        self.auto_unload_on_throttle
                        and self._throttle_streak >= 4
                        and not self._has_auto_unloaded
                        and self.on_throttle_unload is not None
                    ):
                        try:
                            logger.warning(
                                "Resource Governor AUTO-UNLOAD: Sustained external gaming/workload load detected while idle. Evicting Ollama models from GPU VRAM."
                            )
                            if asyncio.iscoroutinefunction(self.on_throttle_unload):
                                await self.on_throttle_unload()
                            else:
                                self.on_throttle_unload()
                            self._has_auto_unloaded = True
                        except Exception as unload_err:
                            logger.warning("Error during auto-unload: %s", unload_err)
                else:
                    self._throttle_streak = 0
                    if self._has_auto_unloaded:
                        logger.info("Resource Governor: External load returned to normal. GPU VRAM clear for on-demand use.")
                        self._has_auto_unloaded = False

            except Exception as e:
                logger.error("Unexpected error in governor poll loop: %s", e)

            await asyncio.sleep(self.poll_interval)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        # Run initial sync sample
        self._current_metrics = self.collect_metrics()
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        if self._nvml_initialized:
            try:
                pynvml.nvmlShutdown()
                self._nvml_initialized = False
            except Exception:
                pass
        logger.info("Resource Governor stopped.")

    async def get_metrics(self) -> SystemMetrics:
        async with self._lock:
            return self._current_metrics

    async def is_throttled(self) -> tuple[bool, Optional[str]]:
        """
        Returns (is_throttled, primary_reason).
        """
        metrics = await self.get_metrics()
        if metrics.throttled and metrics.throttle_reasons:
            return True, metrics.throttle_reasons[0]
        return False, None

    async def wait_until_healthy(self, timeout_seconds: float = 3.0) -> tuple[bool, Optional[str]]:
        """
        Adaptive queueing: Waits up to timeout_seconds for temporary load spikes to clear.
        Returns (is_healthy, throttle_reason).
        """
        throttled, reason = await self.is_throttled()
        if not throttled:
            return True, None

        logger.info("Throttled. Waiting up to %.1fs for system load to normalize...", timeout_seconds)
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            await asyncio.sleep(0.25)
            # Re-check updated metrics
            throttled, reason = await self.is_throttled()
            if not throttled:
                logger.info("System load cleared. Resuming request.")
                return True, None

        return False, reason
