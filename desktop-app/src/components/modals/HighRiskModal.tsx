"use client";

import React, { useEffect, useRef } from "react";
import { GlassPanel } from "../ui/GlassPanel";
import { SpecularButton } from "../ui/SpecularButton";
import { PendingConfirmation } from "@/lib/types";

export interface HighRiskModalProps {
  isOpen: boolean;
  confirmation: PendingConfirmation | null;
  onCancel: () => void;
  onAllowOnce: (actionId: string) => void;
  onAllowForRun: (actionId: string) => void;
}

/**
 * HighRiskModal — Focus-Trapped M3 Stage Glass Modal for HIGH_RISK Actions
 * Cannot be casually dismissed. Explicitly presents dangerous operations to the human.
 */
export function HighRiskModal({
  isOpen,
  confirmation,
  onCancel,
  onAllowOnce,
  onAllowForRun,
}: HighRiskModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onCancel();
      }
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
      modalRef.current?.focus();
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onCancel]);

  if (!isOpen || !confirmation) return null;

  const argsFormatted =
    typeof confirmation.args === "string"
      ? confirmation.args
      : JSON.stringify(confirmation.args, null, 2);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="high-risk-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xl animate-in fade-in duration-std"
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        className="w-full max-w-lg outline-none"
      >
        <GlassPanel
          variant="stage"
          radius="stage"
          className="p-6 space-y-5 shadow-2xl border-t-2 border-danger/80 ring-1 ring-danger/30 shadow-danger/10"
        >
          {/* Header */}
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-2xl bg-danger/20 border-t border-danger/60 flex items-center justify-center text-danger flex-shrink-0 shadow-lg">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div className="space-y-1 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-danger/25 text-danger font-bold uppercase tracking-wider">
                  HIGH_RISK ACTION
                </span>
                <span className="text-[10px] font-mono text-tertiary">
                  ID: {confirmation.action_id}
                </span>
              </div>
              <h2 id="high-risk-title" className="text-base font-bold text-primary">
                Explicit Safety Authorization Required
              </h2>
              <p className="text-xs text-secondary leading-relaxed font-sans">
                {confirmation.reason ||
                  "The agent is attempting an action that can modify critical system resources, execute shell scripts, or delete files."}
              </p>
            </div>
          </div>

          {/* Action Parameters & Payload */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px] font-mono text-tertiary">
              <span className="font-semibold text-secondary">Target Tool: {confirmation.tool}</span>
              <span>Local Sandbox</span>
            </div>
            <pre className="p-3 rounded-card bg-black/60 border border-white/10 text-xs font-mono text-danger/90 overflow-x-auto max-h-48 whitespace-pre-wrap select-text">
              {argsFormatted}
            </pre>
          </div>

          <div className="p-3 rounded-card bg-danger/10 border border-danger/20 text-xs text-secondary leading-relaxed">
            <p className="font-medium text-danger/90 mb-0.5">Deterministic Safety Enforcement</p>
            JARVIS never self-authorizes high-risk operations. The execution is blocked until you explicitly authorize this command.
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-2 border-t border-white/10">
            <SpecularButton variant="secondary" onClick={onCancel}>
              Cancel & Abort
            </SpecularButton>

            <div className="flex items-center gap-2">
              <SpecularButton
                variant="warning"
                onClick={() => onAllowOnce(confirmation.action_id)}
              >
                Allow Once
              </SpecularButton>
              <SpecularButton
                variant="danger"
                onClick={() => onAllowForRun(confirmation.action_id)}
              >
                Allow for This Run
              </SpecularButton>
            </div>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
