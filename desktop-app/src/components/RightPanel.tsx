"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Artifact, ArtifactVersion, ProjectFile } from "@/lib/types";
import { fetchArtifacts, fetchArtifactVersions, fetchProjectFiles } from "@/lib/api";

interface RightPanelProps {
  isOpen: boolean;
  onClose: () => void;
  activeSessionId?: string;
  activeProjectId?: string;
}

type TabType = "artifacts" | "files" | "context" | "activity";

export function RightPanel({
  isOpen,
  onClose,
  activeSessionId,
  activeProjectId,
}: RightPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>("artifacts");
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [versions, setVersions] = useState<ArtifactVersion[]>([]);
  const [selectedVersionNum, setSelectedVersionNum] = useState<number | null>(null);
  const [displayedContent, setDisplayedContent] = useState<string>("");
  const [copied, setCopied] = useState(false);

  // Files Tab State
  const [projectFiles, setProjectFiles] = useState<ProjectFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);

  // Load Artifacts
  const loadArtifacts = useCallback(async () => {
    try {
      const data = await fetchArtifacts(activeSessionId, activeProjectId);
      setArtifacts(data);
      if (data.length > 0) {
        // Select first or maintain current
        const current = data.find((a) => a.id === selectedArtifact?.id) || data[0];
        setSelectedArtifact(current);
        setSelectedVersionNum(current.version);
        setDisplayedContent(current.content);
      } else {
        setSelectedArtifact(null);
        setSelectedVersionNum(null);
        setDisplayedContent("");
      }
    } catch {
      // ignore
    }
  }, [activeSessionId, activeProjectId, selectedArtifact?.id]);

  // Load Versions when selected artifact changes
  useEffect(() => {
    if (selectedArtifact) {
      fetchArtifactVersions(selectedArtifact.id)
        .then((vers) => {
          setVersions(vers);
        })
        .catch(() => setVersions([]));
    } else {
      setVersions([]);
    }
  }, [selectedArtifact]);

  // Load Files for Files tab
  const loadFiles = useCallback(async () => {
    if (!activeProjectId) return;
    try {
      setLoadingFiles(true);
      const files = await fetchProjectFiles(activeProjectId);
      setProjectFiles(files);
    } catch {
      setProjectFiles([]);
    } finally {
      setLoadingFiles(false);
    }
  }, [activeProjectId]);

  useEffect(() => {
    if (isOpen) {
      loadArtifacts();
      if (activeTab === "files") {
        loadFiles();
      }
    }
  }, [isOpen, activeTab, loadArtifacts, loadFiles]);

  const handleSelectVersion = (versionNum: number) => {
    setSelectedVersionNum(versionNum);
    const ver = versions.find((v) => v.version === versionNum);
    if (ver) {
      setDisplayedContent(ver.content);
    } else if (selectedArtifact && selectedArtifact.version === versionNum) {
      setDisplayedContent(selectedArtifact.content);
    }
  };

  const handleCopyContent = () => {
    if (!displayedContent) return;
    navigator.clipboard.writeText(displayedContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!selectedArtifact || !displayedContent) return;
    const blob = new Blob([displayedContent], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = selectedArtifact.name || "artifact.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!isOpen) return null;

  return (
    <aside className="w-96 md:w-[440px] h-full bg-sidebar border-l border-subtle flex flex-col justify-between select-none relative z-20 shadow-2xl animate-in slide-in-from-right duration-200">
      {/* Top Tab Bar (Amendment 4) */}
      <div className="border-b border-subtle bg-void/40">
        <div className="flex items-center justify-between px-3 pt-2">
          <div className="flex items-center gap-1">
            {(
              [
                { id: "artifacts", label: "Artifacts", count: artifacts.length },
                { id: "files", label: "Files", count: projectFiles.length },
                { id: "context", label: "Context" },
                { id: "activity", label: "Activity" },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  if (tab.id === "files") loadFiles();
                }}
                className={`px-3 py-1.5 rounded-t-xl text-xs font-semibold tracking-wide transition-all border-b-2 ${
                  activeTab === tab.id
                    ? "border-cyan-accent text-cyan-accent bg-surface/80"
                    : "border-transparent text-text-muted hover:text-text-main hover:bg-white/5"
                }`}
              >
                <span>{tab.label}</span>
                {"count" in tab && tab.count > 0 && (
                  <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] bg-cyan-accent/20 text-cyan-accent">
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-lg text-text-muted hover:text-text-main hover:bg-white/5 transition-colors mb-1"
            title="Close Panel"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Main Content Viewport */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {/* ==========================================
            TAB 1: ARTIFACTS
        ========================================== */}
        {activeTab === "artifacts" && (
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Artifact Selector Header */}
            {artifacts.length > 0 && (
              <div className="p-3 border-b border-subtle/80 bg-surface/40 space-y-2">
                {/* Horizontal Artifact Tabs */}
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                  {artifacts.map((art) => (
                    <button
                      key={art.id}
                      onClick={() => {
                        setSelectedArtifact(art);
                        setSelectedVersionNum(art.version);
                        setDisplayedContent(art.content);
                      }}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium whitespace-nowrap transition-all border ${
                        selectedArtifact?.id === art.id
                          ? "bg-cyan-accent/15 border-cyan-accent/40 text-cyan-accent"
                          : "bg-void/50 border-subtle text-text-muted hover:text-text-main"
                      }`}
                    >
                      {art.name}
                    </button>
                  ))}
                </div>

                {/* Artifact Details & Actions Toolbar */}
                {selectedArtifact && (
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-mono uppercase bg-void px-2 py-0.5 rounded border border-subtle text-text-muted">
                        {selectedArtifact.type}
                      </span>

                      {/* Version History Selector (Amendment 2) */}
                      {versions.length > 1 && (
                        <select
                          value={selectedVersionNum || selectedArtifact.version}
                          onChange={(e) => handleSelectVersion(Number(e.target.value))}
                          className="bg-void border border-subtle rounded px-2 py-0.5 text-xs text-cyan-accent font-mono focus:outline-none"
                        >
                          {versions.map((v) => (
                            <option key={v.id} value={v.version}>
                              v{v.version} {v.summary ? `— ${v.summary}` : ""}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={handleCopyContent}
                        className="p-1.5 rounded-lg bg-void border border-subtle hover:border-white/20 text-text-muted hover:text-text-main text-xs transition-colors"
                        title="Copy to Clipboard"
                      >
                        {copied ? (
                          <span className="text-emerald-accent text-[11px] font-mono px-1">Copied!</span>
                        ) : (
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                        )}
                      </button>

                      <button
                        onClick={handleDownload}
                        className="p-1.5 rounded-lg bg-void border border-subtle hover:border-white/20 text-text-muted hover:text-text-main text-xs transition-colors"
                        title="Download Artifact"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Artifact Code / Content Viewport */}
            {selectedArtifact ? (
              <div className="flex-1 overflow-auto p-4 font-mono text-xs text-text-main bg-void/70 leading-relaxed">
                <pre className="whitespace-pre-wrap break-words">{displayedContent}</pre>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-text-muted/50 space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-surface border border-subtle flex items-center justify-center text-text-muted/40">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div className="space-y-1">
                  <p className="font-semibold text-xs text-text-main/80 font-sans">No Artifacts Generated</p>
                  <p className="text-[11px] leading-relaxed max-w-xs">
                    When Jarvis generates structured code, HTML widgets, or documents, they will appear here side-by-side.
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ==========================================
            TAB 2: FILES (Section 19 / Amendment 4)
        ========================================== */}
        {activeTab === "files" && (
          <div className="flex-1 flex flex-col overflow-hidden p-3">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-subtle">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                Workspace Files
              </span>
              <button
                onClick={loadFiles}
                className="text-xs text-cyan-accent hover:underline"
              >
                {loadingFiles ? "Refreshing..." : "Refresh"}
              </button>
            </div>

            {projectFiles.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center text-text-muted/50 p-6">
                <p className="text-xs font-semibold text-text-main/80 font-sans">No Files in Workspace</p>
                <p className="text-[11px] mt-1">Upload files via the paperclip button in chat to store them here.</p>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto space-y-1.5">
                {projectFiles.map((file) => (
                  <div
                    key={file.path}
                    className="p-2.5 rounded-xl bg-surface/60 border border-subtle flex items-center justify-between text-xs hover:border-white/20 transition-all"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <svg className="w-4 h-4 text-cyan-accent flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                      <span className="truncate text-text-main font-mono text-[11px]">{file.name}</span>
                    </div>
                    <span className="text-[10px] text-text-muted/60 flex-shrink-0 font-mono">
                      {(file.size_bytes / 1024).toFixed(1)} KB
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ==========================================
            TAB 3: CONTEXT (Option 4 RAG Stub)
        ========================================== */}
        {activeTab === "context" && (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-text-muted/50 space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-surface border border-subtle flex items-center justify-center text-cyan-accent/60">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-xs text-text-main/80 font-sans">Retrieved Context Engine</p>
              <p className="text-[11px] leading-relaxed max-w-xs">
                RAG document chunks, vector search results, and hybrid BM25 matches will appear here in Option 4.
              </p>
            </div>
          </div>
        )}

        {/* ==========================================
            TAB 4: ACTIVITY (Phase 4 Agent Run Stub)
        ========================================== */}
        {activeTab === "activity" && (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-text-muted/50 space-y-3">
            <div className="w-12 h-12 rounded-2xl bg-surface border border-subtle flex items-center justify-center text-emerald-accent/60">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-xs text-text-main/80 font-sans">Agent Activity Trace</p>
              <p className="text-[11px] leading-relaxed max-w-xs">
                Multi-step autonomous execution graphs and tool call verification timelines will appear here.
              </p>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
