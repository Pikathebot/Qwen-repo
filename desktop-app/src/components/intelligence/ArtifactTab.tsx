"use client";

import React, { useState, useMemo } from "react";
import { Artifact, ArtifactVersion } from "@/lib/types";
import { SpecularButton } from "../ui/SpecularButton";
import { EmptyState } from "../ui/EmptyState";
import Prism from "prismjs";

export interface ArtifactTabProps {
  artifacts: Artifact[];
  selectedArtifact: Artifact | null;
  versions: ArtifactVersion[];
  onSelectArtifact: (art: Artifact) => void;
  onSelectVersion: (versionNum: number) => void;
  onRegenerate?: () => void;
  className?: string;
}

export function ArtifactTab({
  artifacts,
  selectedArtifact,
  versions,
  onSelectArtifact,
  onSelectVersion,
  onRegenerate,
  className = "",
}: ArtifactTabProps) {
  const [viewMode, setViewMode] = useState<"code" | "preview" | "split">("code");
  const [copied, setCopied] = useState(false);

  const highlightedCode = useMemo(() => {
    if (!selectedArtifact?.content) return "";
    try {
      const lang = selectedArtifact.type === "cpp" ? Prism.languages.cpp : Prism.languages.javascript;
      return Prism.highlight(selectedArtifact.content, lang || Prism.languages.plain, selectedArtifact.type || "text");
    } catch {
      return selectedArtifact.content;
    }
  }, [selectedArtifact]);

  const handleCopy = () => {
    if (selectedArtifact?.content) {
      navigator.clipboard.writeText(selectedArtifact.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    if (!selectedArtifact) return;
    const blob = new Blob([selectedArtifact.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = selectedArtifact.name;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!artifacts || artifacts.length === 0) {
    return (
      <EmptyState
        title="No Artifacts Generated"
        description="When JARVIS generates files, components, or documents, they will appear here with live preview and version history."
      />
    );
  }

  return (
    <div className={`space-y-4 flex flex-col h-full ${className}`}>
      {/* Artifact Selector Header */}
      <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
        <div className="flex items-center gap-2 min-w-0">
          <select
            value={selectedArtifact?.id}
            onChange={(e) => {
              const found = artifacts.find((a) => a.id === e.target.value);
              if (found) onSelectArtifact(found);
            }}
            aria-label="Select generated artifact"
            className="bg-white/[0.06] border border-white/10 rounded-xl px-2.5 py-1 text-xs text-primary font-mono focus:outline-none focus:ring-1 focus:ring-accent truncate max-w-[200px]"
          >
            {artifacts.map((a) => (
              <option key={a.id} value={a.id} className="bg-deep text-primary">
                {a.name} (v{a.version})
              </option>
            ))}
          </select>
        </div>

        {/* View Mode Switcher */}
        <div className="flex items-center bg-white/[0.04] rounded-pill p-0.5 border border-white/10 text-[10px]">
          <button
            onClick={() => setViewMode("code")}
            className={`px-2 py-0.5 rounded-pill transition-all ${
              viewMode === "code" ? "bg-white/[0.16] text-primary font-bold" : "text-tertiary hover:text-secondary"
            }`}
          >
            Code
          </button>
          <button
            onClick={() => setViewMode("preview")}
            className={`px-2 py-0.5 rounded-pill transition-all ${
              viewMode === "preview" ? "bg-white/[0.16] text-primary font-bold" : "text-tertiary hover:text-secondary"
            }`}
          >
            Preview
          </button>
        </div>
      </div>

      {/* Main View Area */}
      <div className="flex-1 overflow-hidden rounded-xl border border-white/10 bg-black/40 relative flex flex-col">
        {viewMode === "code" ? (
          <pre className="flex-1 p-3 text-xs font-mono overflow-auto leading-relaxed !bg-transparent !border-0 select-text">
            <code dangerouslySetInnerHTML={{ __html: highlightedCode }} />
          </pre>
        ) : (
          <div className="flex-1 p-4 overflow-auto text-xs text-secondary leading-relaxed bg-white/[0.02]">
            <div className="p-3 rounded-lg bg-black/30 border border-white/5 font-mono text-[11px] mb-3">
              <span className="text-accent font-semibold">Artifact Type:</span> {selectedArtifact?.type} · Version {selectedArtifact?.version}
            </div>
            <div className="whitespace-pre-wrap font-sans text-primary">
              {selectedArtifact?.content}
            </div>
          </div>
        )}
      </div>

      {/* Version History List */}
      {versions && versions.length > 0 && (
        <div className="space-y-1.5 pt-2 border-t border-white/[0.06]">
          <span className="text-[10px] font-mono uppercase tracking-wider text-tertiary font-semibold">
            Version Timeline
          </span>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {versions.map((ver) => (
              <button
                key={ver.id}
                onClick={() => onSelectVersion(ver.version)}
                className={`px-2.5 py-1 rounded-pill text-[10px] font-mono border transition-all ${
                  ver.version === selectedArtifact?.version
                    ? "bg-accent/20 border-accent/40 text-accent font-bold"
                    : "bg-white/[0.04] border-white/10 text-secondary hover:text-primary"
                }`}
              >
                v{ver.version}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-white/[0.06] text-xs">
        <div className="flex items-center gap-2">
          <SpecularButton variant="secondary" size="sm" onClick={handleCopy}>
            {copied ? "Copied!" : "Copy Code"}
          </SpecularButton>
          <SpecularButton variant="secondary" size="sm" onClick={handleDownload}>
            Download
          </SpecularButton>
        </div>

        {onRegenerate && (
          <SpecularButton variant="ghost" size="sm" onClick={onRegenerate}>
            Regenerate
          </SpecularButton>
        )}
      </div>
    </div>
  );
}
