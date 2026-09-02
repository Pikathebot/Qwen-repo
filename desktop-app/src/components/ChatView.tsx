"use client";

import React, { useEffect, useRef } from "react";
import { Message } from "@/lib/types";
import { MessageBubble } from "./MessageBubble";

interface ChatViewProps {
  messages: Message[];
  streamingMessageId: string | null;
  onConfirmAction?: (actionId: string) => void;
  onDenyAction?: () => void;
  onQuickPrompt?: (prompt: string) => void;
}

export function ChatView({
  messages,
  streamingMessageId,
  onConfirmAction,
  onDenyAction,
  onQuickPrompt,
}: ChatViewProps) {
  const scrollBottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingMessageId]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 select-none">
        <div className="max-w-md w-full text-center space-y-6">
          <div className="w-14 h-14 mx-auto rounded-2xl bg-surface border border-subtle flex items-center justify-center text-cyan-accent font-bold text-xl shadow-lg">
            J
          </div>

          <div className="space-y-2">
            <h1 className="text-xl font-bold text-text-main tracking-tight font-sans">
              Jarvis AI Command Center
            </h1>
            <p className="text-xs text-text-muted leading-relaxed">
              100% offline, local intelligence powered by llama.cpp and Qwen3.5. Execute tools, run commands, and automate workflows securely.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left pt-2">
            {[
              { title: "System Status", prompt: "What is your current system status and active backend?" },
              { title: "List Files", prompt: "List the files in the current workspace directory." },
              { title: "Run Diagnostics", prompt: "Check system health, memory, and governor limits." },
              { title: "Write Code", prompt: "Write a high-performance async Python script with typing." },
            ].map((card) => (
              <button
                key={card.title}
                onClick={() => onQuickPrompt?.(card.prompt)}
                className="p-3 bg-surface/60 hover:bg-surface border border-subtle hover:border-white/20 rounded-xl text-xs text-text-muted hover:text-text-main transition-all text-left shadow-sm active:scale-[0.98]"
              >
                <div className="font-semibold text-text-main text-[11px]">{card.title}</div>
                <div className="text-[10px] text-text-muted/70 truncate mt-0.5">{card.prompt}</div>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-4">
      <div className="max-w-4xl mx-auto space-y-4">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreaming={msg.id === streamingMessageId}
            onConfirmAction={onConfirmAction}
            onDenyAction={onDenyAction}
          />
        ))}
        <div ref={scrollBottomRef} />
      </div>
    </div>
  );
}
