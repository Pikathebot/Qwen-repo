"use client";

import React, { useState } from "react";
import { ToolStep } from "@/lib/types";

interface ToolStepCardProps {
  step: ToolStep;
}

export function ToolStepCard({ step }: ToolStepCardProps) {
  const [isOpen, setIsOpen] = useState(false);

  let statusBadge = (
    <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-cyan-accent/10 text-cyan-accent border border-cyan-accent/30 animate-pulse">
      <span className="w-1.5 h-1.5 rounded-full bg-cyan-accent animate-ping" />
      Running
    </span>
  );

  if (step.status === "success") {
    statusBadge = (
      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-accent/10 text-emerald-accent border border-emerald-accent/30">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
        Completed
      </span>
    );
  } else if (step.status === "error") {
    statusBadge = (
      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-accent/10 text-rose-accent border border-rose-accent/30">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
        </svg>
        Failed
      </span>
    );
  }

  const argsStr = step.args?.raw && typeof step.args.raw === "string"
    ? step.args.raw
    : JSON.stringify(step.args || {}, null, 2);
  const resultStr = typeof step.result === "string" 
    ? step.result 
    : JSON.stringify(step.result || {}, null, 2);

  return (
    <div className="my-2 rounded-xl border border-subtle bg-surface/70 overflow-hidden text-xs">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 hover:bg-white/[0.02] transition-colors text-left"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1 rounded bg-void border border-subtle text-cyan-accent">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <span className="font-mono text-text-main font-semibold truncate">{step.tool}</span>
        </div>

        <div className="flex items-center gap-2">
          {statusBadge}
          <svg
            className={`w-3.5 h-3.5 text-text-muted transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {isOpen && (
        <div className="px-3.5 pb-3 pt-1 border-t border-subtle/60 bg-void/40 space-y-2">
          {step.args && Object.keys(step.args).length > 0 && (
            <div>
              <div className="text-[10px] uppercase font-semibold text-text-muted mb-1">Arguments</div>
              <pre className="p-2 bg-void text-text-muted font-mono text-[11px] rounded-lg border border-subtle overflow-x-auto max-h-40">
                {argsStr}
              </pre>
            </div>
          )}

          {step.result !== undefined && (
            <div>
              <div className="text-[10px] uppercase font-semibold text-text-muted mb-1">Result</div>
              <pre className="p-2 bg-void text-text-main font-mono text-[11px] rounded-lg border border-subtle overflow-x-auto max-h-56">
                {resultStr}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
