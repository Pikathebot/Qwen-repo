"use client";

import { useState, useEffect, useCallback } from "react";
import { HealthResponse } from "@/lib/types";
import { fetchHealth, pauseGovernor, resumeGovernor } from "@/lib/api";

export interface UseGovernorReturn {
  health: HealthResponse | null;
  status: "ok" | "degraded" | "throttled" | "offline";
  throttled: boolean;
  activeBackend: string;
  configuredModel: string;
  availableModels: string[];
  llamaConnected: boolean;
  ollamaConnected: boolean;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  pause: (reason?: string) => Promise<void>;
  resume: () => Promise<void>;
}

export function useGovernor(pollIntervalMs: number = 2000): UseGovernorReturn {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchHealth();
      setHealth(data);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Backend unreachable";
      setError(msg);
      // Keep previous data if available, but flag offline/degraded
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, pollIntervalMs);
    return () => clearInterval(interval);
  }, [refresh, pollIntervalMs]);

  const pause = useCallback(
    async (reason?: string) => {
      try {
        await pauseGovernor(reason);
        await refresh();
      } catch (err: unknown) {
        console.error("Failed to pause governor:", err);
      }
    },
    [refresh]
  );

  const resume = useCallback(async () => {
    try {
      await resumeGovernor();
      await refresh();
    } catch (err: unknown) {
      console.error("Failed to resume governor:", err);
    }
  }, [refresh]);

  let status: "ok" | "degraded" | "throttled" | "offline" = "ok";
  if (error || !health) {
    status = "offline";
  } else if (health.governor_throttled) {
    status = "throttled";
  } else if (health.status === "degraded") {
    status = "degraded";
  }

  const isLlama = health?.llama_connected ?? false;
  const isOllama = health?.ollama_connected ?? false;

  return {
    health,
    status,
    throttled: health?.governor_throttled ?? false,
    activeBackend: health?.active_backend ?? "llama_cpp",
    configuredModel: health?.configured_model ?? "models/Qwen3.5-9B-Q4_K_M.gguf",
    availableModels: health?.available_models ?? [],
    llamaConnected: isLlama,
    ollamaConnected: isLlama || isOllama,
    isLoading,
    error,
    refresh,
    pause,
    resume,
  };
}
