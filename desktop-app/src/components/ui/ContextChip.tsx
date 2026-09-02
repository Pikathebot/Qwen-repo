"use client";

import React from "react";

export type ContextChipType = "file" | "memory" | "skill" | "model" | "tool";

export interface ContextChipProps {
  type?: ContextChipType;
  label: string;
  subLabel?: string;
  onRemove?: () => void;
  onClick?: () => void;
  className?: string;
}

/**
 * ContextChip — Micro capsule for active context tokens (files, memories, skills, models, tools)
 */
export function ContextChip({
  type = "file",
  label,
  subLabel,
  onRemove,
  onClick,
  className = "",
}: ContextChipProps) {
  let badgeColor = "bg-accent/15 text-accent border-accent/25";
  let icon = (
    <svg className="w-3 h-3 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  );

  if (type === "memory") {
    badgeColor = "bg-memory/15 text-memory border-memory/25";
    icon = (
      <svg className="w-3 h-3 text-memory" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    );
  } else if (type === "skill") {
    badgeColor = "bg-reasoning/15 text-reasoning border-reasoning/25";
    icon = (
      <svg className="w-3 h-3 text-reasoning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
      </svg>
    );
  } else if (type === "model") {
    badgeColor = "bg-reasoning/15 text-reasoning border-reasoning/25";
    icon = <span className="w-1.5 h-1.5 rounded-full bg-reasoning animate-pulse" />;
  } else if (type === "tool") {
    badgeColor = "bg-neutral/15 text-neutral border-neutral/25";
    icon = (
      <svg className="w-3 h-3 text-neutral" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      </svg>
    );
  }

  return (
    <div
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-pill text-xs font-mono border backdrop-blur-md transition-all duration-fast ${badgeColor} ${
        onClick ? "cursor-pointer hover:brightness-125" : ""
      } ${className}`}
    >
      <span className="flex-shrink-0">{icon}</span>
      <span className="truncate max-w-[180px] font-medium">{label}</span>
      {subLabel && <span className="opacity-60 text-[10px]">· {subLabel}</span>}
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="ml-0.5 -mr-1 p-0.5 hover:bg-white/10 rounded-full text-current opacity-70 hover:opacity-100 transition-opacity"
          aria-label={`Remove ${label}`}
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}
