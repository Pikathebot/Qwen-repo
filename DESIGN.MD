# DESIGN.md — Liquid Workspace (JARVIS)

**Version:** 2.0
**Role:** Single source of truth for frontend design generation.
**Execution path:** Antigravity → Stitch MCP (`upload_design_md` → `create_design_system_from_design_md` → `generate_screen_from_text` per screen in §14).
**Target:** Next.js + Tailwind + Tauri desktop app (primary) · Alt+Space Spotlight overlay (secondary).
**Device:** DESKTOP for all screens (min width 1440px) except Spotlight Overlay (floating 680px panel over a dimmed desktop).

> ⚠️ **Original visual language.** Do NOT reproduce Anthropic/Claude branding or Apple proprietary assets/icons. Liquid glass here is an original interpretation of the iOS 26 material language: functional translucency, vibrancy, specular light, depth.

---

## 1. Product Overview

Liquid Workspace is a **professional local AI intelligence workspace** merging two systems:

1. **Claude-like local workspace:** persistent chats, projects, knowledge/RAG, memory, skills, artifacts, agent tool loops, structured SSE streaming.
2. **JARVIS desktop assistant:** local-first runtime, model/provider abstraction (main / fast / embedding / reranker / vision models), permission tiers, terminal sandbox, resource governor, OS-level quick access via Spotlight overlay.

**Core promise:** the UI makes orchestration visible — what the agent knows, what it retrieved, what tools it ran, what files it wants to change, and what it needs permission for — without overwhelming the conversation.

**Feel:** calm · precise · high-trust · technically capable · premium.
**Anti-feel:** admin dashboard, chatbot toy, neon cyberpunk, cluttered IDE.

---

## 2. AESTHETIC MANDATE — Authentic iOS 26 Liquid Glass

> 🔴 **CRITICAL.** Previous generations produced generic glassmorphism (opaque gray panels + uniform borders). That is REJECTED. Every surface in this product must feel like **iOS 26 liquid glass**: near-transparent, vibrant, refractive, lit from above, floating in depth.

### 2.1 The seven laws of liquid glass

1. **Extreme translucency.** Primary glass is 2–6% white fill. The background MUST be clearly visible through every panel. If a panel looks like a solid surface, it is wrong.
2. **Vibrancy.** Glass saturates and brightens what's behind it (`saturate(180–200%) brightness(110–125%)`). Content behind glass should look *more alive*, not duller.
3. **Specular edges.** Light hits glass from the top-left. Top/left edges get bright hairline highlights (up to 30% white); right/bottom edges nearly vanish (2–5%). This directional lighting replaces borders.
4. **Depth through light, not borders.** Layering is communicated by inner top highlights + soft outer shadows. Do NOT draw visible outline borders around glass panels.
5. **Floating quality.** Panels hover above the environment with soft, wide, low-opacity shadows. Nothing looks glued to the screen.
6. **Organic geometry.** Large radii: panels 20–28px, cards 16–20px, controls as pills (9999px). No sharp corners except in code blocks.
7. **A rich environment.** Glass is invisible over flat backgrounds. The app environment MUST contain vibrant gradient color fields (see §3) so translucency is perceivable and meaningful.

### 2.2 Glass recipes (use exactly)

**M1 — Primary glass (sidebar, right panel, composer shell):**
```css
background: linear-gradient(165deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
backdrop-filter: blur(32px) saturate(180%) brightness(115%);
border-top: 1px solid rgba(255,255,255,0.28);
border-left: 1px solid rgba(255,255,255,0.14);
border-right: 1px solid rgba(255,255,255,0.04);
border-bottom: 1px solid rgba(255,255,255,0.02);
box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 8px 40px rgba(0,0,0,0.25);
border-radius: 24px;
```

**M2 — Elevated glass (cards, tool cards, messages, chips containers):**
```css
background: linear-gradient(165deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0.03) 100%);
backdrop-filter: blur(40px) saturate(200%) brightness(120%);
border-top: 1px solid rgba(255,255,255,0.30);
box-shadow: inset 0 1px 0 rgba(255,255,255,0.22), 0 12px 48px rgba(0,0,0,0.35);
border-radius: 20px;
```

