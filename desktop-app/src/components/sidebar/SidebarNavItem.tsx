"use client";

import React from "react";

export interface SidebarNavItemProps {
  icon: React.ReactNode;
  label: string;
  badge?: string | number;
  isActive?: boolean;
  isCollapsed?: boolean;
  onClick: () => void;
  className?: string;
}

/**
 * SidebarNavItem — Elevated pill navigation button in the left sidebar
 */
export function SidebarNavItem({
  icon,
  label,
  badge,
  isActive = false,
  isCollapsed = false,
  onClick,
  className = "",
}: SidebarNavItemProps) {
  const activeClass = isActive
    ? "bg-white/[0.12] text-primary font-medium border-t border-white/30 shadow-md shadow-black/20"
    : "text-secondary hover:text-primary hover:bg-white/[0.05]";

  return (
    <button
      onClick={onClick}
      className={`specular-sweep group relative w-full flex items-center gap-3 px-3 py-2 rounded-xl text-xs transition-all duration-fast ease-liquid focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/50 ${activeClass} ${className}`}
      title={isCollapsed ? label : undefined}
    >
      <span
        className={`flex-shrink-0 transition-colors ${
          isActive ? "text-accent" : "text-secondary group-hover:text-primary"
        }`}
      >
        {icon}
      </span>

      {!isCollapsed && (
        <>
          <span className="truncate flex-1 text-left">{label}</span>
          {badge !== undefined && (
            <span
              className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono font-medium ${
                isActive
                  ? "bg-accent/20 text-accent"
                  : "bg-white/[0.06] text-tertiary group-hover:text-secondary"
              }`}
            >
              {badge}
            </span>
          )}
        </>
      )}
    </button>
  );
}
