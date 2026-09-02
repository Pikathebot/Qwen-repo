"use client";

import React from "react";

export type SpecularButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "warning"
  | "danger"
  | "success";

export type SpecularButtonSize = "sm" | "md" | "lg" | "icon";

export interface SpecularButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: SpecularButtonVariant;
  size?: SpecularButtonSize;
  icon?: React.ReactNode;
  children?: React.ReactNode;
  loading?: boolean;
  className?: string;
}

/**
 * SpecularButton — Pill button with directional specular highlight sweep
 * Implements DESIGN.MD §2.2 pill controls with specular top edge and lighting sweep.
 */
export function SpecularButton({
  variant = "primary",
  size = "md",
  icon,
  children,
  loading = false,
  disabled,
  className = "",
  ...props
}: SpecularButtonProps) {
  let baseVariantStyle = "";

  switch (variant) {
    case "primary":
      baseVariantStyle =
        "bg-gradient-to-r from-accent to-[#388cf5] text-deep font-semibold shadow-md shadow-accent/25 hover:brightness-110 active:brightness-95 border-t border-white/40";
      break;
    case "secondary":
      baseVariantStyle =
        "glass-pill text-primary hover:bg-white/[0.12] active:bg-white/[0.06] border-t border-white/30";
      break;
    case "ghost":
      baseVariantStyle =
        "text-secondary hover:text-primary hover:bg-white/[0.06] active:bg-white/[0.03]";
      break;
    case "warning":
      baseVariantStyle =
        "bg-gradient-to-r from-warning to-[#e09815] text-deep font-semibold shadow-md shadow-warning/20 hover:brightness-110 active:brightness-95 border-t border-white/40";
      break;
    case "danger":
      baseVariantStyle =
        "bg-gradient-to-r from-danger to-[#e54545] text-white font-semibold shadow-md shadow-danger/20 hover:brightness-110 active:brightness-95 border-t border-white/35";
      break;
    case "success":
      baseVariantStyle =
        "bg-gradient-to-r from-success to-[#2bb56e] text-deep font-semibold shadow-md shadow-success/20 hover:brightness-110 active:brightness-95 border-t border-white/35";
      break;
  }

  let sizeStyle = "px-4 py-2 text-sm gap-2";
  if (size === "sm") {
    sizeStyle = "px-3 py-1 text-xs gap-1.5";
  } else if (size === "lg") {
    sizeStyle = "px-6 py-2.5 text-base gap-2.5";
  } else if (size === "icon") {
    sizeStyle = "p-2 aspect-square flex items-center justify-center";
  }

  return (
    <button
      disabled={disabled || loading}
      className={`specular-sweep inline-flex items-center justify-center rounded-pill font-medium transition-all duration-fast ease-liquid focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:opacity-45 disabled:pointer-events-none disabled:shadow-none ${baseVariantStyle} ${sizeStyle} ${className}`}
      {...props}
    >
      {loading ? (
        <svg
          className="animate-spin -ml-1 mr-2 h-4 w-4 text-current"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      ) : icon ? (
        <span className="flex-shrink-0">{icon}</span>
      ) : null}
      {children}
    </button>
  );
}
