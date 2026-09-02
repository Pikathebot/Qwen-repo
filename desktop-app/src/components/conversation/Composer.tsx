"use client";

import React, { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Attachment } from "@/lib/types";
import { GlassPanel } from "../ui/GlassPanel";
import { SpecularButton } from "../ui/SpecularButton";
import { ContextChip } from "../ui/ContextChip";
import { ModelBadge } from "../ui/ModelBadge";

export interface ComposerProps {
  onSendMessage: (text: string, attachments?: Attachment[]) => void;
  isLoading: boolean;
  onAbort?: () => void;
  disabled?: boolean;
  placeholder?: string;
  projectName?: string;
  activeModelName?: string;
  activeSkillsCount?: number;
  onOpenModelSelector?: () => void;
  onOpenSkillsBrowser?: () => void;
  className?: string;
}

/**
 * Composer — Floating 28px M2 Liquid Glass Input Capsule
 */
export function Composer({
  onSendMessage,
  isLoading,
  onAbort,
  disabled = false,
  placeholder = "Message JARVIS (e.g. 'Refactor InventoryComponent.cpp for GAS')...",
  projectName,
  activeModelName = "Qwen3-30B",
  activeSkillsCount = 3,
  onOpenModelSelector,
  onOpenSkillsBrowser,
  className = "",
}: ComposerProps) {
  const [text, setText] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isLoading && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isLoading]);

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      setAttachedFiles((prev) => [...prev, ...filesArray]);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    const trimmed = text.trim();
    if ((!trimmed && attachedFiles.length === 0) || isLoading || disabled) return;

    // Convert local files to mock attachment structures if needed
    const attachments: Attachment[] = attachedFiles.map((file, idx) => ({
      id: `att_${Date.now()}_${idx}`,
      filename: file.name,
      path: `uploads/${file.name}`,
      size_bytes: file.size,
      created_at: new Date().toISOString(),
    }));

    onSendMessage(trimmed, attachments);
    setText("");
    setAttachedFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  return (
    <div className={`w-full max-w-[72ch] mx-auto px-4 pb-4 select-none ${className}`}>
      <GlassPanel
        variant="elevated"
        radius="stage"
        className="p-3 space-y-2 shadow-2xl border-t border-white/30 backdrop-blur-3xl"
      >
        {/* Attached Files Row */}
        {attachedFiles.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-1 pb-1">
            {attachedFiles.map((file, idx) => (
              <ContextChip
                key={idx}
                type="file"
                label={file.name}
                subLabel={`${(file.size / 1024).toFixed(0)}KB`}
                onRemove={() => removeFile(idx)}
              />
            ))}
          </div>
        )}

        {/* Text Input Area */}
        <div className="relative flex items-center">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              handleInput();
            }}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder}
            className="w-full max-h-[180px] bg-transparent text-sm text-primary placeholder-secondary/50 focus:outline-none resize-none px-2 py-1.5 leading-relaxed font-sans"
          />
        </div>

        {/* Bottom Capsule Controls: Tokens + Actions */}
        <div className="flex items-center justify-between pt-1 border-t border-white/[0.06] text-xs">
          {/* Left Token Badges */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {/* Attachment Button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              multiple
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 rounded-full text-secondary hover:text-primary hover:bg-white/[0.08] transition-colors"
              title="Attach files to context"
              aria-label="Attach file"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                />
              </svg>
            </button>

            {/* Model Badge Chip */}
            <ModelBadge
              role="MAIN"
              modelName={activeModelName}
              size="sm"
              onClick={onOpenModelSelector}
            />

            {/* Project Context Chip */}
            {projectName && (
              <span className="hidden sm:inline-flex px-2 py-0.5 rounded-full font-mono text-[10px] bg-white/[0.06] text-secondary border border-white/10">
                {projectName}
              </span>
            )}

            {/* Skills Chip */}
            {onOpenSkillsBrowser && (
              <button
                type="button"
                onClick={onOpenSkillsBrowser}
                className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-mono text-[10px] bg-reasoning/10 text-reasoning border border-reasoning/25 hover:bg-reasoning/20 transition-colors"
                title="View active skills"
              >
                <span className="w-1 h-1 rounded-full bg-reasoning" />
                <span>{activeSkillsCount} skills</span>
              </button>
            )}
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center gap-2">
            {isLoading ? (
              <SpecularButton
                variant="danger"
                size="sm"
                onClick={onAbort}
                className="px-3"
                icon={
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
                  </svg>
                }
              >
                Stop
              </SpecularButton>
            ) : (
              <SpecularButton
                variant="primary"
                size="sm"
                onClick={handleSubmit}
                disabled={(!text.trim() && attachedFiles.length === 0) || disabled}
                className="px-3"
                icon={
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                }
              >
                Send
              </SpecularButton>
            )}
          </div>
        </div>
      </GlassPanel>
    </div>
  );
}
