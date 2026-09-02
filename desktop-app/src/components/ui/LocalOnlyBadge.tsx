"use client";

import React from "react";

export type LocalPrivacyStatus = "local" | "mock" | "fallback_warning" | "offline";

export interface LocalOnlyBadgeProps {
  status?: LocalPrivacyStatus;
  chunksCount?: number;
  className?: string;
  onClick?: () => void;
}

/**
 * LocalOnlyBadge — Trust & Privacy Badge
 * Confirms deterministic local execution without telemetry or cloud dependency.
 * Features subtle Sandbox/Mock mode when offline.
 */
export function LocalOnlyBadge({
  status = "local",
  chunksCount,
  className = "",
  onClick,
}: LocalOnlyBadgeProps) {
  let badgeStyle = "bg-accent/10 border-accent/25 text-accent";
  let label = "Local only";
  let icon = (
    <svg className="w-3.5 h-3.5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  );

  if (status === "mock") {
    badgeStyle = "bg-white/[0.04] border-white/15 text-tertiary border-dashed";
    label = "Local only · Sandbox";
    icon = (
      <svg className="w-3.5 h-3.5 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
        />
      </svg>
    );
  } else if (status === "fallback_warning") {
    badgeStyle = "bg-warning/15 border-warning/30 text-warning";
    label = "Cloud fallback active";
    icon = (
      <svg className="w-3.5 h-3.5 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
        />
      </svg>
    );
  } else if (status === "offline") {
    badgeStyle = "bg-white/[0.04] border-white/10 text-tertiary";
    label = "Offline";
    icon = (
      <span className="w-1.5 h-1.5 rounded-full bg-tertiary" />
    );
  }

  return (
    <div
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border backdrop-blur-md transition-all ${badgeStyle} ${
        onClick ? "cursor-pointer hover:brightness-125" : ""
      } ${className}`}
      title={
        status === "mock"
          ? "Running in isolated local mock mode. Ready for FastAPI connection."
          : "All embeddings, reasoning, and context operate 100% locally."
      }
    >
      <span className="flex-shrink-0">{icon}</span>
      <span className="font-semibold">{label}</span>
      {chunksCount !== undefined && (
        <>
          <span className="opacity-40">·</span>
          <span className="text-secondary font-normal">{chunksCount.toLocaleString()} chunks</span>
        </>
      )}
    </div>
  );
}