**M3 — Stage glass (modals, spotlight overlay, artifact stage):**
```css
background: linear-gradient(165deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.04) 100%);
backdrop-filter: blur(48px) saturate(200%) brightness(125%);
border-top: 1px solid rgba(255,255,255,0.35);
box-shadow: inset 0 1px 0 rgba(255,255,255,0.25), 0 24px 80px rgba(0,0,0,0.5);
border-radius: 28px;
```

**M4 — Signal glass (permission / success / error surfaces):**
Same as M2 but tinted: warning `rgba(255,176,32,0.10)`, danger `rgba(255,93,93,0.10)`, success `rgba(52,199,123,0.10)` blended over the white gradient. Keep specular top edge.

**Specular sweep (apply as ::before overlay on interactive elements):**
```css
background: linear-gradient(135deg, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.0) 45%);
```

**Pill control (buttons, chips, composer tokens):**
```css
border-radius: 9999px;
background: rgba(255,255,255,0.08);
backdrop-filter: blur(24px) saturate(180%);
box-shadow: inset 0 1px 0 rgba(255,255,255,0.22), 0 2px 8px rgba(0,0,0,0.2);
```

### 2.3 Explicitly FORBIDDEN (auto-reject list)

- ❌ Opaque/near-opaque panel fills (>15% white or solid hex panels)
- ❌ Uniform 1px borders on all four sides of glass panels
- ❌ Heavy frosted blur that erases the background (blur > 60px)
- ❌ Desaturating blur (no `saturate(<100%)`)
- ❌ Flat solid dark backgrounds with no color fields behind glass
- ❌ Small radii (<12px) on panels and cards
- ❌ Hard drop shadows (must be wide, soft, low opacity)
- ❌ Neon glow everywhere; glow is reserved for status only
- ❌ Extra unrequested chrome: top navbars, "Deploy" buttons, breadcrumbs, marketing headers

---

## 3. Environment Backdrop

The environment is what makes glass readable. Dark-first.

```css
/* App base */
background: #0B0D10;

/* Vibrant field mesh — MUST exist behind all glass */
background-image:
  radial-gradient(60% 50% at 18% 12%, rgba(69,179,255,0.16) 0%, transparent 60%),
  radial-gradient(50% 45% at 82% 22%, rgba(155,140,255,0.14) 0%, transparent 60%),
  radial-gradient(55% 55% at 60% 88%, rgba(47,212,194,0.10) 0%, transparent 60%);
```

- Fields are soft, wide, low-opacity (10–16%) — ambient light, not wallpaper.
- The mesh shifts hue subtly per context: default blue/violet, amber-tinted when a HIGH_RISK permission is pending, green-tinted pulse on run completion.

---

## 4. Color System

Base is low-chroma graphite. Color is reserved for meaning.

### Dark mode (default)
| Token | Value | Use |
|---|---|---|
| `bg-deep` | #0B0D10 | environment base |
| `bg-app` | #101318 | app base |
| `text-primary` | #F2F5F8 | body text |
| `text-secondary` | #A7B0BA | labels, secondary |
| `text-tertiary` | #6B7480 | metadata |
| `glass-edge` | rgba(255,255,255,0.28) | specular tops |

### Semantic accents
| Token | Value | Meaning |
|---|---|---|
| `accent` | #45B3FF | streaming, retrieval, local-model active |
| `reasoning` | #9B8CFF | deep reasoning / main model |
| `memory` | #2FD4C2 | memory references |
| `success` | #34C77B | completed / accepted |
| `warning` | #FFB020 | CONFIRMATION_REQUIRED, pending edits |
| `danger` | #FF5D5D | HIGH_RISK, failures |
| `neutral` | #8A93A0 | background tool activity |

### Permission tiers (rendered exactly like this)
- **LOW_RISK** → quiet inline notice, no interruption.
- **CONFIRMATION_REQUIRED** → M4 amber glass card, diff preview, `Reject / Approve` specular pill buttons.
- **HIGH_RISK** → M3 modal, red-amber edge glow, focus-trapped, `Cancel / Allow once / Allow for this run`.

