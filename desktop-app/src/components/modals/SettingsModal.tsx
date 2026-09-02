"use client";

import React, { useState } from "react";
import { GlassPanel } from "../ui/GlassPanel";
import { SpecularButton } from "../ui/SpecularButton";
import { GovernorStatus } from "@/lib/types";

export interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  governor?: GovernorStatus;
  selectedModel: string | null;
  onSelectModel: (model: string) => void;
  backendUrl?: string;
  onUpdateBackendUrl?: (url: string) => void;
}

export function SettingsModal({
  isOpen,
  onClose,
  governor,
  selectedModel,
  onSelectModel,
  backendUrl = "http://127.0.0.1:8000",
  onUpdateBackendUrl,
}: SettingsModalProps) {
  const [urlInput, setUrlInput] = useState(backendUrl);

  if (!isOpen) return null;

  const availableModels = governor?.availableModels?.length
    ? governor.availableModels
    : ["Qwen3-30B", "Qwen3-4B", "Qwen3-0.6B", "Qwen2.5-Coder-32B", "Llama-3.3-70B"];

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xl animate-in fade-in duration-std"
    >
      <div className="w-full max-w-lg">
        <GlassPanel
          variant="stage"
          radius="stage"
          className="p-6 space-y-5 shadow-2xl border-t border-white/30"
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.08]">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-white/[0.08] border-t border-white/20 flex items-center justify-center text-primary flex-shrink-0">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <div>
                <h2 className="text-base font-bold text-primary">System Settings</h2>
                <p className="text-xs text-secondary font-sans">
                  Local FastAPI engine and model provider configuration.
                </p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-tertiary hover:text-primary hover:bg-white/[0.08] transition-colors"
              aria-label="Close modal"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Model Selection */}
          <div className="space-y-2">
            <label className="text-xs font-mono text-tertiary uppercase tracking-wider block font-semibold">
              Default Main Model
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {availableModels.map((m) => {
                const isSelected = selectedModel === m;
                return (
                  <button
                    key={m}
                    onClick={() => onSelectModel(m)}
                    className={`p-3 rounded-xl border text-left text-xs font-mono transition-all ${
                      isSelected
                        ? "bg-accent/20 border-accent/40 text-accent font-semibold shadow-sm"
                        : "bg-black/30 border-white/5 text-secondary hover:text-primary hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="truncate">{m}</span>
                      {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-accent" />}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Local Backend URL */}
          <div className="space-y-1.5">
            <label className="text-xs font-mono text-tertiary uppercase tracking-wider block font-semibold">
              FastAPI Endpoint URL
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                className="flex-1 px-3 py-1.5 rounded-xl bg-black/40 border border-white/10 text-xs font-mono text-primary focus:outline-none focus:ring-1 focus:ring-accent"
              />
              <SpecularButton
                variant="secondary"
                size="sm"
                onClick={() => onUpdateBackendUrl?.(urlInput)}
              >
                Apply
              </SpecularButton>
            </div>
          </div>

          {/* Close Action */}
          <div className="flex justify-end pt-3 border-t border-white/[0.06]">
            <SpecularButton variant="primary" onClick={onClose}>
              Done
            </SpecularButton>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
