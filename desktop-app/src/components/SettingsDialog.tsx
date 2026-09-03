"use client";

import React, { useState } from "react";
import { UseGovernorReturn } from "@/hooks/useGovernor";
import { usePersona } from "@/hooks/usePersona";

interface SettingsDialogProps {
  isOpen: boolean;
  onClose: () => void;
  governor: UseGovernorReturn;
  selectedModel: string | null;
  onSelectModel: (model: string | null) => void;
}

export function SettingsDialog({
  isOpen,
  onClose,
  governor,
  selectedModel,
  onSelectModel,
}: SettingsDialogProps) {
  const { availableModels, configuredModel, activeBackend, ollamaConnected } = governor;
  const [customModelInput, setCustomModelInput] = useState("");
  const { persona, selectPersona, applyOverrides, resetOverrides } = usePersona();

  if (!isOpen) return null;

  const defaultPresets = [
    { label: "Default Main (Qwen3.5-9B)", value: "main", desc: "Highest intelligence & deep reasoning" },
    { label: "Default Fast (Qwen3.5-4B)", value: "fast", desc: "Ultra-low latency responses" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-surface border border-subtle w-full max-w-lg rounded-2xl p-6 shadow-2xl space-y-6 animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between border-b border-subtle pb-4">
          <div>
            <h2 className="text-base font-semibold text-text-main">Runtime & Model Settings</h2>
            <p className="text-xs text-text-muted mt-0.5">Configure local model execution targets</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-text-muted hover:text-text-main hover:bg-white/5 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Active Backend Overview */}
        <div className="p-3.5 bg-void rounded-xl border border-subtle flex items-center justify-between text-xs">
          <div>
            <span className="text-text-muted">Active Primary Provider: </span>
            <span className="font-mono text-cyan-accent font-medium ml-1">{activeBackend}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${ollamaConnected ? "bg-emerald-accent" : "bg-text-muted/40"}`} />
            <span className="text-text-muted text-[11px]">Ollama Fallback</span>
          </div>
        </div>

        {/* Model Presets */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-text-muted">Target Model Profile</label>
          <div className="grid grid-cols-1 gap-2">
            {defaultPresets.map((preset) => {
              const isSelected = selectedModel === preset.value || (!selectedModel && preset.value === "main");
              return (
                <button
                  key={preset.value}
                  onClick={() => onSelectModel(preset.value)}
                  className={`flex items-start justify-between p-3 rounded-xl border text-left transition-all ${
                    isSelected
                      ? "bg-cyan-accent/10 border-cyan-accent/40 text-text-main"
                      : "bg-void/60 border-subtle hover:border-white/20 text-text-muted"
                  }`}
                >
                  <div>
                    <div className="text-xs font-medium text-text-main">{preset.label}</div>
                    <div className="text-[11px] text-text-muted mt-0.5">{preset.desc}</div>
                  </div>
                  {isSelected && (
                    <span className="px-2 py-0.5 text-[10px] font-semibold bg-cyan-accent/20 text-cyan-accent rounded-full border border-cyan-accent/30">
                      Active
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Available Models from Backend */}
        {availableModels && availableModels.length > 0 && (
          <div className="space-y-2">
            <label className="text-xs font-medium text-text-muted">Detected Local Models</label>
            <div className="max-h-36 overflow-y-auto space-y-1 pr-1">
              {availableModels.map((m) => (
                <button
                  key={m}
                  onClick={() => onSelectModel(m)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs font-mono truncate border transition-all ${
                    selectedModel === m
                      ? "bg-cyan-accent/10 border-cyan-accent/40 text-cyan-accent"
                      : "bg-void/40 border-subtle hover:border-white/10 text-text-muted hover:text-text-main"
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Persona */}
        {persona && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-text-muted">Persona</label>
              {Object.keys(persona.overrides).length > 0 && (
                <button
                  onClick={() => void resetOverrides()}
                  className="text-[11px] text-text-muted hover:text-cyan-accent transition-colors"
                >
                  Reset customizations
                </button>
              )}
            </div>
            <div className="grid grid-cols-1 gap-2">
              {persona.available.map((p) => {
                const isSelected = persona.active_id === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => void selectPersona(p.id)}
                    className={`flex items-start justify-between p-3 rounded-xl border text-left transition-all ${
                      isSelected
                        ? "bg-cyan-accent/10 border-cyan-accent/40 text-text-main"
                        : "bg-void/60 border-subtle hover:border-white/20 text-text-muted"
                    }`}
                  >
                    <div className="pr-3">
                      <div className="text-xs font-medium text-text-main capitalize">{p.id}</div>
                      <div className="text-[11px] text-text-muted mt-0.5">{p.description}</div>
                    </div>
                    {isSelected && (
                      <span className="shrink-0 px-2 py-0.5 text-[10px] font-semibold bg-cyan-accent/20 text-cyan-accent rounded-full border border-cyan-accent/30">
                        Active
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="space-y-1">
                <label className="text-[11px] text-text-muted">Addresses you as</label>
                <input
                  value={persona.active.address_term}
                  placeholder="none"
                  onChange={(e) => void applyOverrides({ address_term: e.target.value })}
                  className="w-full px-2.5 py-1.5 bg-void border border-subtle rounded-lg text-xs text-text-main outline-none focus:border-cyan-accent/40"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[11px] text-text-muted">Spoken voice</label>
                <select
                  value={persona.active.voice_id}
                  onChange={(e) => void applyOverrides({ voice_id: e.target.value })}
                  className="w-full px-2.5 py-1.5 bg-void border border-subtle rounded-lg text-xs text-text-main outline-none focus:border-cyan-accent/40"
                >
                  {Object.keys(persona.available_voices).map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] text-text-muted">
                Spoken reply length:{" "}
                {persona.active.max_speech_sentences === 0
                  ? "read everything aloud"
                  : `first ${persona.active.max_speech_sentences} sentence(s)`}
              </label>
              <input
                type="range"
                min={0}
                max={10}
                value={persona.active.max_speech_sentences}
                onChange={(e) =>
                  void applyOverrides({ max_speech_sentences: Number(e.target.value) })
                }
                className="w-full accent-cyan-accent"
              />
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2 border-t border-subtle">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-void hover:bg-white/5 text-text-main border border-subtle rounded-xl text-xs font-medium transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