### Resource Governor meter (6 tiers)
IDLE (neutral) → LIGHT (memory teal) → MODERATE (accent) → HEAVY (reasoning violet) → CRITICAL (danger) → PAUSED/OVERRIDE (warning, animated stripe).

---

## 5. Typography

- **UI & reading:** Inter (400/500/600). **Code & data:** JetBrains Mono (400/500).
- Scale: 11 micro-label (uppercase, +0.06em tracking) · 12 caption · 14 body-sm · 16 body (line-height 1.7) · 18 title-sm · 22 title · 28 display.
- Reading column max width: **72ch**.
- Micro-labels for: system status, tab names, metadata, model badges.
- Code blocks: 13px mono, own recessed surface (`rgba(0,0,0,0.35)`, radius 12px, NO blur — code must be crisp).

---

## 6. Layout Architecture

Desktop three-column shell. Columns are floating glass slabs with 12–16px gaps between them and the window edges — the environment backdrop peeks through the gaps.

```
┌────────────┬─────────────────────────────────┬──────────────┐
│ Sidebar    │ Conversation Canvas             │ Intelligence │
│ 260px      │ fluid · 72ch reading column     │ Panel 360px  │
│ M1 glass   │                                 │ M1 glass     │
└────────────┴─────────────────────────────────┴──────────────┘
            floating status bar (bottom, pill, M2)
```

### Sidebar (260px)
New Chat · Search · Projects (expandable) · Chats · Memory Library · Skills · Settings — then a footer: Local-only badge + model health dot.
Active item = M2 elevated pill with accent icon.

### Canvas
Session header → message stream → floating composer (bottom, M2, radius 28px, floats with shadow).

### Intelligence Panel (360px)
Tabs: **Artifact · Files · Context · Activity · System**. Tab bar = pill-style segmented control (active tab is an elevated M2 pill).

### Status bar
Floating pill, bottom-center of canvas: `🛡 Local only · ● Index ready · 12,403 chunks · Context 14k/32k`.

### Responsive
<1280px: intelligence panel becomes slide-over. <960px: sidebar collapses to icon rail.

---

## 7. Component Inventory

| # | Component | Spec |
|---|---|---|
| 1 | **GlassPanel** | M1 shell, no visible border, specular top edge |
| 2 | **GlassCard** | M2; variants default/active/success/warning/danger |
| 3 | **SpecularButton** | pill; primary (accent fill + specular sweep), secondary (glass), danger, warning; states hover/pressed/disabled |
| 4 | **ContextChip** | pill: icon + label; for files, memory entries, skills, models |
| 5 | **AgentStepper** | vertical timeline; states pending/running/success/warning/failed/blocked; running step has animated accent glow |
| 6 | **ToolCallCard** | collapsed: `✓ filesystem.read — InventoryComponent.cpp`; expanded: path, status, duration, result; edit variant embeds DiffViewer + Approve/Reject |
| 7 | **PermissionDialog** | tiered per §4; HIGH_RISK is M3 modal, focus-trapped |
| 8 | **DiffViewer** | additions soft-green glass, deletions soft-red glass, "Agent proposed" label, per-file Accept/Reject pills |
| 9 | **ArtifactFrame** | sandboxed preview; controls: Code / Preview / Split / Versions / Download |
| 10 | **Composer** | M2 floating glass; tokens: project selector, model badge, skill chip, tools chip; send = accent pill with specular sweep; streaming → stop control |
| 11 | **LocalOnlyBadge** | shield + "Local only"; flips to warning tone if cloud fallback engages |
| 12 | **ModelBadge** | `MAIN · Qwen3-30B` micro-label with reasoning dot |
| 13 | **GovernorMeter** | compact 6-segment bar for System tab / status |
| 14 | **EmptyState** | glass illustration + one primary action |

---

## 8. Screen Specifications

