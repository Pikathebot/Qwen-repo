"use client";

import React, { useState } from "react";
import { ProjectFile } from "@/lib/types";
import { EmptyState } from "../ui/EmptyState";

export interface FilesTabProps {
  files: ProjectFile[];
  onSelectFile?: (file: ProjectFile) => void;
  className?: string;
}

function FileTreeNode({
  file,
  depth = 0,
  onSelectFile,
}: {
  file: ProjectFile;
  depth?: number;
  onSelectFile?: (file: ProjectFile) => void;
}) {
  const [isOpen, setIsOpen] = useState(true);

  if (file.is_dir) {
    return (
      <div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center gap-2 py-1 px-2 rounded-lg text-xs text-secondary hover:text-primary hover:bg-white/[0.04] transition-colors text-left font-mono"
          style={{ paddingLeft: `${depth * 14 + 8}px` }}
        >
          <svg
            className={`w-3.5 h-3.5 text-tertiary transition-transform ${
              isOpen ? "rotate-90 text-accent" : ""
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <svg className="w-3.5 h-3.5 text-accent/80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <span className="font-medium text-primary">{file.name}</span>
        </button>

        {isOpen && file.children && (
          <div className="space-y-0.5">
            {file.children.map((child, idx) => (
              <FileTreeNode
                key={`${child.path}-${idx}`}
                file={child}
                depth={depth + 1}
                onSelectFile={onSelectFile}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  let statusBadge = null;
  if (file.status === "pending_edit") {
    statusBadge = (
      <span className="px-1.5 py-0.2 rounded font-mono text-[9px] bg-warning/20 text-warning font-semibold border border-warning/30">
        Pending Edit
      </span>
    );
  } else if (file.status === "modified") {
    statusBadge = (
      <span className="px-1.5 py-0.2 rounded font-mono text-[9px] bg-accent/20 text-accent font-semibold">
        Modified
      </span>
    );
  }

  return (
    <button
      onClick={() => onSelectFile?.(file)}
      className="w-full flex items-center justify-between py-1 px-2 rounded-lg text-xs hover:bg-white/[0.05] transition-colors text-left font-mono group"
      style={{ paddingLeft: `${depth * 14 + 18}px` }}
    >
      <div className="flex items-center gap-2 min-w-0">
        <svg className="w-3.5 h-3.5 text-tertiary group-hover:text-secondary flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span className="truncate text-secondary group-hover:text-primary">{file.name}</span>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        {statusBadge}
        {file.size_bytes > 0 && (
          <span className="text-[10px] text-tertiary">
            {(file.size_bytes / 1024).toFixed(1)} KB
          </span>
        )}
      </div>
    </button>
  );
}

export function FilesTab({ files, onSelectFile, className = "" }: FilesTabProps) {
  if (!files || files.length === 0) {
    return (
      <EmptyState
        title="No Project Files"
        description="Select an active project in the sidebar to browse its indexed local directory tree and pending file patches."
      />
    );
  }

  return (
    <div className={`space-y-3 flex flex-col h-full ${className}`}>
      <div className="flex items-center justify-between pb-2 border-b border-white/[0.06] text-xs">
        <span className="font-mono text-[11px] text-tertiary uppercase tracking-wider font-semibold">
          Project Hierarchy
        </span>
        <span className="text-[10px] font-mono text-secondary">
          Local Tree
        </span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-0.5 pr-1">
        {files.map((file, idx) => (
          <FileTreeNode
            key={`${file.path}-${idx}`}
            file={file}
            onSelectFile={onSelectFile}
          />
        ))}
      </div>
    </div>
  );
}
