"use client";

import React from "react";
import { SkillItem } from "@/lib/types";
import { GlassPanel } from "../ui/GlassPanel";
import { GlassCard } from "../ui/GlassCard";

export interface SkillsBrowserModalProps {
  isOpen: boolean;
  onClose: () => void;
  skills: SkillItem[];
  onToggleSkill?: (skillId: string) => void;
}

export function SkillsBrowserModal({
  isOpen,
  onClose,
  skills,
  onToggleSkill,
}: SkillsBrowserModalProps) {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xl animate-in fade-in duration-std"
    >
      <div className="w-full max-w-xl max-h-[85vh] flex flex-col">
        <GlassPanel
          variant="stage"
          radius="stage"
          className="p-6 flex flex-col h-full space-y-4 shadow-2xl border-t border-white/30"
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.08]">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-reasoning/20 border-t border-reasoning/40 flex items-center justify-center text-reasoning flex-shrink-0">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
              </div>
              <div>
                <h2 className="text-base font-bold text-primary">Active Agent Skills</h2>
                <p className="text-xs text-secondary font-sans">
                  Domain specializations and verified tools loaded into the agent context.
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

          {/* Skills List */}
          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
            {skills.map((skill) => (
              <GlassCard
                key={skill.id}
                variant={skill.isActive ? "active" : "default"}
                className="p-3.5 flex items-start justify-between gap-3"
              >
                <div className="space-y-1 flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-semibold text-primary">{skill.name}</h4>
                    {skill.toolsCount !== undefined && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-white/[0.06] text-tertiary">
                        {skill.toolsCount} tools
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-secondary font-sans leading-relaxed">
                    {skill.description}
                  </p>
                </div>

                <div className="flex items-center pt-1">
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={skill.isActive}
                      onChange={() => onToggleSkill?.(skill.id)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-accent"></div>
                  </label>
                </div>
              </GlassCard>
            ))}
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