### S1 — Main Workspace (HERO)
Three-column shell per §6. Canvas shows: user message (M2 bubble, right) with two file chips (`InventoryComponent.cpp`, `InventoryTypes.h`) → AgentStepper with two successful `filesystem.read` steps → assistant message (M2 card) with model badge `MAIN · Qwen3-30B`, inline code block, and a **pending file-edit approval card** (M4 amber glass: "Agent wants to modify InventoryComponent.cpp · View diff · Reject · Approve"). Intelligence panel shows Files tab with the project tree; footer shows Governor meter.

### S2 — Spotlight Overlay (Alt+Space)
Dimmed desktop backdrop; centered floating M3 glass panel 680px wide, radius 28px. Single input row with project token `JARVIS Workspace`, model token `Auto`, tools token `Safe`. Below: two compact result cards (one answer, one pending approval). Action: "Expand to workspace".

### S3 — Agent Run Timeline
Activity tab expanded to full view: run header (`Run #a41f · Running · MAIN · Qwen3-30B`), full AgentStepper (8 steps incl. one `awaiting approval` warning step), token/latency stats in micro-labels, files-changed chip row.

### S4 — Project Overview
Project "Unreal Inventory System": description, instructions card, linked folders, index status (`12,403 chunks · ready`), skills row (`Unreal Engine` active chip), tool permissions list, conversation history list.

### S5 — Memory Inspector
Memory Library: search field, category filter chips (Preference/Fact/Workflow/Project), list of M2 memory cards each with content, source trace, edit/delete. Example entry: "User prefers modular UE5 C++ with Gameplay Ability System patterns."

---

## 9. Streaming & States

Event-driven (SSE): `message_start · text_delta · tool_call · tool_result · file_change · artifact_update · agent_status · message_complete · error`. UI never invents state.

Status copy: `Reasoning… · Searching project… · Reading 3 files… · Preparing patch… · Your approval is required to continue.`

Streaming text animates opacity-in only — never position. Send button morphs to Stop during streaming.

---

## 10. Motion

`instant` 80ms · `fast` 140ms · `standard` 220ms · `slow` 320ms · `glass` 400ms.
Easing: `cubic-bezier(0.32, 0.72, 0.28, 1)`.
Panels rise and settle (translateY 8px → 0 + fade). Hover = light moving across glass (specular sweep brightens), not scale bounces. Permission cards enter with extra weight (scale 0.98→1 + edge glow). Honor `prefers-reduced-motion` and `prefers-reduced-transparency` (fallback: solid elevated surfaces).

---

## 11. Accessibility

- WCAG AA text contrast over glass — every glass surface has an invisible scrim (`rgba(10,12,16,0.35)`) behind body text.
- Status = icon + label + color, never color alone.
- Full keyboard nav, visible focus rings, command palette.
- `aria-live` polite region for agent status; HIGH_RISK dialogs focus-trapped.

---

## 12. Realistic Sample Content (NEVER use lorem ipsum)

| Slot | Content |
|---|---|
| Projects | "JARVIS Workspace", "Unreal Inventory System" |
| Files | `InventoryComponent.cpp`, `InventoryTypes.h`, `AbilitySystem.Build.cs` |
| Tool calls | `filesystem.read`, `search.project`, `terminal.execute` |
| Models | `MAIN · Qwen3-30B`, `FAST · Qwen3-4B`, `EMBED · Qwen3-0.6B` |
| Memory | "User prefers modular UE5 C++ with Gameplay Ability System patterns." |
| Status | "Local only · Index ready · 12,403 chunks · Context 14k/32k" |
| Run | "Run #a41f · 8 steps · 2.4k tokens · 6.2s" |

---

## 13. Forbidden Elements

❌ Anthropic/Claude logos, brand colors, or UI clones · ❌ Apple SF Symbols/iOS assets · ❌ generic chatbot avatars or mascot icons · ❌ telemetry/analytics dashboards · ❌ cloud-only indicators · ❌ top navigation bars, breadcrumbs, marketing headers, "Deploy" or billing buttons · ❌ lorem ipsum · ❌ more than 5 tabs in the intelligence panel.

---

## 14. ANTI-GRAVITY → STITCH EXECUTION PROTOCOL

Antigravity, execute in this exact order:

