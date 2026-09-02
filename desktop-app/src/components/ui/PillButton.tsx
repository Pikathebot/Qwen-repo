"use client";

import React from "react";

export interface PillButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  icon?: React.ReactNode;
  badge?: string | number;
  children: React.ReactNode;
  size?: "sm" | "md";
  className?: string;
}

/**
 * PillButton — Segmented and toggle control capsule
 */
export function PillButton({
  active = false,
  icon,
  badge,
  children,
  size = "md",
  className = "",
  ...props
}: PillButtonProps) {
  const sizeClass = size === "sm" ? "px-2.5 py-1 text-xs gap-1.5" : "px-3.5 py-1.5 text-sm gap-2";

  const activeClass = active
    ? "bg-white/[0.14] text-primary shadow-sm ring-1 ring-white/20 border-t border-white/35 font-medium"
    : "text-secondary hover:text-primary hover:bg-white/[0.05] border-transparent";

  return (
    <button
      className={`inline-flex items-center justify-center rounded-pill transition-all duration-fast ease-liquid focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/50 ${sizeClass} ${activeClass} ${className}`}
      {...props}
    >
      {icon && <span className="flex-shrink-0 text-current">{icon}</span>}
      <span>{children}</span>
      {badge !== undefined && (
        <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-accent/20 text-accent font-semibold">
          {badge}
        </span>
      )}
    </button>
  );
}
