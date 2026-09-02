"use client";

import React from "react";

export type GlassCardVariant = "default" | "active" | "subtle" | "warning" | "danger" | "success";

export interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: GlassCardVariant;
  interactive?: boolean;
  withSpecularSweep?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * GlassCard — M2 Elevated Liquid Glass Card
 * Used for messages, tool cards, project cards, memory items, and permission surfaces.
 */
export function GlassCard({
  variant = "default",
  interactive = false,
  withSpecularSweep = false,
  children,
  className = "",
  ...props
}: GlassCardProps) {
  let variantClass = "glass-m2";

  if (variant === "subtle") {
    variantClass = "glass-m1";
  } else if (variant === "active") {
    variantClass = "glass-m2 ring-1 ring-accent/30 shadow-lg shadow-accent/5";
  } else if (variant === "warning") {
    variantClass = "glass-signal-warning";
  } else if (variant === "danger") {
    variantClass = "glass-signal-danger";
  } else if (variant === "success") {
    variantClass = "glass-signal-success";
  }

  const interactiveClass = interactive
    ? "transition-all duration-fast ease-liquid hover:translate-y-[-1px] hover:shadow-xl cursor-pointer"
    : "";

  return (
    <div
      className={`${variantClass} ${
        withSpecularSweep ? "specular-sweep" : ""
      } ${interactiveClass} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
