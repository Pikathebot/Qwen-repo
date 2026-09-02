"use client";

import React, { useState, useEffect, useRef } from "react";
import { GlassPanel } from "../ui/GlassPanel";
import { GlassCard } from "../ui/GlassCard";
import { SpecularButton } from "../ui/SpecularButton";

export interface SpotlightOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  onExpandToWorkspace?: (query: string) => void;
  projectName?: string;
  modelName?: string;
}

export function SpotlightOverlay({
  isOpen,
  onClose,
  onExpandToWorkspace,
  projectName = "Unreal Inventory System",
  modelName = "Qwen3-30B",
}: SpotlightOverlayProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onExpandToWorkspace?.(query.trim());
      onClose();
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-2xl animate-in fade-in duration-fast"
    >
      <div className="w-full max-w-[680px]">
        <GlassPanel
          variant="stage"
          radius="stage"
          className="p-5 space-y-4 shadow-2xl border-t border-white/35 backdrop-blur-3xl"
        >
          {/* Top Search Input & Tokens */}
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex items-center gap-3 px-3 py-2 rounded-2xl bg-black/40 border border-white/10">
              <svg className="w-5 h-5 text-accent flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask JARVIS or run local command..."
                className="w-full bg-transparent text-sm text-primary placeholder-secondary/50 focus:outline-none font-sans"
              />
            </div>

            {/* Context Token Row */}
            <div className="flex items-center justify-between px-1 text-xs">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-pill font-mono text-[10px] bg-accent/15 text-accent border border-accent/25">
                  {projectName}
                </span>
                <span className="px-2.5 py-0.5 rounded-pill font-mono text-[10px] bg-reasoning/15 text-reasoning border border-reasoning/25">
                  {modelName}
                </span>
                <span className="px-2.5 py-0.5 rounded-pill font-mono text-[10px] bg-success/15 text-success border border-success/25">
                  Safe Tools
                </span>
              </div>

              <span className="text-[10px] font-mono text-tertiary">ESC to close</span>
            </div>
          </form>

          {/* Compact Result Cards */}
          <div className="space-y-2 pt-2 border-t border-white/[0.06]">
            <GlassCard variant="default" className="p-3 space-y-1">
              <div className="flex items-center justify-between text-[11px] font-mono">
                <span className="text-accent font-semibold">InventoryComponent.cpp (Patch)</span>
                <span className="text-success">Ready for review</span>
              </div>
              <p className="text-xs text-secondary truncate">
                Updated GiveItemAbility to associate source object with GameplayAbilitySpec.
              </p>
            </GlassCard>

            <GlassCard variant="warning" className="p-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="w-1.5 h-1.5 rounded-full bg-warning flex-shrink-0" />
                <span className="text-xs text-warning truncate font-medium">
                  Pending Approval: Write patch to InventoryComponent.cpp
                </span>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-warning/20 text-warning font-semibold flex-shrink-0">
                CONFIRMATION_REQUIRED
              </span>
            </GlassCard>
          </div>

          {/* Action Footer */}
          <div className="flex items-center justify-between pt-2 border-t border-white/[0.06]">
            <span className="text-[11px] font-mono text-tertiary">Alt + Space Quick Access</span>
            <SpecularButton
              variant="primary"
              size="sm"
              onClick={() => {
                onExpandToWorkspace?.(query);
                onClose();
              }}
            >
              Expand to Workspace →
            </SpecularButton>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
