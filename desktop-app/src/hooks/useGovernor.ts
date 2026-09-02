"use client";

import { useState, useEffect, useCallback } from "react";
import { HealthResponse, GovernorTier } from "@/lib/types";
import { fetchHealth, pauseGovernor, resumeGovernor } from "@/lib/api";
import { MockAdapter } from "@/lib/mock-adapter";

export interface UseGovernorReturn {
  health: HealthResponse | null;
  status: "ok" | "degraded" | "throttled" | "offline";
  tier: GovernorTier;
  throttled: boolean;
  activeBackend: string;
  configuredModel: string;
  availableModels: string[];
  ollamaConnected: boolean;
  isLoading: boolean;
  isMock: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  pause: (reason?: string) => Promise<void>;
  resume: () => Promise<void>;
}

export function useGovernor(pollIntervalMs: number = 3000): UseGovernorReturn {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [tier, setTier] = useState<GovernorTier>("IDLE");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isMock, setIsMock] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchHealth();
      setHealth(data);
      setIsMock(false);
      setError(null);
      if (data.governor_throttled) {
        setTier("HEAVY");
      } else if (data.status === "degraded") {
        setTier("MODERATE");
      } else {
        setTier("IDLE");
      }
    } catch {
      // Backend offline -> Load realistic mock telemetry seamlessly
      const mockHealth = await MockAdapter.getHealth();
      setHealth(mockHealth);
      setIsMock(true);
      setError(null);
      setTier("IDLE");
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
      } catch {
        // mock pause
      }
      setTier("PAUSED");
    },
    []
  );

  const resume = useCallback(async () => {
    try {
      await resumeGovernor();
    } catch {
      // mock resume
    }
    setTier("IDLE");
  }, []);

  let status: "ok" | "degraded" | "throttled" | "offline" = "ok";
  if (tier === "PAUSED") {
    status = "throttled";
  } else if (health?.governor_throttled) {
    status = "throttled";
  } else if (health?.status === "degraded") {
    status = "degraded";
  }

  return {
    health,
    status,
    tier,
    throttled: health?.governor_throttled ?? false,
    activeBackend: health?.active_backend ?? "vLLM / Ollama",
    configuredModel: health?.configured_model ?? "Qwen3-30B",
    availableModels: health?.available_models ?? ["Qwen3-30B", "Qwen3-4B", "Qwen3-0.6B"],
    ollamaConnected: health?.ollama_connected ?? true,
    isLoading,
    isMock,
    error,
    refresh,
    pause,
    resume,
  };
}
