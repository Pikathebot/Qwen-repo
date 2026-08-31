"use client";

import React, { useState } from "react";
import { useChat } from "@/hooks/useChat";
import { useGovernor } from "@/hooks/useGovernor";
import { Sidebar } from "@/components/Sidebar";
import { ChatView } from "@/components/ChatView";
import { Composer } from "@/components/Composer";
import { GovernorPill } from "@/components/GovernorPill";
import { SettingsDialog } from "@/components/SettingsDialog";

export default function Home() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [chatMode, setChatMode] = useState<"WORKSPACE" | "SYSTEM">("WORKSPACE");

  const governor = useGovernor(2000);
  const chat = useChat();

  const handleQuickPrompt = (prompt: string) => {
    chat.sendMessage(prompt);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-void text-text-main font-sans">
      {/* 1. Left Navigation Sidebar */}
      <Sidebar
        activeSessionId={chat.activeSessionId}
        onSelectSession={chat.selectSession}
        onNewChat={chat.newChat}
        onOpenSettings={() => setSettingsOpen(true)}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* 2. Main Content Area */}
      <main className="flex-1 flex flex-col h-full bg-main relative overflow-hidden">
        {/* Top App Header */}
        <header className="h-14 border-b border-subtle bg-main/90 backdrop-blur-md px-6 flex items-center justify-between select-none z-10">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-text-main">
                {chat.activeSessionId === "default"
                  ? "Default Workspace"
                  : `Session ${chat.activeSessionId.substring(0, 12)}...`}
              </span>
            </div>

            {/* Chat Mode Switcher */}
            <div className="hidden sm:flex items-center bg-void rounded-lg p-0.5 border border-subtle text-[11px] font-mono">
              <button
                onClick={() => setChatMode("WORKSPACE")}
                className={`px-2 py-0.5 rounded-md transition-all ${
                  chatMode === "WORKSPACE"
                    ? "bg-surface text-cyan-accent font-semibold shadow-xs"
                    : "text-text-muted hover:text-text-main"
                }`}
              >
                WORKSPACE
              </button>
              <button
                onClick={() => setChatMode("SYSTEM")}
                className={`px-2 py-0.5 rounded-md transition-all ${
                  chatMode === "SYSTEM"
                    ? "bg-surface text-cyan-accent font-semibold shadow-xs"
                    : "text-text-muted hover:text-text-main"
                }`}
              >
                SYSTEM
              </button>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <GovernorPill
              governor={governor}
              selectedModel={chat.selectedModel}
              onOpenSettings={() => setSettingsOpen(true)}
            />

            <button
              onClick={() => setSettingsOpen(true)}
              className="p-1.5 rounded-xl bg-surface border border-subtle hover:border-white/20 text-text-muted hover:text-text-main transition-colors shadow-sm"
              title="Settings"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          </div>
        </header>

        {/* Global Error Banner if chat has error */}
        {chat.error && (
          <div className="bg-rose-500/10 border-b border-rose-500/30 px-6 py-2 flex items-center justify-between text-xs text-rose-300 animate-in fade-in duration-150">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-rose-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{chat.error}</span>
            </div>
            <button
              onClick={chat.clearError}
              className="text-rose-400 hover:text-rose-200 font-bold px-2 py-0.5"
            >
              ✕
            </button>
          </div>
        )}

        {/* Conversation Body Viewport */}
        <ChatView
          messages={chat.messages}
          streamingMessageId={chat.streamingMessageId}
          onConfirmAction={chat.confirmAction}
          onDenyAction={chat.denyAction}
          onQuickPrompt={handleQuickPrompt}
        />

        {/* Bottom Composer */}
        <Composer
          onSendMessage={(text) => chat.sendMessage(text)}
          isLoading={chat.isLoading}
          onAbort={chat.abortStream}
          disabled={governor.status === "offline"}
        />
      </main>

      {/* Settings Modal */}
      <SettingsDialog
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        governor={governor}
        selectedModel={chat.selectedModel}
        onSelectModel={(m) => {
          chat.setSelectedModel(m);
          setSettingsOpen(false);
        }}
      />
    </div>
  );
}
