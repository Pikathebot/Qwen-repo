"use client";

import React, { useState } from "react";
import { MemoryItem } from "@/lib/types";
import { GlassPanel } from "../ui/GlassPanel";
import { GlassCard } from "../ui/GlassCard";
import { SpecularButton } from "../ui/SpecularButton";

export interface MemoryInspectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  memories: MemoryItem[];
  onAddMemory?: (memory: Omit<MemoryItem, "id" | "created_at">) => void;
  onDeleteMemory?: (id: string) => void;
}

const CATEGORIES: Array<MemoryItem["category"] | "All"> = [
  "All",
  "Preference",
  "Fact",
  "Workflow",
  "Project",
];

export function MemoryInspectorModal({
  isOpen,
  onClose,
  memories,
  onAddMemory,
  onDeleteMemory,
}: MemoryInspectorModalProps) {
  const [selectedCategory, setSelectedCategory] = useState<MemoryItem["category"] | "All">("All");
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newCategory, setNewCategory] = useState<MemoryItem["category"]>("Preference");

  if (!isOpen) return null;

  const filteredMemories = memories.filter((mem) => {
    const matchesCategory = selectedCategory === "All" || mem.category === selectedCategory;
    const matchesSearch =
      mem.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      mem.content.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newContent.trim()) return;
    onAddMemory?.({
      title: newTitle.trim(),
      content: newContent.trim(),
      category: newCategory,
      source: "Manual Entry",
    });
    setNewTitle("");
    setNewContent("");
    setShowAddForm(false);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xl animate-in fade-in duration-std"
    >
      <div className="w-full max-w-2xl max-h-[85vh] flex flex-col">
        <GlassPanel
          variant="stage"
          radius="stage"
          className="p-6 flex flex-col h-full space-y-4 shadow-2xl border-t border-white/30"
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.08]">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-memory/20 border-t border-memory/40 flex items-center justify-center text-memory flex-shrink-0">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h2 className="text-base font-bold text-primary">Long-Term Memory Library</h2>
                <p className="text-xs text-secondary font-sans">
                  Persistent local preferences, architectural conventions, and project facts.
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

          {/* Search & Category Filter Row */}
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 flex-wrap">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1 rounded-pill text-xs font-mono transition-all ${
                    selectedCategory === cat
                      ? "bg-memory/20 text-memory border border-memory/40 font-semibold"
                      : "bg-white/[0.04] text-secondary hover:text-primary border border-white/5"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search memories..."
                className="px-3 py-1 rounded-pill bg-white/[0.05] border border-white/10 text-xs text-primary placeholder-tertiary focus:outline-none focus:ring-1 focus:ring-memory"
              />
              <SpecularButton
                variant="secondary"
                size="sm"
                onClick={() => setShowAddForm(!showAddForm)}
              >
                {showAddForm ? "Cancel" : "+ Add Memory"}
              </SpecularButton>
            </div>
          </div>

          {/* Add Memory Form */}
          {showAddForm && (
            <form onSubmit={handleCreate} className="p-4 rounded-xl bg-black/40 border border-white/10 space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <input
                  type="text"
                  placeholder="Memory Title (e.g. GAS Replication Pattern)"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="col-span-2 px-3 py-1.5 rounded-lg bg-white/[0.06] border border-white/10 text-xs text-primary focus:outline-none focus:ring-1 focus:ring-memory"
                />
                <select
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value as MemoryItem["category"])}
                  className="px-3 py-1.5 rounded-lg bg-deep border border-white/10 text-xs text-primary focus:outline-none"
                >
                  <option value="Preference">Preference</option>
                  <option value="Fact">Fact</option>
                  <option value="Workflow">Workflow</option>
                  <option value="Project">Project</option>
                </select>
              </div>

              <textarea
                placeholder="Memory Content / Learned Behavior..."
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                rows={3}
                className="w-full px-3 py-1.5 rounded-lg bg-white/[0.06] border border-white/10 text-xs text-primary resize-none focus:outline-none focus:ring-1 focus:ring-memory"
              />

              <div className="flex justify-end gap-2">
                <SpecularButton variant="secondary" size="sm" onClick={() => setShowAddForm(false)}>
                  Cancel
                </SpecularButton>
                <SpecularButton variant="primary" size="sm" type="submit">
                  Save Memory
                </SpecularButton>
              </div>
            </form>
          )}

          {/* Memory Cards Stream */}
          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {filteredMemories.length === 0 ? (
              <div className="p-8 text-center text-xs text-tertiary">
                No memories match your query.
              </div>
            ) : (
              filteredMemories.map((mem) => (
                <GlassCard key={mem.id} variant="default" className="p-3.5 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded font-mono text-[10px] bg-memory/15 text-memory font-semibold border border-memory/25">
                        {mem.category}
                      </span>
                      <h4 className="text-xs font-semibold text-primary">{mem.title}</h4>
                    </div>

                    {onDeleteMemory && (
                      <button
                        onClick={() => onDeleteMemory(mem.id)}
                        className="p-1 text-tertiary hover:text-danger rounded transition-colors"
                        title="Delete memory entry"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    )}
                  </div>

                  <p className="text-xs text-secondary leading-relaxed select-text font-sans">
                    {mem.content}
                  </p>

                  {mem.source && (
                    <div className="text-[10px] font-mono text-tertiary pt-1 border-t border-white/[0.04]">
                      Source: {mem.source}
                    </div>
                  )}
                </GlassCard>
              ))
            )}
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
