"use client";

import React from "react";

export interface GlassPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "primary" | "elevated" | "stage";
  radius?: "panel" | "card" | "stage" | "pill" | "none";
  withSpecularSweep?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * GlassPanel — Foundational M1/M2/M3 Liquid Glass Container
 * Features: Near-translucent fill (2-8%), specular directional top border,
 * background blur with saturation boost, and soft outer depth.
 */
export function GlassPanel({
  variant = "primary",
  radius = "panel",
  withSpecularSweep = false,
  children,
  className = "",
  ...props
}: GlassPanelProps) {
  const variantClass =
    variant === "stage"
      ? "glass-m3"
      : variant === "elevated"
      ? "glass-m2"
      : "glass-m1";

  const radiusClass =
    radius === "stage"
      ? "rounded-stage"
      : radius === "card"
      ? "rounded-card"
      : radius === "pill"
      ? "rounded-pill"
      : radius === "none"
      ? "rounded-none"
      : "rounded-panel";

  return (
    <div
      className={`relative ${variantClass} ${radiusClass} ${
        withSpecularSweep ? "specular-sweep" : ""
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
