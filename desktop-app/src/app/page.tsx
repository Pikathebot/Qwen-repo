"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useChat } from "@/hooks/useChat";
import { useGovernor } from "@/hooks/useGovernor";
import { useVoice } from "@/hooks/useVoice";
import { useAwareness } from "@/hooks/useAwareness";
import { Sidebar } from "@/components/Sidebar";
import { ChatView } from "@/components/ChatView";
import { Composer } from "@/components/Composer";
import { GovernorPill } from "@/components/GovernorPill";
import { SettingsDialog } from "@/components/SettingsDialog";
import { RightPanel } from "@/components/RightPanel";
import { VoiceOrb } from "@/components/VoiceOrb";
import { AwarenessTray } from "@/components/AwarenessTray";
import { fetchActiveProject, fetchArtifacts } from "@/lib/api";
import { Observation } from "@/lib/types";

export default function Home() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [chatMode, setChatMode] = useState<"WORKSPACE" | "SYSTEM">("WORKSPACE");
  const [activeProjectId, setActiveProjectId] = useState<string | undefined>(undefined);
  const [artifactsCount, setArtifactsCount] = useState<number>(0);
  const [sessionsRefreshKey, setSessionsRefreshKey] = useState<number>(0);

  const triggerSessionsRefresh = useCallback(() => {
    setSessionsRefreshKey((k) => k + 1);
  }, []);

  const governor = useGovernor(2000);
  const chat = useChat(triggerSessionsRefresh);

  const syncWorkspaceState = useCallback(async () => {
    try {
      const activeProj = await fetchActiveProject();
      setActiveProjectId(activeProj?.id);
      const arts = await fetchArtifacts(chat.activeSessionId, activeProj?.id);
      setArtifactsCount(arts.length);
    } catch {
      // ignore
    }
  }, [chat.activeSessionId]);

  useEffect(() => {
    syncWorkspaceState();
  }, [syncWorkspaceState, chat.messages.length]);

  // A voice turn is answered out loud once the agent finishes streaming.
  const awaitingVoiceReplyRef = useRef(false);

  const handleVoiceCommand = useCallback(
    (query: string) => {
      awaitingVoiceReplyRef.current = true;
      void chat.sendMessage(query, undefined, undefined, activeProjectId, chatMode);
    },
    [chat, activeProjectId, chatMode]
  );

  const voice = useVoice({
    sessionId: chat.activeSessionId,
    onCommand: handleVoiceCommand,
  });

  useEffect(() => {
    if (chat.isLoading || !awaitingVoiceReplyRef.current) return;

    const lastReply = [...chat.messages]
      .reverse()
      .find((m) => m.role === "assistant" && m.content.trim());
    if (!lastReply) return;

    awaitingVoiceReplyRef.current = false;
    void voice.speak(lastReply.content);
  }, [chat.isLoading, chat.messages, voice]);

  // Ambient observations. Spoken only while hands-free voice is on, so the
  // machine never talks to an empty room.
  const speakObservation = useCallback(
    (spoken: string) => {
      if (voice.isActive) void voice.speak(spoken);
    },
    [voice]
  );

  const awareness = useAwareness({ onSpeak: speakObservation });
  const [briefingCard, setBriefingCard] = useState<Observation | null>(null);

  const requestBriefing = useCallback(async () => {
    const briefing = await awareness.getBriefing();
    if (!briefing) return;

    setBriefingCard({
      id: `briefing_${Date.now()}`,
      seq: -1,
      kind: "briefing",
      severity: "notice",
      title: "Status briefing",
      detail: briefing.text.replace(/\*\*/g, "").replace(/^- /gm, "· "),
      spoken: briefing.spoken,
      data: {},
      timestamp: Date.now() / 1000,
      acknowledged: false,
      resolved: false,
    });

    if (voice.isActive) void voice.speak(briefing.spoken);
  }, [awareness, voice]);

  const trayObservations = briefingCard
    ? [...awareness.observations, briefingCard]
    : awareness.observations;

  const dismissObservation = useCallback(
    (observationId: string) => {
      if (briefingCard && observationId === briefingCard.id) {
        setBriefingCard(null);
        return;
      }
      awareness.dismiss(observationId);
    },
    [awareness, briefingCard]
  );

  const dismissAllObservations = useCallback(() => {
    setBriefingCard(null);
    awareness.dismissAll();
  }, [awareness]);

  const handleQuickPrompt = (prompt: string) => {
    chat.sendMessage(prompt, undefined, undefined, activeProjectId, chatMode);
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
        refreshKey={sessionsRefreshKey}
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
            <button
              onClick={() => void requestBriefing()}
              className="px-2.5 py-1 rounded-lg bg-surface border border-subtle hover:border-white/20 text-text-muted hover:text-text-main transition-colors text-[11px] font-mono"
              title="Spoken status briefing"
            >
              brief
            </button>

            <VoiceOrb
              isActive={voice.isActive}
              isSupported={voice.isSupported}
              state={voice.state}
              level={voice.level}
              transcript={voice.transcript}
              spokenText={voice.spokenText}
              error={voice.error}
              onToggle={() => void voice.toggle()}
              onStopSpeaking={voice.stopSpeaking}
            />

            <GovernorPill
              governor={governor}
              selectedModel={chat.selectedModel}
              onOpenSettings={() => setSettingsOpen(true)}
            />

            {/* Right Panel Toggle Button (Amendment 4) */}
            <button
              onClick={() => setRightPanelOpen(!rightPanelOpen)}
              className={`p-1.5 rounded-xl border transition-all flex items-center gap-1.5 text-xs shadow-sm ${
                rightPanelOpen
                  ? "bg-cyan-accent/15 border-cyan-accent/40 text-cyan-accent"
                  : "bg-surface border-subtle hover:border-white/20 text-text-muted hover:text-text-main"
              }`}
              title="Toggle Artifacts & Workspace Panel"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {artifactsCount > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-cyan-accent/20 text-cyan-accent font-mono">
                  {artifactsCount}
                </span>
              )}
            </button>

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

        <AwarenessTray
          observations={trayObservations}
          onDismiss={dismissObservation}
          onDismissAll={dismissAllObservations}
        />

        {/* Bottom Composer */}
        <Composer
          onSendMessage={(text, attachments) =>
            chat.sendMessage(text, undefined, attachments, activeProjectId, chatMode)
          }
          isLoading={chat.isLoading}

          onAbort={chat.abortStream}
          disabled={governor.status === "offline"}
          activeSessionId={chat.activeSessionId}
          activeProjectId={activeProjectId}
        />
      </main>

      {/* 3. Right Panel (Artifacts | Files | Context | Activity) */}
      <RightPanel
        isOpen={rightPanelOpen}
        onClose={() => setRightPanelOpen(false)}
        activeSessionId={chat.activeSessionId}
        activeProjectId={activeProjectId}
        retrievalContext={chat.retrievalContext}
        activitySteps={chat.activitySteps}
      />



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
