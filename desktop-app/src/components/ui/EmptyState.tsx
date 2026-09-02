"use client";

import React from "react";
import { SpecularButton } from "./SpecularButton";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

/**
 * EmptyState — Translucent glass empty state display
 */
export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-center max-w-sm mx-auto ${className}`}
    >
      <div className="w-12 h-12 rounded-2xl glass-m2 flex items-center justify-center text-accent mb-4 border-t border-white/30 shadow-lg">
        {icon || (
          <svg className="w-6 h-6 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        )}
      </div>
      <h3 className="text-sm font-semibold text-primary mb-1">{title}</h3>
      <p className="text-xs text-secondary leading-relaxed mb-5">{description}</p>
      {actionLabel && onAction && (
        <SpecularButton variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </SpecularButton>
      )}
    </div>
  );
}
