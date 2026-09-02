"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useChat } from "@/hooks/useChat";
import { useGovernor } from "@/hooks/useGovernor";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { CanvasHeader } from "@/components/conversation/CanvasHeader";
import { MessageList } from "@/components/conversation/MessageList";
import { Composer } from "@/components/conversation/Composer";
import { IntelligencePanel } from "@/components/intelligence/IntelligencePanel";
import { StatusFooter } from "@/components/footer/StatusFooter";
import { HighRiskModal } from "@/components/modals/HighRiskModal";
import { MemoryInspectorModal } from "@/components/modals/MemoryInspectorModal";
import { SkillsBrowserModal } from "@/components/modals/SkillsBrowserModal";
import { SettingsModal } from "@/components/modals/SettingsModal";
import { SpotlightOverlay } from "@/components/modals/SpotlightOverlay";
import { GlassPanel } from "@/components/ui/GlassPanel";
import {
  Project,
  Session,
  Artifact,
  ProjectFile,
  MemoryItem,
  SkillItem,
  PendingConfirmation,
} from "@/lib/types";
import {
  fetchProjects,
  fetchActiveProject,
  fetchSessions,
  fetchArtifacts,
  fetchArtifactVersions,
  fetchProjectFiles,
  unloadModelsApi,
} from "@/lib/api";
import { MockAdapter } from "@/lib/mock-adapter";

