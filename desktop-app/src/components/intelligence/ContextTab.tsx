"use client";

import React, { useState } from "react";
import { SSERetrievalContextEvent } from "@/lib/types";
import { EmptyState } from "../ui/EmptyState";

export interface ContextTabProps {
  contextData?: SSERetrievalContextEvent | null;
  className?: string;
}

export function ContextTab({ contextData, className = "" }: ContextTabProps) {
  const [expandedChunkId, setExpandedChunkId] = useState<string | null>(null);

  if (!contextData || (!contextData.chunks_used?.length && !contextData.budget_report)) {
    return (
      <EmptyState
        title="No Active Retrieval Context"
        description="When you query JARVIS in WORKSPACE mode, semantic embeddings and reranked code chunks will be displayed here."
      />
    );
  }

  const budget = contextData.budget_report;

  return (
    <div className={`space-y-4 flex flex-col h-full ${className}`}>
      {/* Token Budget Gauge */}
      {budget && (
        <div className="p-3.5 rounded-card bg-black/30 border border-white/[0.08] space-y-2.5">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="font-semibold text-secondary uppercase tracking-wider">
              Token Budget
            </span>
            <span className="text-primary font-bold">
              {budget.total_input_tokens_used.toLocaleString()} /{" "}
              {budget.total_context_window.toLocaleString()}
            </span>
          </div>

          {/* Multi-segment Token Progress Bar */}
          <div className="h-2 w-full rounded-full bg-white/[0.08] overflow-hidden flex">
            <div
              title={`System Prompt: ${budget.tier1_system_tokens} tokens`}
              className="h-full bg-secondary/60"
              style={{
                width: `${(budget.tier1_system_tokens / budget.total_context_window) * 100}%`,
              }}
            />
            <div
              title={`RAG Chunks: ${budget.tier3_rag_tokens} tokens`}
              className="h-full bg-accent"
              style={{
                width: `${(budget.tier3_rag_tokens / budget.total_context_window) * 100}%`,
              }}
            />
            <div
              title={`Conversation History: ${budget.tier4_history_tokens} tokens`}
              className="h-full bg-reasoning"
              style={{
                width: `${(budget.tier4_history_tokens / budget.total_context_window) * 100}%`,
              }}
            />
            <div
              title={`User Input: ${budget.tier2_user_tokens} tokens`}
              className="h-full bg-success"
              style={{
                width: `${(budget.tier2_user_tokens / budget.total_context_window) * 100}%`,
              }}
            />
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-tertiary pt-1">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-accent" />
              <span>RAG: {budget.tier3_rag_tokens} tok</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-reasoning" />
              <span>History: {budget.tier4_history_tokens} tok</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-secondary" />
              <span>System: {budget.tier1_system_tokens} tok</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />
              <span>Free: {budget.remaining_unallocated_tokens} tok</span>
            </div>
          </div>
        </div>
      )}

      {/* Retrieved Chunks List */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        <div className="flex items-center justify-between text-xs px-1">
          <span className="font-mono text-[11px] text-tertiary uppercase tracking-wider font-semibold">
            Used RAG Chunks ({contextData.chunks_used?.length || 0})
          </span>
          <span className="text-[10px] font-mono text-secondary">Reranked</span>
        </div>

        {contextData.chunks_used?.map((chunk, idx) => {
          const chunkId = chunk.chunk_id || `chunk-${idx}`;
          const isExpanded = expandedChunkId === chunkId;

          return (
            <div
              key={chunkId}
              className="rounded-xl border border-white/[0.08] bg-black/25 overflow-hidden text-xs transition-all"
            >
              <button
                type="button"
                onClick={() => setExpandedChunkId(isExpanded ? null : chunkId)}
                className="w-full flex items-center justify-between p-2.5 hover:bg-white/[0.04] transition-colors text-left"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-primary font-semibold truncate">
                      {chunk.file_name || chunk.file_path}
                    </span>
                    {chunk.symbol_name && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-accent/15 text-accent">
                        {chunk.symbol_name}
                      </span>
                    )}
                  </div>
                  {chunk.start_line !== undefined && (
                    <span className="text-[10px] font-mono text-tertiary">
                      Lines {chunk.start_line}-{chunk.end_line}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  {chunk.similarity_score !== undefined && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-success/15 text-success font-semibold">
                      {(chunk.similarity_score * 100).toFixed(0)}% match
                    </span>
                  )}
                  <svg
                    className={`w-3.5 h-3.5 text-tertiary transition-transform ${
                      isExpanded ? "rotate-180" : ""
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>

              {isExpanded && chunk.content && (
                <div className="p-2.5 border-t border-white/[0.06] bg-black/40">
                  <pre className="text-[11px] font-mono text-secondary whitespace-pre-wrap overflow-x-auto max-h-48 leading-relaxed">
                    {chunk.content}
                  </pre>
                </div>
              )}
            </div>
          );
        })}

        {/* Dropped Chunks if any */}
        {contextData.chunks_dropped && contextData.chunks_dropped.length > 0 && (
          <div className="pt-2 border-t border-white/[0.06] space-y-1.5">
            <span className="font-mono text-[10px] text-tertiary uppercase tracking-wider">
              Dropped Chunks ({contextData.chunks_dropped.length})
            </span>
            {contextData.chunks_dropped.map((dropped, idx) => (
              <div
                key={idx}
                className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04] text-[11px] font-mono text-tertiary flex items-center justify-between"
              >
                <span className="truncate">{dropped.file_name || dropped.file_path}</span>
                <span className="text-[9px] opacity-60">below threshold</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
