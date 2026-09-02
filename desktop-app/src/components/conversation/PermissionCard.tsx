"use client";

import React, { useState } from "react";
import { PendingConfirmation } from "@/lib/types";
import { GlassCard } from "../ui/GlassCard";
import { SpecularButton } from "../ui/SpecularButton";
import { DiffViewer } from "./DiffViewer";

export interface PermissionCardProps {
  confirmation: PendingConfirmation;
  onApprove: (actionId: string) => void;
  onReject: (actionId: string) => void;
  className?: string;
}

/**
 * PermissionCard — Deterministic confirmation surface
 * Renders LOW_RISK notices and CONFIRMATION_REQUIRED amber glass cards with integrated diff preview.
 */
export function PermissionCard({
  confirmation,
  onApprove,
  onReject,
  className = "",
}: PermissionCardProps) {
  const [showDiff, setShowDiff] = useState(true);
  const tier = confirmation.risk_tier || "CONFIRMATION_REQUIRED";

  if (tier === "LOW_RISK") {
    return (
      <div
        className={`flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-xs text-secondary font-mono ${className}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-accent" />
        <span>Low-risk action auto-authorized:</span>
        <span className="text-primary font-semibold">{confirmation.tool}</span>
      </div>
    );
  }

  return (
    <GlassCard variant="warning" className={`p-4 space-y-3 shadow-xl ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-warning/20 border-t border-warning/40 flex items-center justify-center text-warning flex-shrink-0">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-xs text-warning tracking-wide font-mono">
                SAFETY CONFIRMATION REQUIRED
              </span>
              <span className="text-[10px] px-2 py-0.2 rounded-full font-mono bg-warning/20 text-warning font-semibold border border-warning/30">
                {tier}
              </span>
            </div>
            <p className="text-xs text-primary/90 mt-0.5 font-medium">
              {confirmation.reason || `Agent requests permission to execute ${confirmation.tool}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {confirmation.diffPayload && (
            <button
              onClick={() => setShowDiff(!showDiff)}
              className="px-2.5 py-1 rounded-pill bg-white/[0.08] hover:bg-white/[0.14] text-primary text-xs font-mono transition-colors"
            >
              {showDiff ? "Hide diff" : "View diff"}
            </button>
          )}
        </div>
      </div>

      {/* Embedded Diff Viewer if file modification */}
      {confirmation.diffPayload && showDiff && (
        <DiffViewer
          diff={confirmation.diffPayload}
          showActions={false}
          className="mt-2"
        />
      )}

      {/* Tool Arguments View if no diff */}
      {!confirmation.diffPayload && confirmation.args && (
        <pre className="p-2.5 rounded-xl bg-black/40 border border-white/10 text-[11px] font-mono text-secondary overflow-x-auto">
          {typeof confirmation.args === "string"
            ? confirmation.args
            : JSON.stringify(confirmation.args, null, 2)}
        </pre>
      )}

      {/* Action Buttons */}
      <div className="flex items-center justify-between pt-1 border-t border-warning/20">
        <span className="text-[10px] font-mono text-secondary">
          Action ID: {confirmation.action_id}
        </span>
        <div className="flex items-center gap-2.5">
          <SpecularButton
            variant="secondary"
            size="sm"
            onClick={() => onReject(confirmation.action_id)}
          >
            Reject
          </SpecularButton>
          <SpecularButton
            variant="warning"
            size="sm"
            onClick={() => onApprove(confirmation.action_id)}
          >
            Approve & Continue
          </SpecularButton>
        </div>
      </div>
    </GlassCard>
  );
}