export default function Home() {
  // Navigation & Panel states
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [chatMode, setChatMode] = useState<"WORKSPACE" | "SYSTEM">("WORKSPACE");

  // Modals
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [highRiskConfirmation, setHighRiskConfirmation] = useState<PendingConfirmation | null>(null);

  // Workspace entity states
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [artifactVersions, setArtifactVersions] = useState<import("@/lib/types").ArtifactVersion[]>([]);
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>([]);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [skills, setSkills] = useState<SkillItem[]>([]);

  // System & Chat hooks
  const governor = useGovernor(3000);
  const chat = useChat(() => {
    loadSessionsList(activeProject?.id);
  });

  // Load Projects & initial state
  const loadInitialData = useCallback(async () => {
    try {
      const projData = await fetchProjects();
      setProjects(projData);
      const active = projData.find((p) => p.is_active) || projData[0] || null;
      setActiveProject(active);
      return active;
    } catch {
      // Offline fallback to MockAdapter
      const mockProjects = await MockAdapter.getProjects();
      setProjects(mockProjects);
      const active = mockProjects.find((p) => p.is_active) || mockProjects[0] || null;
      setActiveProject(active);
      return active;
    }
  }, []);

  const loadSessionsList = useCallback(async (projectId?: string) => {
    try {
      const sessData = await fetchSessions(projectId);
      setSessions(sessData);
    } catch {
      const mockSess = await MockAdapter.getSessions(projectId);
      setSessions(mockSess);
    }
  }, []);

  const loadArtifactsList = useCallback(async (sessionId?: string, projectId?: string) => {
    try {
      const artData = await fetchArtifacts(sessionId, projectId);
      setArtifacts(artData);
      if (artData.length > 0) {
        setSelectedArtifact(artData[0]);
      }
    } catch {
      const mockArts = await MockAdapter.getArtifacts(sessionId, projectId);
      setArtifacts(mockArts);
      if (mockArts.length > 0) {
        setSelectedArtifact(mockArts[0]);
      }
    }
  }, []);

  const loadFilesList = useCallback(async (projectId?: string) => {
    try {
      if (projectId) {
        const filesData = await fetchProjectFiles(projectId);
        setProjectFiles(filesData);
      } else {
        const mockFiles = await MockAdapter.getProjectFiles();
        setProjectFiles(mockFiles);
      }
    } catch {
      const mockFiles = await MockAdapter.getProjectFiles(projectId);
      setProjectFiles(mockFiles);
    }
  }, []);

  const loadMemoriesAndSkills = useCallback(async () => {
    const mems = await MockAdapter.getMemories();
    setMemories(mems);
    const sks = await MockAdapter.getSkills();
    setSkills(sks);
  }, []);

  useEffect(() => {
    loadInitialData().then((active) => {
      loadSessionsList(active?.id);
      loadArtifactsList(chat.activeSessionId, active?.id);
      loadFilesList(active?.id);
      loadMemoriesAndSkills();
    });
  }, [loadInitialData, loadSessionsList, loadArtifactsList, loadFilesList, loadMemoriesAndSkills, chat.activeSessionId]);

  // Load artifact versions when selected artifact changes
  useEffect(() => {
    if (selectedArtifact) {
      fetchArtifactVersions(selectedArtifact.id)
        .then(setArtifactVersions)
        .catch(() => setArtifactVersions([]));
    } else {
      setArtifactVersions([]);
    }
  }, [selectedArtifact]);

  // Keyboard shortcut listener for Spotlight (Alt+Space or Cmd+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.altKey && e.code === "Space") || (e.ctrlKey && e.key === "k") || (e.metaKey && e.key === "k")) {
        e.preventDefault();
        setSpotlightOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Filter pending HIGH_RISK confirmations to show modal
  useEffect(() => {
    const highRisk = chat.pendingConfirmations.find(
      (c) => c.risk_tier === "HIGH_RISK"
    );
    if (highRisk) {
      setHighRiskConfirmation(highRisk);
    }
  }, [chat.pendingConfirmations]);

  const handleSelectProject = (proj: Project) => {
    setActiveProject(proj);
    loadSessionsList(proj.id);
    loadFilesList(proj.id);
  };

  const handleAddMemory = async (newMem: Omit<MemoryItem, "id" | "created_at">) => {
    const created = await MockAdapter.addMemory(newMem);
    setMemories((prev) => [created, ...prev]);
  };

  const handleDeleteMemory = async (id: string) => {
    await MockAdapter.deleteMemory(id);
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  const handleToggleSkill = async (id: string) => {
    const updated = await MockAdapter.toggleSkill(id);
    setSkills([...updated]);
  };

  const handleUnloadModels = async () => {
    try {
      await unloadModelsApi();
    } catch {
      // mock unload
    }
    await governor.refresh();
  };

  const activeSessionTitle =
    sessions.find((s) => s.session_id === chat.activeSessionId)?.title ||
    (chat.activeSessionId === "session_gas_refactor_a41f"
      ? "GAS Inventory Component Patch"
      : chat.activeSessionId === "default"
      ? "Default Workspace"
      : `Session ${chat.activeSessionId.substring(0, 10)}...`);

  const localPrivacyStatus = chat.isMockMode || governor.isMock ? "mock" : "local";

  return (
    <div className="flex h-screen w-screen overflow-hidden p-3 gap-3 select-none text-primary font-sans relative">
      {/* 1. Left Navigation Sidebar (260px M1 Liquid Glass) */}
      <Sidebar
        activeSessionId={chat.activeSessionId}
        sessions={sessions}
        projects={projects}
        activeProject={activeProject}
        onSelectSession={chat.selectSession}
        onNewChat={chat.newChat}
        onSelectProject={handleSelectProject}
        onOpenSearch={() => setSpotlightOpen(true)}
        onOpenMemory={() => setMemoryOpen(true)}
        onOpenSkills={() => setSkillsOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        localStatus={localPrivacyStatus}
        activeModelName={chat.selectedModel || "Qwen3-30B"}
      />

      {/* 2. Center Conversation Canvas (Fluid M1/M2 Glass with 72ch Constraint) */}
      <GlassPanel
        variant="primary"
        className="flex-1 flex flex-col h-full relative overflow-hidden shadow-2xl"
      >
        {/* Top Canvas Header */}
        <CanvasHeader
          sessionTitle={activeSessionTitle}
          projectName={activeProject?.name}
          chatMode={chatMode}
          onToggleChatMode={setChatMode}
          selectedModel={chat.selectedModel || "Qwen3-30B"}
          governorTier={governor.tier}
          vramUsedMb={governor.health?.vram_used_mb}
          rightPanelOpen={rightPanelOpen}
          onToggleRightPanel={() => setRightPanelOpen(!rightPanelOpen)}
          artifactsCount={artifacts.length}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        {/* Global Error Banner if any */}
        {chat.error && (
          <div className="bg-danger/10 border-b border-danger/30 px-6 py-2 flex items-center justify-between text-xs text-danger animate-in fade-in duration-fast">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{chat.error}</span>
            </div>
            <button
              onClick={chat.clearError}
              className="text-danger hover:text-white font-bold px-2 py-0.5"
            >
              ✕
            </button>
          </div>
        )}

        {/* Scrollable Message List with 72ch Reading Constraint */}
        <MessageList
          messages={chat.messages}
          streamingMessageId={chat.streamingMessageId}
          onConfirmAction={chat.confirmAction}
          onDenyAction={chat.denyAction}
          onQuickPrompt={(prompt) => chat.sendMessage(prompt, undefined, undefined, activeProject?.id)}
        />

        {/* Floating Composer (28px M2 Capsule) */}
        <Composer
          onSendMessage={(text, attachments) =>
            chat.sendMessage(text, undefined, attachments, activeProject?.id)
          }
          isLoading={chat.isLoading}
          onAbort={chat.abortStream}
          projectName={activeProject?.name}
          activeModelName={chat.selectedModel || "Qwen3-30B"}
          activeSkillsCount={skills.filter((s) => s.isActive).length}
          onOpenModelSelector={() => setSettingsOpen(true)}
          onOpenSkillsBrowser={() => setSkillsOpen(true)}
        />

        {/* Floating Status Bar (Bottom Center) */}
        <div className="absolute bottom-1 left-0 right-0 flex justify-center pointer-events-none pb-2">
          <div className="pointer-events-auto">
            <StatusFooter
              localStatus={localPrivacyStatus}
              chunksCount={activeProject?.chunks_count || 12403}
              contextTokens={{
                used: chat.retrievalContext?.budget_report?.total_input_tokens_used || 14000,
                max: chat.retrievalContext?.budget_report?.total_context_window || 32768,
              }}
              governorTier={governor.tier}
              vramUsageMb={governor.health?.vram_used_mb}
              onOpenSystem={() => setRightPanelOpen(true)}
            />
          </div>
        </div>
      </GlassPanel>

      {/* 3. Right Intelligence Panel (360px M1 Glass) */}
      <IntelligencePanel
        isOpen={rightPanelOpen}
        onClose={() => setRightPanelOpen(false)}
        artifacts={artifacts}
        selectedArtifact={selectedArtifact}
        artifactVersions={artifactVersions}
        onSelectArtifact={setSelectedArtifact}
        onSelectVersion={(v) => {
          const foundVer = artifactVersions.find((ver) => ver.version === v);
          if (foundVer && selectedArtifact) {
            setSelectedArtifact({ ...selectedArtifact, version: v, content: foundVer.content });
          }
        }}
        projectFiles={projectFiles}
        retrievalContext={chat.retrievalContext}
        activitySteps={chat.activitySteps}
        localStatus={localPrivacyStatus}
        governorTier={governor.tier}
        vramUsedMb={governor.health?.vram_used_mb}
        onUnloadModels={handleUnloadModels}
        onTogglePauseGovernor={() => {
          if (governor.tier === "PAUSED") governor.resume();
          else governor.pause("User requested pause from System tab");
        }}
      />

      {/* 4. Modals & Overlays */}
      <HighRiskModal
        isOpen={!!highRiskConfirmation}
        confirmation={highRiskConfirmation}
        onCancel={() => {
          if (highRiskConfirmation) chat.denyAction(highRiskConfirmation.action_id);
          setHighRiskConfirmation(null);
        }}
        onAllowOnce={(actionId) => {
          chat.confirmAction(actionId);
          setHighRiskConfirmation(null);
        }}
        onAllowForRun={(actionId) => {
          chat.confirmAction(actionId);
          setHighRiskConfirmation(null);
        }}
      />

      <MemoryInspectorModal
        isOpen={memoryOpen}
        onClose={() => setMemoryOpen(false)}
        memories={memories}
        onAddMemory={handleAddMemory}
        onDeleteMemory={handleDeleteMemory}
      />

      <SkillsBrowserModal
        isOpen={skillsOpen}
        onClose={() => setSkillsOpen(false)}
        skills={skills}
        onToggleSkill={handleToggleSkill}
      />

      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        governor={governor.health ? {
          status: governor.status,
          tier: governor.tier,
          throttled: governor.throttled,
          activeBackend: governor.activeBackend,
          configuredModel: governor.configuredModel,
          availableModels: governor.availableModels,
          ollamaConnected: governor.ollamaConnected,
        } : undefined}
        selectedModel={chat.selectedModel}
        onSelectModel={(m) => {
          chat.setSelectedModel(m);
        }}
      />

      <SpotlightOverlay
        isOpen={spotlightOpen}
        onClose={() => setSpotlightOpen(false)}
        onExpandToWorkspace={(prompt) => {
          chat.sendMessage(prompt, undefined, undefined, activeProject?.id);
        }}
        projectName={activeProject?.name}
        modelName={chat.selectedModel || "Qwen3-30B"}
      />
    </div>
  );
}
