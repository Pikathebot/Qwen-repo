"use client";

import React from "react";

export interface TabItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  badge?: string | number;
}

export interface TabBarProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  size?: "sm" | "md";
  className?: string;
}

/**
 * TabBar — Pill-style segmented switcher control
 */
export function TabBar({
  tabs,
  activeTab,
  onChange,
  size = "md",
  className = "",
}: TabBarProps) {
  return (
    <div
      role="tablist"
      className={`inline-flex items-center p-1 rounded-pill bg-white/[0.04] border border-white/[0.06] backdrop-blur-md ${className}`}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        const paddingClass =
          size === "sm" ? "px-2.5 py-1 text-xs gap-1.5" : "px-3.5 py-1.5 text-xs font-medium gap-2";

        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={`relative flex items-center rounded-pill transition-all duration-fast ease-liquid ${paddingClass} ${
              isActive
                ? "bg-white/[0.12] text-primary shadow-sm ring-1 ring-white/20 border-t border-white/35 font-semibold"
                : "text-secondary hover:text-primary hover:bg-white/[0.05]"
            }`}
          >
            {tab.icon && <span className="flex-shrink-0">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span
                className={`ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                  isActive
                    ? "bg-accent/25 text-accent font-bold"
                    : "bg-white/10 text-tertiary"
                }`}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
