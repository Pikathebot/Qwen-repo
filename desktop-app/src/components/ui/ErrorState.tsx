"use client";

import React from "react";
import { GlassCard } from "./GlassCard";
import { SpecularButton } from "./SpecularButton";

export interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

/**
 * ErrorState — Signal glass error notification card
 */
export function ErrorState({
  title = "Execution Interrupted",
  message,
  onRetry,
  onDismiss,
  className = "",
}: ErrorStateProps) {
  return (
    <GlassCard variant="danger" className={`p-4 ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-danger/20 text-danger flex-shrink-0 border-t border-danger/40">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-danger">{title}</h4>
            <p className="text-xs text-primary/90 mt-0.5 leading-relaxed font-mono">{message}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {onRetry && (
            <SpecularButton variant="danger" size="sm" onClick={onRetry}>
              Retry
            </SpecularButton>
          )}
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="p-1 rounded-full text-danger/80 hover:text-danger hover:bg-danger/20 transition-colors"
              aria-label="Dismiss error"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </GlassCard>
  );
}
