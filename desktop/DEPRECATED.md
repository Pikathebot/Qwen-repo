# Legacy Desktop UI (DEPRECATED)

> [!WARNING]
> This directory (`desktop/ui/`) contains the legacy vanilla HTML/JavaScript frontend.
>
> **Canonical Target Frontend**: `desktop-app/` (Next.js 14 + React + Tailwind CSS + TypeScript).

## Overview
As specified in `Build plan.md` Section 1, the primary user interface is the polished Next.js/React application located in [`desktop-app/`](../desktop-app/).

`desktop/ui` is maintained solely as a fallback interface.

## Launching
- **Default (Canonical Next.js UI)**:
  `python run_jarvis.py`
  (Serves the optimized build from `desktop-app/out/`).

- **Fallback (Legacy Vanilla UI)**:
  `python run_jarvis.py --legacy-ui`
  (Forces serving from `desktop/ui/`).
