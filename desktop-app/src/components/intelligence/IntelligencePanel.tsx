"use client";

import React, { useState } from "react";
import {
  Artifact,
  ArtifactVersion,
  ProjectFile,
  SSERetrievalContextEvent,
  ActivityStep,
  ModelTopology,
  GovernorTier,
} from "@/lib/types";
import { GlassPanel } from "../ui/GlassPanel";
import { TabBar, TabItem } from "../ui/TabBar";
import { ArtifactTab } from "./ArtifactTab";
import { FilesTab } from "./FilesTab";
import { ContextTab } from "./ContextTab";
import { ActivityTab } from "./ActivityTab";
import { SystemTab } from "./SystemTab";
import { LocalPrivacyStatus } from "../ui/LocalOnlyBadge";

export type IntelligenceTab = "artifact" | "files" | "context" | "activity" | "system";

export interface IntelligencePanelProps {
  isOpen: boolean;
  onClose: () => void;
  artifacts?: Artifact[];
  selectedArtifact?: Artifact | null;
  artifactVersions?: ArtifactVersion[];
  onSelectArtifact?: (art: Artifact) => void;
  onSelectVersion?: (versionNum: number) => void;
  onRegenerateArtifact?: () => void;
  projectFiles?: ProjectFile[];
  onSelectFile?: (file: ProjectFile) => void;
  retrievalContext?: SSERetrievalContextEvent | null;
  activitySteps?: ActivityStep[];
  localStatus?: LocalPrivacyStatus;
  models?: ModelTopology;
  governorTier?: GovernorTier;
  vramUsedMb?: number;
  onUnloadModels?: () => Promise<void>;
  onTogglePauseGovernor?: () => void;
  className?: string;
}

export function IntelligencePanel({
  isOpen,
  onClose,
  artifacts = [],
  selectedArtifact = null,
  artifactVersions = [],
  onSelectArtifact = () => {},
  onSelectVersion = () => {},
  onRegenerateArtifact,
  projectFiles = [],
  onSelectFile,
  retrievalContext = null,
  activitySteps = [],
  localStatus = "local",
  models,
  governorTier = "IDLE",
  vramUsedMb,
  onUnloadModels,
  onTogglePauseGovernor,
  className = "",
}: IntelligencePanelProps) {
  const [activeTab, setActiveTab] = useState<IntelligenceTab>("files");

  if (!isOpen) return null;

  const tabs: TabItem[] = [
    { id: "artifact", label: "Artifact", badge: artifacts.length > 0 ? artifacts.length : undefined },
    { id: "files", label: "Files", badge: projectFiles.length > 0 ? projectFiles.length : undefined },
    { id: "context", label: "Context", badge: retrievalContext?.chunks_used?.length },
    { id: "activity", label: "Activity", badge: activitySteps.length > 0 ? activitySteps.length : undefined },
    { id: "system", label: "System" },
  ];

  return (
    <aside
      className={`relative h-full w-[360px] flex-shrink-0 transition-all duration-std ease-liquid z-20 ${className}`}
    >
      <GlassPanel
        variant="primary"
        className="h-full w-full p-4 flex flex-col justify-between overflow-hidden shadow-2xl"
      >
        {/* Top Header: Tab Bar & Close Button */}
        <div className="flex items-center justify-between gap-2 pb-3 border-b border-white/[0.06] flex-shrink-0">
          <TabBar
            tabs={tabs}
            activeTab={activeTab}
            onChange={(t) => setActiveTab(t as IntelligenceTab)}
            size="sm"
          />

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-tertiary hover:text-primary hover:bg-white/[0.08] transition-colors flex-shrink-0"
            title="Close panel"
            aria-label="Close intelligence panel"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tab Body Viewports */}
        <div className="flex-1 my-3 overflow-hidden flex flex-col">
          {activeTab === "artifact" && (
            <ArtifactTab
              artifacts={artifacts}
              selectedArtifact={selectedArtifact}
              versions={artifactVersions}
              onSelectArtifact={onSelectArtifact}
              onSelectVersion={onSelectVersion}
              onRegenerate={onRegenerateArtifact}
            />
          )}

          {activeTab === "files" && (
            <FilesTab files={projectFiles} onSelectFile={onSelectFile} />
          )}

          {activeTab === "context" && (
            <ContextTab contextData={retrievalContext} />
          )}

          {activeTab === "activity" && (
            <ActivityTab steps={activitySteps} />
          )}

          {activeTab === "system" && (
            <SystemTab
              localStatus={localStatus}
              models={models}
              governorTier={governorTier}
              vramUsedMb={vramUsedMb}
              onUnloadModels={onUnloadModels}
              onTogglePauseGovernor={onTogglePauseGovernor}
            />
          )}
        </div>
      </GlassPanel>
    </aside>
  );
}
