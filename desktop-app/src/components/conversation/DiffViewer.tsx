"use client";

import React, { useState } from "react";
import { DiffPayload } from "@/lib/types";
import { SpecularButton } from "../ui/SpecularButton";

export interface DiffViewerProps {
  diff: DiffPayload;
  onApprove?: () => void;
  onReject?: () => void;
  showActions?: boolean;
  className?: string;
}

/**
 * DiffViewer — Liquid Glass File Diff Viewer
 * Displays additions in soft green glass and deletions in soft red glass.
 */
export function DiffViewer({
  diff,
  onApprove,
  onReject,
  showActions = true,
  className = "",
}: DiffViewerProps) {
  const [viewMode, setViewMode] = useState<"unified" | "split">("unified");

  const oldLines = diff.oldContent.split("\n");
  const newLines = diff.newContent.split("\n");

  return (
    <div
      className={`rounded-card overflow-hidden border border-white/10 bg-black/40 backdrop-blur-md text-xs font-mono shadow-inner ${className}`}
    >
      {/* Diff Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-white/[0.04] border-b border-white/[0.08]">
        <div className="flex items-center gap-2 min-w-0">
          <svg className="w-4 h-4 text-warning flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          <span className="font-semibold text-primary truncate">{diff.filePath}</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded bg-white/[0.08] text-secondary">
            Agent proposed
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[11px]">
            {diff.additions !== undefined && (
              <span className="text-success font-semibold">+{diff.additions}</span>
            )}
            {diff.deletions !== undefined && (
              <span className="text-danger font-semibold">-{diff.deletions}</span>
            )}
          </div>

          <div className="flex items-center bg-white/[0.06] rounded-pill p-0.5 border border-white/10 text-[10px]">
            <button
              onClick={() => setViewMode("unified")}
              className={`px-2 py-0.5 rounded-pill transition-all ${
                viewMode === "unified"
                  ? "bg-white/[0.16] text-primary font-semibold"
                  : "text-tertiary hover:text-secondary"
              }`}
            >
              Unified
            </button>
            <button
              onClick={() => setViewMode("split")}
              className={`px-2 py-0.5 rounded-pill transition-all ${
                viewMode === "split"
                  ? "bg-white/[0.16] text-primary font-semibold"
                  : "text-tertiary hover:text-secondary"
              }`}
            >
              Split
            </button>
          </div>
        </div>
      </div>

      {/* Diff Content View */}
      <div className="overflow-x-auto max-h-72 p-2 space-y-0.5 text-[11px] leading-relaxed select-text">
        {viewMode === "unified" ? (
          <div>
            {oldLines.map((line, idx) => (
              <div
                key={`del-${idx}`}
                className="flex items-start gap-3 px-2 py-0.5 rounded bg-danger/10 text-danger/90 border-l-2 border-danger"
              >
                <span className="w-6 text-right text-danger/60 select-none">-</span>
                <pre className="flex-1 font-mono whitespace-pre-wrap">{line}</pre>
              </div>
            ))}
            {newLines.map((line, idx) => (
              <div
                key={`add-${idx}`}
                className="flex items-start gap-3 px-2 py-0.5 rounded bg-success/10 text-success/90 border-l-2 border-success"
              >
                <span className="w-6 text-right text-success/60 select-none">+</span>
                <pre className="flex-1 font-mono whitespace-pre-wrap">{line}</pre>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 rounded bg-danger/5 border border-danger/20">
              <div className="text-[10px] text-danger/70 font-semibold mb-1 uppercase">Original</div>
              <pre className="text-danger/90 whitespace-pre-wrap">{diff.oldContent}</pre>
            </div>
            <div className="p-2 rounded bg-success/5 border border-success/20">
              <div className="text-[10px] text-success/70 font-semibold mb-1 uppercase">Proposed</div>
              <pre className="text-success/90 whitespace-pre-wrap">{diff.newContent}</pre>
            </div>
          </div>
        )}
      </div>

      {/* Action Footer */}
      {showActions && (onApprove || onReject) && (
        <div className="flex items-center justify-between px-3.5 py-2 bg-white/[0.02] border-t border-white/[0.06]">
          <span className="text-[10px] text-tertiary">
            Approval writes changes directly to workspace disk
          </span>
          <div className="flex items-center gap-2">
            {onReject && (
              <SpecularButton variant="secondary" size="sm" onClick={onReject}>
                Reject
              </SpecularButton>
            )}
            {onApprove && (
              <SpecularButton variant="success" size="sm" onClick={onApprove}>
                Approve & Write
              </SpecularButton>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
