"use client";

import React from "react";
import { ModelRole } from "@/lib/types";

export interface ModelBadgeProps {
  role?: ModelRole;
  modelName: string;
  provider?: string;
  isActive?: boolean;
  size?: "sm" | "md";
  className?: string;
  onClick?: () => void;
}

/**
 * ModelBadge — Micro-label indicator for local/remote model status
 * Example: MAIN · Qwen3-30B with animated reasoning dot.
 */
export function ModelBadge({
  role = "MAIN",
  modelName,
  provider,
  isActive = true,
  size = "md",
  className = "",
  onClick,
}: ModelBadgeProps) {
  let roleColor = "text-reasoning bg-reasoning/10 border-reasoning/30";
  let dotColor = "bg-reasoning";

  if (role === "FAST") {
    roleColor = "text-accent bg-accent/10 border-accent/30";
    dotColor = "bg-accent";
  } else if (role === "EMBED" || role === "RERANK") {
    roleColor = "text-memory bg-memory/10 border-memory/30";
    dotColor = "bg-memory";
  } else if (role === "VISION") {
    roleColor = "text-warning bg-warning/10 border-warning/30";
    dotColor = "bg-warning";
  }

  const sizeClass = size === "sm" ? "text-[10px] px-2 py-0.5" : "text-[11px] px-2.5 py-1";

  return (
    <div
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full font-mono uppercase tracking-wider border backdrop-blur-md transition-all ${roleColor} ${
        onClick ? "cursor-pointer hover:brightness-125" : ""
      } ${sizeClass} ${className}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${dotColor} ${
          isActive ? "animate-pulse" : "opacity-40"
        }`}
      />
      <span className="font-semibold">{role}</span>
      <span className="opacity-40">·</span>
      <span className="text-primary font-normal truncate max-w-[140px]">{modelName}</span>
      {provider && <span className="opacity-40 text-[9px] lowercase">({provider})</span>}
    </div>
  );
}
