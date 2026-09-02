"use client";

import React, { useState } from "react";
import { ModelTopology, GovernorTier } from "@/lib/types";
import { GovernorMeter } from "../ui/GovernorMeter";
import { LocalOnlyBadge, LocalPrivacyStatus } from "../ui/LocalOnlyBadge";
import { SpecularButton } from "../ui/SpecularButton";

export interface SystemTabProps {
  localStatus?: LocalPrivacyStatus;
  models?: ModelTopology;
  governorTier?: GovernorTier;
  vramUsedMb?: number;
  vramTotalMb?: number;
  onUnloadModels?: () => Promise<void>;
  onTogglePauseGovernor?: () => void;
  className?: string;
}

const DEFAULT_MODELS: ModelTopology = {
  main: {
    role: "MAIN",
    name: "Qwen3-30B",
    provider: "Local (vLLM)",
    status: "online",
    contextWindow: 32768,
    quantization: "AWQ 4-bit",
    vramUsageMb: 18400,
  },
  fast: {
    role: "FAST",
    name: "Qwen3-4B",
    provider: "Local (vLLM)",
    status: "online",
    contextWindow: 32768,
    quantization: "FP16",
    vramUsageMb: 8200,
  },
  embed: {
    role: "EMBED",
    name: "Qwen3-0.6B-Embed",
    provider: "Local (FastEmbed)",
    status: "online",
    contextWindow: 8192,
    vramUsageMb: 1200,
  },
  rerank: {
    role: "RERANK",
    name: "Qwen3-0.6B-Reranker",
    provider: "Local (FastEmbed)",
    status: "online",
    contextWindow: 8192,
    vramUsageMb: 1200,
  },
  vision: {
    role: "VISION",
    name: "Qwen2-VL-7B",
    provider: "Local (Ollama)",
    status: "online",
    contextWindow: 16384,
    vramUsageMb: 7600,
  },
};

export function SystemTab({
  localStatus = "local",
  models = DEFAULT_MODELS,
  governorTier = "IDLE",
  vramUsedMb = 18400,
  vramTotalMb = 24576,
  onUnloadModels,
  onTogglePauseGovernor,
  className = "",
}: SystemTabProps) {
  const [terminalEnabled, setTerminalEnabled] = useState(true);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [unloading, setUnloading] = useState(false);

  const handleUnload = async () => {
    if (!onUnloadModels) return;
    try {
      setUnloading(true);
      await onUnloadModels();
    } finally {
      setUnloading(false);
    }
  };

  const modelList = [
    models.main,
    models.fast,
    models.embed,
    models.rerank,
    models.vision,
  ];

  return (
    <div className={`space-y-4 flex flex-col h-full overflow-y-auto pr-1 ${className}`}>
      {/* Privacy & Hardware Overview Card */}
      <div className="p-3.5 rounded-card bg-black/30 border border-white/[0.08] space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[11px] text-tertiary uppercase tracking-wider font-semibold">
            Runtime Architecture
          </span>
          <LocalOnlyBadge status={localStatus} />
        </div>

        {/* Governor Status & VRAM Meter */}
        <div className="space-y-2 pt-2 border-t border-white/[0.06]">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-secondary">Resource Governor</span>
            <span className="text-primary font-semibold">{governorTier}</span>
          </div>

          <GovernorMeter
            tier={governorTier}
            vramUsedMb={vramUsedMb}
            vramTotalMb={vramTotalMb}
            showLabels={true}
          />
        </div>

        {/* Unload & Pause Actions */}
        <div className="flex items-center gap-2 pt-2 border-t border-white/[0.06]">
          <SpecularButton
            variant="secondary"
            size="sm"
            onClick={handleUnload}
            loading={unloading}
            className="flex-1 text-[11px]"
          >
            Evict GPU VRAM
          </SpecularButton>

          {onTogglePauseGovernor && (
            <SpecularButton
              variant={governorTier === "PAUSED" ? "warning" : "secondary"}
              size="sm"
              onClick={onTogglePauseGovernor}
              className="text-[11px]"
            >
              {governorTier === "PAUSED" ? "Resume" : "Pause"}
            </SpecularButton>
          )}
        </div>
      </div>

      {/* 5-Model Topology Table */}
      <div className="space-y-2">
        <span className="font-mono text-[11px] text-tertiary uppercase tracking-wider font-semibold px-1">
          Local Model Routing Table
        </span>

        <div className="space-y-1.5">
          {modelList.map((model) => (
            <div
              key={model.role}
              className="p-2.5 rounded-xl bg-black/25 border border-white/[0.06] flex items-center justify-between text-xs font-mono"
            >
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span
                    className={`font-semibold text-[10px] px-1.5 py-0.2 rounded ${
                      model.role === "MAIN"
                        ? "bg-reasoning/20 text-reasoning"
                        : model.role === "FAST"
                        ? "bg-accent/20 text-accent"
                        : model.role === "VISION"
                        ? "bg-warning/20 text-warning"
                        : "bg-memory/20 text-memory"
                    }`}
                  >
                    {model.role}
                  </span>
                  <span className="font-medium text-primary">{model.name}</span>
                </div>
                <div className="text-[10px] text-tertiary">
                  {model.provider} · {(model.contextWindow / 1024).toFixed(0)}k ctx
                  {model.quantization && ` · ${model.quantization}`}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {model.vramUsageMb && (
                  <span className="text-[10px] text-tertiary">
                    {(model.vramUsageMb / 1024).toFixed(1)} GB
                  </span>
                )}
                <span className="w-2 h-2 rounded-full bg-success" title="Online & Ready" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sandbox & Tool Permissions Toggles */}
      <div className="p-3.5 rounded-card bg-black/20 border border-white/[0.06] space-y-3">
        <span className="font-mono text-[11px] text-tertiary uppercase tracking-wider font-semibold block">
          Execution Environment
        </span>

        <div className="space-y-2 text-xs">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-secondary">Terminal Sandbox</span>
            <input
              type="checkbox"
              checked={terminalEnabled}
              onChange={(e) => setTerminalEnabled(e.target.checked)}
              className="w-4 h-4 accent-accent rounded"
            />
          </label>

          <label className="flex items-center justify-between cursor-pointer">
            <span className="text-secondary">External Web Search</span>
            <input
              type="checkbox"
              checked={webSearchEnabled}
              onChange={(e) => setWebSearchEnabled(e.target.checked)}
              className="w-4 h-4 accent-accent rounded"
            />
          </label>
        </div>
      </div>
    </div>
  );
}
