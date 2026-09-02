"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Prism from "prismjs";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-python";
import "prismjs/components/prism-bash";
import "prismjs/components/prism-json";
import "prismjs/components/prism-markdown";
import "prismjs/components/prism-c";
import "prismjs/components/prism-cpp";
import "prismjs/components/prism-csharp";

import { Message } from "@/lib/types";
import { GlassCard } from "../ui/GlassCard";
import { ContextChip } from "../ui/ContextChip";
import { ModelBadge } from "../ui/ModelBadge";
import { ToolCallCard } from "./ToolCallCard";
import { PermissionCard } from "./PermissionCard";

export interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  onConfirmAction?: (actionId: string) => void;
  onDenyAction?: (actionId: string) => void;
}

function HighlightedCode({ code, language }: { code: string; language: string }) {
  const highlighted = useMemo(() => {
    try {
      const grammar = Prism.languages[language] || Prism.languages.javascript || Prism.languages.plain;
      return Prism.highlight(code, grammar, language);
    } catch {
      return code;
    }
  }, [code, language]);

  return (
    <div className="relative group my-3">
      <div className="flex items-center justify-between px-3 py-1.5 bg-black/60 rounded-t-xl border-t border-l border-r border-white/10 text-[10px] font-mono text-tertiary">
        <span className="uppercase">{language || "code"}</span>
        <button
          type="button"
          onClick={() => navigator.clipboard.writeText(code)}
          className="hover:text-primary transition-colors flex items-center gap-1 opacity-70 hover:opacity-100"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          Copy
        </button>
      </div>
      <pre className="!mt-0 !rounded-t-none text-xs leading-relaxed font-mono">
        <code dangerouslySetInnerHTML={{ __html: highlighted }} />
      </pre>
    </div>
  );
}

/**
 * MessageBubble — Liquid Glass Message Unit
 */
export function MessageBubble({
  message,
  isStreaming = false,
  onConfirmAction,
  onDenyAction,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  if (isSystem) {
    return (
      <div className="flex justify-center my-3">
        <div className="glass-pill px-3 py-1 text-xs text-secondary font-mono flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          <span>{message.content}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-3 my-5 ${isUser ? "justify-end" : "justify-start"}`}>
      {/* Assistant Avatar Icon */}
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-xl glass-m2 flex items-center justify-center text-accent font-mono font-bold text-xs shadow-md border-t border-white/30">
          J
        </div>
      )}

      <div className={`max-w-[88%] space-y-2.5 ${isUser ? "items-end" : "items-start"}`}>
        {/* Assistant Header & Model Badge */}
        {!isUser && (
          <div className="flex items-center gap-2 px-1">
            <ModelBadge
              role="MAIN"
              modelName={message.model || "Qwen3-30B"}
              provider={message.provider}
              size="sm"
            />
          </div>
        )}

        {/* User Context Chips (e.g. Attached Files, Memories) */}
        {isUser && message.contextChips && message.contextChips.length > 0 && (
          <div className="flex flex-wrap gap-1.5 justify-end mb-1">
            {message.contextChips.map((chip, idx) => (
              <ContextChip key={idx} type={chip.type} label={chip.label} />
            ))}
          </div>
        )}

        {/* Tool Execution Steps */}
        {message.toolSteps && message.toolSteps.length > 0 && (
          <div className="w-full space-y-1.5">
            {message.toolSteps.map((step) => (
              <ToolCallCard key={step.id} step={step} />
            ))}
          </div>
        )}

        {/* Main Message Content */}
        {(message.content !== undefined || isStreaming) && (
          <GlassCard
            variant={isUser ? "active" : "default"}
            className={`p-4 text-sm leading-relaxed ${
              isUser
                ? "bg-accent/10 border-accent/30 text-primary rounded-tr-sm shadow-md"
                : "text-primary rounded-tl-sm shadow-md"
            }`}
          >
            {isUser ? (
              <div className="whitespace-pre-wrap font-medium">{message.content}</div>
            ) : (
              <div className="prose prose-invert max-w-none text-sm space-y-2 select-text">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    code({ className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || "");
                      const codeContent = String(children).replace(/\n$/, "");
                      if (match) {
                        return (
                          <HighlightedCode
                            code={codeContent}
                            language={match[1]}
                          />
                        );
                      }
                      return (
                        <code
                          className="px-1.5 py-0.5 rounded bg-black/40 text-accent font-mono text-[12px] border border-white/5"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {message.content || ""}
                </ReactMarkdown>

                {isStreaming && (
                  <span className="inline-block w-2 h-4 ml-1 align-middle bg-accent rounded-sm animate-pulse" />
                )}
              </div>
            )}
          </GlassCard>
        )}

        {/* Pending Safety Confirmations */}
        {message.pendingConfirmations && message.pendingConfirmations.length > 0 && (
          <div className="w-full space-y-2 mt-2">
            {message.pendingConfirmations.map((conf) => (
              <PermissionCard
                key={conf.action_id}
                confirmation={conf}
                onApprove={(id) => onConfirmAction?.(id)}
                onReject={(id) => onDenyAction?.(id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
