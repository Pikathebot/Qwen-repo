"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Session } from "@/lib/types";
import { fetchSessions, deleteSessionApi, unloadModelsApi } from "@/lib/api";

interface SidebarProps {
  activeSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onOpenSettings?: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({
  activeSessionId,
  onSelectSession,
  onNewChat,
  onOpenSettings,
  isCollapsed,
  onToggleCollapse,
}: SidebarProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [freeingVram, setFreeingVram] = useState(false);

  const loadSessions = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSessions();
      setSessions(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions, activeSessionId]);

  const handleFreeVram = async () => {
    try {
      setFreeingVram(true);
      const res = await unloadModelsApi();
      showToast(res.message || "Model unloaded & GPU VRAM released.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to free VRAM";
      showToast(msg);
    } finally {
      setFreeingVram(false);
    }
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await deleteSessionApi(sessionId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      if (sessionId === activeSessionId) {
        onNewChat();
      }
    } catch {
      // ignore
    }
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  if (isCollapsed) {
    return (
      <aside className="w-14 h-full bg-sidebar border-r border-subtle flex flex-col items-center py-4 justify-between select-none">
        <div className="flex flex-col items-center gap-3">
          <button
            onClick={onToggleCollapse}
            className="p-2 rounded-xl text-text-muted hover:text-text-main hover:bg-white/5 transition-colors"
            title="Expand Sidebar"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <button
            onClick={onNewChat}
            className="p-2 rounded-xl bg-cyan-accent/10 text-cyan-accent hover:bg-cyan-accent/20 transition-colors"
            title="New Chat"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>

        <div className="flex flex-col items-center gap-2">
          <button
            onClick={handleFreeVram}
            disabled={freeingVram}
            className="p-2 rounded-xl text-text-muted hover:text-rose-accent hover:bg-rose-accent/10 transition-colors"
            title="Free GPU VRAM"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
          {onOpenSettings && (
            <button
              onClick={onOpenSettings}
              className="p-2 rounded-xl text-text-muted hover:text-text-main hover:bg-white/5 transition-colors"
              title="Settings"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          )}
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-64 h-full bg-sidebar border-r border-subtle flex flex-col justify-between select-none relative z-20">
      {/* Header */}
      <div className="p-3.5 border-b border-subtle flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-cyan-accent/20 border border-cyan-accent/40 flex items-center justify-center font-bold text-cyan-accent text-xs">
            J
          </div>
          <span className="font-semibold text-xs tracking-wider uppercase text-text-main font-mono">
            Jarvis
          </span>
        </div>

        <button
          onClick={onToggleCollapse}
          className="p-1 rounded-lg text-text-muted hover:text-text-main hover:bg-white/5 transition-colors"
          title="Collapse Sidebar"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* New Chat Button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-cyan-accent/10 hover:bg-cyan-accent/20 text-cyan-accent border border-cyan-accent/30 rounded-xl text-xs font-semibold transition-all shadow-sm active:scale-[0.98]"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Chat
        </button>
      </div>

      {/* Session History List */}
      <div className="flex-1 overflow-y-auto px-3 space-y-1 py-1">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted/60 px-2 py-1">
          Recent Sessions
        </div>

        {sessions.length === 0 && !loading && (
          <div className="text-center py-8 text-xs text-text-muted/40 font-mono">
            No past sessions
          </div>
        )}

        {sessions.map((s) => {
          const isSelected = s.session_id === activeSessionId;
          const label = s.session_id === "default" ? "Default Workspace" : s.session_id;

          return (
            <div
              key={s.session_id}
              onClick={() => onSelectSession(s.session_id)}
              className={`group flex items-center justify-between px-2.5 py-2 rounded-xl text-xs cursor-pointer border transition-all ${
                isSelected
                  ? "bg-surface border-cyan-accent/40 text-text-main font-medium shadow-sm"
                  : "border-transparent text-text-muted hover:bg-white/[0.03] hover:text-text-main"
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <svg className="w-3.5 h-3.5 text-text-muted/50 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                <span className="truncate">{label}</span>
              </div>

              {s.session_id !== "default" && (
                <button
                  onClick={(e) => handleDeleteSession(e, s.session_id)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:text-rose-accent hover:bg-rose-accent/10 transition-all"
                  title="Delete Session"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Bottom Actions */}
      <div className="p-3 border-t border-subtle space-y-1.5 bg-void/50">
        <button
          onClick={handleFreeVram}
          disabled={freeingVram}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-void hover:bg-rose-500/10 text-rose-accent/90 hover:text-rose-accent border border-subtle hover:border-rose-500/30 text-xs font-medium transition-colors"
          title="Evict loaded models and release 100% GPU VRAM"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          {freeingVram ? "Freeing VRAM..." : "Free VRAM"}
        </button>

        {onOpenSettings && (
          <button
            onClick={onOpenSettings}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-void hover:bg-white/5 text-text-muted hover:text-text-main border border-subtle text-xs transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Settings
          </button>
        )}
      </div>

      {/* Toast popup */}
      {toastMessage && (
        <div className="absolute bottom-16 left-3 right-3 p-2.5 bg-surface text-text-main text-xs border border-subtle rounded-xl shadow-2xl animate-in fade-in slide-in-from-bottom-2 duration-150 z-50">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-accent" />
            <span>{toastMessage}</span>
          </div>
        </div>
      )}
    </aside>
  );
}
