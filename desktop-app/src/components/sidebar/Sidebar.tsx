"use client";

import React, { useState } from "react";
import { Project, Session } from "@/lib/types";
import { GlassPanel } from "../ui/GlassPanel";
import { SpecularButton } from "../ui/SpecularButton";
import { SidebarNavItem } from "./SidebarNavItem";
import { LocalOnlyBadge, LocalPrivacyStatus } from "../ui/LocalOnlyBadge";

export interface SidebarProps {
  activeSessionId: string;
  sessions: Session[];
  projects: Project[];
  activeProject: Project | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onSelectProject: (project: Project) => void;
  onDeleteSession?: (sessionId: string) => void;
  onOpenSearch?: () => void;
  onOpenMemory?: () => void;
  onOpenSkills?: () => void;
  onOpenSettings?: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  localStatus?: LocalPrivacyStatus;
  activeModelName?: string;
  className?: string;
}

/**
 * Sidebar — 260px M1 Liquid Glass Navigation Panel
 */
export function Sidebar({
  activeSessionId,
  sessions,
  projects,
  activeProject,
  onSelectSession,
  onNewChat,
  onSelectProject,
  onDeleteSession,
  onOpenSearch,
  onOpenMemory,
  onOpenSkills,
  onOpenSettings,
  isCollapsed,
  onToggleCollapse,
  localStatus = "local",
  activeModelName = "Qwen3-30B",
  className = "",
}: SidebarProps) {
  const [projectsExpanded, setProjectsExpanded] = useState(true);

  return (
    <aside
      className={`relative h-full transition-all duration-std ease-liquid flex flex-col z-20 ${
        isCollapsed ? "w-16" : "w-[260px]"
      } ${className}`}
    >
      <GlassPanel
        variant="primary"
        className="h-full w-full p-3 flex flex-col justify-between overflow-hidden shadow-2xl"
      >
        {/* Top Header & Branding */}
        <div className="space-y-3 flex-shrink-0">
          <div className="flex items-center justify-between px-2 pt-1">
            {!isCollapsed ? (
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-lg bg-accent/20 border-t border-accent/40 flex items-center justify-center text-accent text-xs font-mono font-bold shadow-sm">
                  J
                </div>
                <span className="font-semibold text-xs tracking-wider uppercase text-primary font-mono">
                  JARVIS
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-white/[0.06] text-tertiary">
                  v2.0
                </span>
              </div>
            ) : (
              <div className="w-8 h-8 rounded-lg bg-accent/20 border-t border-accent/40 flex items-center justify-center text-accent text-xs font-mono font-bold mx-auto">
                J
              </div>
            )}

            <button
              onClick={onToggleCollapse}
              className="p-1 rounded-lg text-tertiary hover:text-primary hover:bg-white/[0.08] transition-colors"
              title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
              aria-label="Toggle Sidebar"
            >
              <svg
                className={`w-4 h-4 transition-transform duration-std ${
                  isCollapsed ? "rotate-180" : ""
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
                />
              </svg>
            </button>
          </div>

          {/* New Chat Button */}
          <SpecularButton
            variant="primary"
            size={isCollapsed ? "icon" : "sm"}
            onClick={onNewChat}
            className="w-full"
            icon={
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            }
          >
            {!isCollapsed && "New Chat"}
          </SpecularButton>

          {/* Search Button */}
          {onOpenSearch && (
            <button
              onClick={onOpenSearch}
              className="w-full flex items-center gap-2.5 px-3 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.05] text-tertiary hover:text-secondary text-xs transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              {!isCollapsed && (
                <span className="flex-1 text-left font-mono text-[11px]">Search (Alt+Space)</span>
              )}
            </button>
          )}
        </div>

        {/* Scrollable Navigation Body */}
        <div className="flex-1 my-3 overflow-y-auto space-y-4 pr-1">
          {/* Projects Hierarchy */}
          <div>
            {!isCollapsed ? (
              <div className="flex items-center justify-between px-2 mb-1.5">
                <span className="text-[10px] font-mono uppercase tracking-wider text-tertiary font-semibold">
                  Projects
                </span>
                <button
                  onClick={() => setProjectsExpanded(!projectsExpanded)}
                  className="text-tertiary hover:text-primary transition-colors text-[10px]"
                >
                  {projectsExpanded ? "Hide" : "Show"}
                </button>
              </div>
            ) : null}

            {projectsExpanded && (
              <div className="space-y-1">
                {projects.map((proj) => {
                  const isActive = activeProject?.id === proj.id;
                  return (
                    <button
                      key={proj.id}
                      onClick={() => onSelectProject(proj)}
                      className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-xl text-xs text-left transition-all ${
                        isActive
                          ? "bg-accent/15 text-accent font-medium border-t border-accent/30 shadow-xs"
                          : "text-secondary hover:text-primary hover:bg-white/[0.05]"
                      }`}
                      title={proj.name}
                    >
                      <span className="w-2 h-2 rounded-full bg-current opacity-80 flex-shrink-0" />
                      {!isCollapsed && (
                        <span className="truncate flex-1 font-medium">{proj.name}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Conversations Stream */}
          <div>
            {!isCollapsed && (
              <div className="px-2 mb-1.5">
                <span className="text-[10px] font-mono uppercase tracking-wider text-tertiary font-semibold">
                  Recent Chats
                </span>
              </div>
            )}

            <div className="space-y-0.5">
              {sessions.map((sess) => {
                const isActive = sess.session_id === activeSessionId;
                const title = sess.title || (sess.session_id === "default" ? "Workspace Session" : `Session ${sess.session_id.substring(0, 10)}`);

                return (
                  <div
                    key={sess.session_id}
                    className={`group relative flex items-center rounded-xl transition-all ${
                      isActive
                        ? "bg-white/[0.12] text-primary font-medium border-t border-white/30"
                        : "text-secondary hover:text-primary hover:bg-white/[0.05]"
                    }`}
                  >
                    <button
                      onClick={() => onSelectSession(sess.session_id)}
                      className="flex-1 flex items-center gap-2.5 px-2.5 py-2 text-xs text-left truncate"
                      title={title}
                    >
                      <svg
                        className={`w-3.5 h-3.5 flex-shrink-0 ${
                          isActive ? "text-accent" : "text-tertiary group-hover:text-secondary"
                        }`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                        />
                      </svg>
                      {!isCollapsed && (
                        <span className="truncate flex-1 text-xs">{title}</span>
                      )}
                    </button>

                    {!isCollapsed && onDeleteSession && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteSession(sess.session_id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1.5 mr-1 text-tertiary hover:text-danger rounded-lg transition-opacity"
                        title="Delete chat"
                        aria-label="Delete session"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quick Views: Memory, Skills, Settings */}
          <div className="pt-2 border-t border-white/[0.06] space-y-1">
            {onOpenMemory && (
              <SidebarNavItem
                icon={
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                }
                label="Memory Library"
                isCollapsed={isCollapsed}
                onClick={onOpenMemory}
              />
            )}

            {onOpenSkills && (
              <SidebarNavItem
                icon={
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                  </svg>
                }
                label="Skills"
                isCollapsed={isCollapsed}
                onClick={onOpenSkills}
              />
            )}

            {onOpenSettings && (
              <SidebarNavItem
                icon={
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                }
                label="Settings"
                isCollapsed={isCollapsed}
                onClick={onOpenSettings}
              />
            )}
          </div>
        </div>

        {/* Bottom Local Trust & Model Status Footer */}
        <div className="pt-3 border-t border-white/[0.06] flex flex-col gap-2 flex-shrink-0">
          {!isCollapsed ? (
            <>
              <LocalOnlyBadge status={localStatus} className="w-full justify-center" />
              <div className="flex items-center justify-between px-2 text-[10px] font-mono text-tertiary">
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-reasoning animate-pulse" />
                  <span className="text-secondary truncate">{activeModelName}</span>
                </div>
                <span>Ollama / vLLM</span>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-success" title="Local only" />
              <span className="w-1.5 h-1.5 rounded-full bg-reasoning animate-pulse" title={activeModelName} />
            </div>
          )}
        </div>
      </GlassPanel>
    </aside>
  );
}
