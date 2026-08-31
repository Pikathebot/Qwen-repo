"use client";

import React, { useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Prism from "prismjs";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-python";
import "prismjs/components/prism-bash";
import "prismjs/components/prism-json";
import "prismjs/components/prism-markdown";
import { Message, PendingConfirmation } from "@/lib/types";
import { ToolStepCard } from "./ToolStepCard";

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  onConfirmAction?: (actionId: string) => void;
  onDenyAction?: () => void;
}

export function MessageBubble({
  message,
  isStreaming,
  onConfirmAction,
  onDenyAction,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  if (isSystem) {
    return (
      <div className="flex justify-center my-3">
        <div className="px-3 py-1.5 rounded-full bg-void/80 border border-subtle text-xs text-text-muted font-mono flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-accent" />
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-3 my-4 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-xl bg-surface border border-subtle flex items-center justify-center text-cyan-accent font-semibold text-xs shadow-sm">
          J
        </div>
      )}

      <div className={`max-w-[85%] space-y-2 ${isUser ? "items-end" : "items-start"}`}>
        {/* Tool Steps */}
        {message.toolSteps && message.toolSteps.length > 0 && (
          <div className="w-full space-y-1.5">
            {message.toolSteps.map((step) => (
              <ToolStepCard key={step.id} step={step} />
            ))}
          </div>
        )}

        {/* Message Content Bubble */}
        {(message.content !== undefined || isStreaming) && (
          <div
            className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
              isUser
                ? "bg-cyan-accent text-void font-medium rounded-tr-sm shadow-md"
                : "bg-surface border border-subtle text-text-main rounded-tl-sm shadow-sm"
            }`}
          >
            {isUser ? (
              <div className="whitespace-pre-wrap">{message.content}</div>
            ) : (
              <div className="prose prose-invert max-w-none text-sm space-y-2">
                <SafeMarkdown content={message.content || ""} isStreaming={isStreaming} />

                {isStreaming && (
                  <span className="inline-block w-1.5 h-4 ml-1 align-middle bg-cyan-accent animate-pulse" />
                )}
              </div>
            )}
          </div>
        )}

        {/* Pending Confirmations Banner */}
        {message.pendingConfirmations && message.pendingConfirmations.length > 0 && (
          <div className="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-xl space-y-2.5 text-xs text-amber-200">
            <div className="flex items-center gap-1.5 font-semibold text-amber-300">
              <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              Safety Confirmation Required
            </div>

            {message.pendingConfirmations.map((conf) => (
              <div key={conf.action_id} className="p-2.5 bg-void/60 rounded-lg border border-amber-500/20 space-y-1.5">
                <div className="flex justify-between">
                  <span className="font-mono text-cyan-accent font-semibold">{conf.tool}</span>
                  <span className="text-[10px] px-1.5 py-0.2 bg-amber-500/20 text-amber-300 rounded font-mono">
                    {conf.risk_tier || "CONFIRMATION_REQUIRED"}
                  </span>
                </div>
                <div className="text-text-muted text-[11px]">{conf.reason}</div>
                <pre className="p-1.5 bg-void text-text-main font-mono text-[10px] rounded overflow-x-auto max-h-24">
                  {typeof conf.args === "string" ? conf.args : JSON.stringify(conf.args, null, 2)}
                </pre>
                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => onConfirmAction?.(conf.action_id)}
                    className="flex-1 py-1 px-3 bg-emerald-accent/20 hover:bg-emerald-accent/30 text-emerald-accent border border-emerald-accent/40 rounded-lg font-medium transition-colors"
                  >
                    Approve Execution
                  </button>
                  <button
                    onClick={() => onDenyAction?.()}
                    className="py-1 px-3 bg-void hover:bg-white/5 text-text-muted hover:text-text-main border border-subtle rounded-lg transition-colors"
                  >
                    Deny
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Metadata Footer */}
        {!isUser && message.model && (
          <div className="flex items-center gap-2 text-[10px] font-mono text-text-muted/60 pl-1">
            <span>{message.provider}</span>
            <span>·</span>
            <span>{message.model}</span>
          </div>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-xl bg-cyan-accent/20 border border-cyan-accent/40 flex items-center justify-center text-cyan-accent font-semibold text-xs shadow-sm">
          U
        </div>
      )}
    </div>
  );
}

function SafeMarkdown({ content, isStreaming }: { content: string; isStreaming?: boolean }) {
  const { thinking, responseText } = useMemo(() => {
    if (!content.includes("<think>")) {
      return { thinking: null, responseText: content };
    }

    if (content.includes("</think>")) {
      const parts = content.split("</think>");
      const thinkRaw = parts[0].replace("<think>", "").trim();
      const rest = parts.slice(1).join("</think>").trim();
      return { thinking: thinkRaw, responseText: rest };
    }

    const thinkRaw = content.replace("<think>", "").trim();
    return { thinking: thinkRaw, responseText: "" };
  }, [content]);

  try {
    return (
      <div className="space-y-3">
        {thinking && (
          <details
            className="group border border-subtle/60 rounded-xl bg-void/40 overflow-hidden text-xs transition-all"
            open={isStreaming && !responseText}
          >
            <summary className="px-3 py-2 cursor-pointer select-none flex items-center justify-between text-text-muted hover:text-text-main font-medium list-none">
              <span className="flex items-center gap-2">
                <span className={`w-1.5 h-1.5 rounded-full ${isStreaming && !responseText ? "bg-cyan-accent animate-ping" : "bg-cyan-accent/60"}`} />
                <span>{isStreaming && !responseText ? "Thinking..." : "Thought Process"}</span>
              </span>
              <svg className="w-3.5 h-3.5 transform group-open:rotate-180 transition-transform text-text-muted/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </summary>
            <div className="px-3 py-2.5 border-t border-subtle/40 text-text-muted font-mono text-[11px] leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto bg-void/60">
              {thinking}
            </div>
          </details>
        )}

        {responseText ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "");
                const language = match ? match[1] : "";
                const codeContent = String(children).replace(/\n$/, "");

                if (!className && !language) {
                  return (
                    <code className="px-1.5 py-0.5 rounded bg-void text-cyan-accent font-mono text-[13px] border border-subtle" {...props}>
                      {children}
                    </code>
                  );
                }

                return <CodeBlock language={language} code={codeContent} />;
              },
              p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
              ul: ({ children }) => <ul className="list-disc pl-5 my-2 space-y-1">{children}</ul>,
              ol: ({ children }) => <ol className="list-decimal pl-5 my-2 space-y-1">{children}</ol>,
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer" className="text-cyan-accent hover:underline">
                  {children}
                </a>
              ),
            }}
          >
            {responseText}
          </ReactMarkdown>
        ) : isStreaming && !thinking ? (
          <div className="text-xs text-text-muted font-mono">Generating response...</div>
        ) : null}
      </div>
    );
  } catch {
    return <div className="whitespace-pre-wrap font-mono text-xs">{content}</div>;
  }
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const langKey = (language || "text").toLowerCase();
  const grammar = Prism.languages[langKey] || Prism.languages.javascript;

  const highlighted = useMemo(() => {
    try {
      if (grammar) {
        return Prism.highlight(code, grammar, langKey);
      }
    } catch {
      // fallback
    }
    return null;
  }, [code, grammar, langKey]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <div className="relative group my-2 rounded-xl overflow-hidden border border-subtle">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-void border-b border-subtle text-[11px] font-mono text-text-muted">
        <span>{language || "code"}</span>
        <button
          onClick={handleCopy}
          className="hover:text-text-main transition-colors flex items-center gap-1 text-[10px]"
        >
          {copied ? (
            <>
              <svg className="w-3 h-3 text-emerald-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Copied
            </>
          ) : (
            <>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Copy
            </>
          )}
        </button>
      </div>
      <pre className={`language-${language} m-0 rounded-none bg-void text-xs font-mono p-3`}>
        {highlighted ? (
          <code dangerouslySetInnerHTML={{ __html: highlighted }} />
        ) : (
          <code>{code}</code>
        )}
      </pre>
    </div>
  );
}
