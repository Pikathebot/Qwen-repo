"use client";

import React, { useState, useRef, useEffect, KeyboardEvent } from "react";

interface ComposerProps {
  onSendMessage: (text: string) => void;
  isLoading: boolean;
  onAbort?: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export function Composer({
  onSendMessage,
  isLoading,
  onAbort,
  disabled,
  placeholder = "Message Jarvis...",
}: ComposerProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!isLoading && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isLoading]);

  // Adjust height dynamically up to 180px
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

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || isLoading || disabled) return;
    onSendMessage(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  return (
    <div className="relative p-4 bg-void/80 border-t border-subtle backdrop-blur-md">
      <div className="max-w-4xl mx-auto flex items-end gap-2 bg-surface rounded-2xl border border-subtle focus-within:border-cyan-accent/50 focus-within:ring-1 focus-within:ring-cyan-accent/20 transition-all p-2 shadow-lg">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            handleInput();
          }}
          onKeyDown={handleKeyDown}
          placeholder={isLoading ? "Jarvis is processing..." : placeholder}
          disabled={disabled || isLoading}
          rows={1}
          className="flex-1 bg-transparent text-sm text-text-main placeholder:text-text-muted/50 resize-none px-3 py-1.5 focus:outline-none max-h-[180px] font-sans"
        />

        <div className="flex items-center gap-1.5 pb-0.5 pr-0.5">
          {isLoading ? (
            <button
              onClick={onAbort}
              className="p-2 rounded-xl bg-rose-accent/20 hover:bg-rose-accent/30 text-rose-accent transition-colors shadow-sm"
              title="Stop Generation"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
              </svg>
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!text.trim() || disabled}
              className="p-2 rounded-xl bg-cyan-accent text-void font-bold hover:bg-cyan-400 disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-sm active:scale-95"
              title="Send Message (Enter)"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
          )}
        </div>
      </div>
      <div className="text-[11px] text-center text-text-muted/40 mt-2 font-mono">
        Enter to send · Shift+Enter for new line · 100% Offline Local Engine
      </div>
    </div>
  );
}
