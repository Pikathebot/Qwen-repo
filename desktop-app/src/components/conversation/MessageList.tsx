"use client";

import React, { useRef, useEffect } from "react";
import { Message } from "@/lib/types";
import { MessageBubble } from "./MessageBubble";
import { EmptyState } from "../ui/EmptyState";

export interface MessageListProps {
  messages: Message[];
  streamingMessageId?: string | null;
  onConfirmAction?: (actionId: string) => void;
  onDenyAction?: (actionId: string) => void;
  onQuickPrompt?: (prompt: string) => void;
  className?: string;
}

const SAMPLE_STARTER_PROMPTS = [
  "Refactor InventoryComponent.cpp to bind equipped items to GAS",
  "Review replicated struct definitions in InventoryTypes.h",
  "Inspect current Resource Governor tier and VRAM budget",
  "Scan project for GameplayAbilitySpecHandle usages",
];

/**
 * MessageList — Fluid Conversation Stream with 72ch Reading Constraint
 */
export function MessageList({
  messages,
  streamingMessageId,
  onConfirmAction,
  onDenyAction,
  onQuickPrompt,
  className = "",
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamingMessageId]);

  if (!messages || messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-[72ch] w-full text-center space-y-6">
          <EmptyState
            title="Local AI Workspace Ready"
            description="Direct deterministic code refactoring, AST file patches, GAS architecture assistance, and full local model execution."
          />

          {onQuickPrompt && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-xl mx-auto px-4">
              {SAMPLE_STARTER_PROMPTS.map((prompt, idx) => (
                <button
                  key={idx}
                  onClick={() => onQuickPrompt(prompt)}
                  className="p-3 rounded-card bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] text-left text-xs text-secondary hover:text-primary transition-all duration-fast font-sans leading-relaxed group shadow-sm"
                >
                  <span className="text-accent mr-1.5 opacity-80 group-hover:opacity-100">→</span>
                  {prompt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex-1 overflow-y-auto px-6 py-4 space-y-4 ${className}`}
      role="log"
      aria-live="polite"
    >
      <div className="max-w-[72ch] mx-auto space-y-4">
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            isStreaming={message.id === streamingMessageId || message.isStreaming}
            onConfirmAction={onConfirmAction}
            onDenyAction={onDenyAction}
          />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