1. **Create project** titled `Liquid Workspace — JARVIS`.
2. **`upload_design_md`** with this file, then **`create_design_system_from_design_md`** with `deviceType: DESKTOP`.
3. **Generate screens in priority order** (one call each, `deviceType: DESKTOP`), using the prompts below. After each generation, verify against §2.3 forbidden list; if any surface looks opaque or uniformly bordered, regenerate with the prompt prefixed: "Strictly enforce DESIGN.md §2 — surfaces must be near-transparent liquid glass with specular top edges and visible background bleed."
4. **Generate 2 variants** of S1 (Main Workspace) for direction selection.
5. **Apply the design system** to all screens for consistency.

### Generation prompts

**S1:** "Desktop AI workspace, dark mode, iOS-26-style liquid glass per DESIGN.md §2–6. Three floating glass columns over a dark environment with soft blue/violet/teal gradient fields visible THROUGH every panel: 260px sidebar (New Chat, Search, Projects, Chats, Memory Library, Skills, Settings, Local-only footer badge), fluid center conversation with a right-aligned user message containing two file chips (InventoryComponent.cpp, InventoryTypes.h), a two-step completed agent tool timeline, an assistant card labeled MAIN · Qwen3-30B with a C++ code block, and an amber glass pending file-edit approval card with View diff / Reject / Approve pill buttons; 360px right Intelligence Panel with Artifact/Files/Context/Activity/System tabs showing a file tree; floating glass composer at bottom with project selector, model badge, and accent send pill; floating status pill: Local only · Index ready · 12,403 chunks · Context 14k/32k. Near-transparent glass (2–8% fill), 32–48px blur with 180% saturation, bright specular top edges, no visible borders, large 20–28px radii, pill controls. No top navbar, no logos, no lorem ipsum."

**S2:** "Alt+Space spotlight overlay: dimmed desktop behind, centered floating liquid-glass panel 680px wide, 28px radius, near-transparent with vivid background bleed, single input row with pill tokens (JARVIS Workspace / Auto / Safe), two compact result cards below (one answer, one pending approval), 'Expand to workspace' ghost button. iOS 26 liquid glass treatment per DESIGN.md §2."

**S3:** "Agent Run Timeline screen per DESIGN.md S3: dark liquid-glass workspace, full-height Activity view, run header 'Run #a41f · Running · MAIN · Qwen3-30B', vertical agent stepper with 8 steps including one amber 'awaiting approval' step, micro-label stats (2.4k tokens · 6.2s), files-changed chip row. Authentic iOS liquid glass materials."

**S4:** "Project Overview screen per DESIGN.md S4: liquid-glass project card for 'Unreal Inventory System' with description, instructions card, linked folders, index status '12,403 chunks · ready', active skill chip 'Unreal Engine', tool permissions list, conversation history list. iOS liquid glass, dark, no extra chrome."

**S5:** "Memory Inspector screen per DESIGN.md S5: liquid-glass memory library with search field, category filter chips (Preference/Fact/Workflow/Project), memory cards including 'User prefers modular UE5 C++ with Gameplay Ability System patterns' with source trace and edit/delete actions. iOS liquid glass, dark."

---

## 15. Token Export (Tailwind/CSS baseline)

```css
:root[data-theme="dark"] {
  --bg-deep:#0B0D10; --bg-app:#101318;
  --glass-fill:rgba(255,255,255,.04); --glass-blur:32px; --glass-sat:180%;
  --glass-edge-top:rgba(255,255,255,.28); --scrim:rgba(10,12,16,.35);
  --text-1:#F2F5F8; --text-2:#A7B0BA; --text-3:#6B7480;
  --accent:#45B3FF; --reasoning:#9B8CFF; --memory:#2FD4C2;
  --success:#34C77B; --warning:#FFB020; --danger:#FF5D5D;
  --r-card:20px; --r-panel:24px; --r-stage:28px; --r-pill:9999px;
  --m-instant:80ms; --m-fast:140ms; --m-std:220ms; --m-slow:320ms; --m-glass:400ms;
}
```

*End of DESIGN.md v2.0*