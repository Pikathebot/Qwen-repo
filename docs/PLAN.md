# Local Jarvis Assistant — Build Plan

**Stack:** FastAPI + Ollama (Qwen3.5 9B Q4) + OpenRouter (free tier, Heavy Mode fallback)
**Build tools:** Google Antigravity (scaffolding, multi-file agentic builds) + OpenCode (terminal CLI, focused edits)
**Target machine:** Windows 11, i7-14700HX, RTX 4060 8GB VRAM, 16GB RAM

---

## 0. Tool roles — don't conflate these

There are two separate sets of "models" in this project. Keep them mentally separate or the config will get confusing:

| | Models that BUILD the app | Models that RUN INSIDE the app |
|---|---|---|
| What they do | Write/edit your code | Power the assistant itself |
| Where | Antigravity (Gemini 3 / Claude / GPT-OSS) or OpenCode (via OpenRouter free tier) | Ollama, local, Qwen3.5 9B Q4 |
| Cost | Free tier / preview | Free, local, no API cost |

OpenRouter shows up in **both** columns — you might use it to power OpenCode while coding, AND later as your app's own Heavy Mode fallback. Don't let the same API key confuse "the tool that's coding this" with "the tool the finished app calls."

---

## 1. Environment setup checklist

- [ ] Install Ollama, run `ollama pull qwen3.5:9b` (confirmed official tag — Q4_K_M quant, 6.6GB, 9.65B params, 262K context, tool-calling supported)
- [ ] Verify it's serving: `curl http://localhost:11434/api/tags`
- [ ] **VRAM note:** 6.6GB weights on an 8GB card leaves only ~1.4GB for KV cache — much tighter than the ~9GB headroom a 16GB card gets. Don't expect to use anywhere near the full 262K context; watch VRAM closely once tool outputs/file contents start getting fed into context. Factor this smaller margin into the Phase 3 resource-governor thresholds below.
- [ ] Create an OpenRouter account, generate a free-tier API key, note the free-tier rate limits (check current limits on openrouter.ai/docs before relying on them for anything time-sensitive)
- [ ] Install OpenCode CLI, point its provider config at either your OpenRouter key or local Ollama endpoint
- [ ] Install Antigravity, sign in, open this project folder as its workspace
- [ ] `pip install fastapi uvicorn httpx ollama psutil pynvml python-dotenv` (in a venv)
- [ ] `git init`, and before your first commit create `.gitignore` covering at minimum: `.env`, `venv/` or `.venv/`, `__pycache__/`, `*.db` (your SQLite memory store will contain conversation content — don't commit it)
- [ ] Put the OpenRouter key only in `.env` (never in `.env.example`, never hardcoded in `model_router.py`). `.env.example` should show the variable name with a placeholder value only.

---

## 2. Project structure

```
jarvis-assistant/
├── docs/
│   ├── PLAN.md              (this file)
│   └── ARCHITECTURE.md      (fill in as design decisions solidify)
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── agent/
│   │   │   ├── orchestrator.py  # talks to Ollama, handles tool-call loop
│   │   │   ├── tools/            # each tool = one file, one function
│   │   │   ├── permissions.py   # risk-tier classification + confirmation gate
│   │   │   └── model_router.py  # Normal Mode (Ollama) vs Heavy Mode (OpenRouter)
│   │   ├── governor/
│   │   │   └── resource_governor.py  # psutil/pynvml polling loop
│   │   ├── memory/
│   │   │   └── store.py         # SQLite short-term + long-term memory
│   │   └── config.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/                    # later: tray app / hotkey UI
```

---

## 3. Phased build order (build ONE phase at a time — don't skip ahead)

**Phase 0 — Skeleton**
FastAPI service with one `/chat` endpoint that proxies straight to Ollama. No tools, no permissions, no governor yet. Goal: prove the base loop works end to end.
*Done when:* `curl` or Postman to `/chat` with a plain message returns a coherent Qwen3.5 response, consistently, with the server staying up across multiple requests (not just one lucky run).

**Phase 1 — Tool calling**
Add Ollama's native tool-calling with 1–2 LOW-RISK tools only (e.g. read file, list directory). Confirm the model can actually invoke them correctly with Qwen3.5.
*Done when:* you can ask a question that requires the tool (e.g. "what's in this file?") and get back a response that actually used the tool's real output — not the model guessing/hallucinating an answer. Test with at least 3 different phrasings of the same request.

**Phase 2 — Permission layer**
Add `permissions.py`: every tool call gets classified LOW-RISK / CONFIRMATION-REQUIRED / HIGH-RISK before execution. LOW-RISK auto-runs; the other two return a "needs approval" response instead of executing. This is the core safety feature — get it right before adding more tools.

**The tier lookup must be hardcoded, never model-decided.** `permissions.py` should hold a fixed mapping — e.g. a dict of `{tool_name: risk_tier}` — that the code checks *before* running a tool, regardless of what the model says about the action. Never let the LLM classify its own action's risk (via a prompt like "is this safe?") and never trust a risk level the model includes in its own tool-call output. If a new tool doesn't have an entry in the mapping, default to CONFIRMATION-REQUIRED, not LOW-RISK — unclassified should never mean auto-approved.
*Done when:* you can demonstrate all three tiers behaving correctly — a LOW-RISK tool runs with no prompt, a CONFIRMATION-REQUIRED tool blocks and returns an approval request instead of executing, and manually editing the tool→tier mapping changes the behavior (proving it's actually the lookup driving this, not the model).

**Phase 3 — Resource governor**
Background thread polling GPU/VRAM (pynvml) and CPU/RAM (psutil) on an interval. When thresholds are breached (e.g. gaming, UE5 build), the governor flips a flag that `main.py` checks before accepting new generation requests — reject or queue instead of running.
*Done when:* you can artificially load the GPU (e.g. run a game or a benchmark tool) and watch `/chat` requests get rejected/queued in real time, then resume normally within one polling interval after the load stops.

**Phase 4 — Heavy Mode via OpenRouter**
`model_router.py` decides: simple request → Ollama (Normal Mode); flagged-complex request → OpenRouter free-tier model (Heavy Mode). Define what "complex" means concretely (e.g. explicit user request, or task type) rather than guessing.
*Done when:* a request that should route to OpenRouter actually does (verify via logs, not just "the response seemed different"), and a Normal Mode request never accidentally calls the paid/rate-limited API.

**Phase 5 — Memory**
SQLite-backed short-term conversation memory first. Long-term preference storage only after short-term is solid — don't build both at once.

*Context compaction (build this alongside short-term memory, not after):* storing history isn't enough — without compaction, long sessions will hit Qwen3.5's context limit, and your real ceiling is tighter than the model's theoretical 262K because of the ~1.4GB VRAM headroom noted above. Add:
- Rough token tracking per conversation (chars/4 estimate is fine to start; swap for a real tokenizer later if needed)
- A threshold check before each request — approaching the limit triggers compaction instead of sending the full history
- Cheapest step first: prune/drop old bulky tool outputs (file reads, search results) before falling back to full summarization — this is usually where most of the token bloat lives
- Full compaction fallback: send the older half of the conversation to the model with a "summarize into key facts/decisions" prompt, replace those messages with the summary, keep recent messages verbatim
- Don't do this silently — log or surface when compaction happens, unlike Antigravity's behavior, so you can debug "the assistant forgot X" issues later

*Done when:* a conversation deliberately pushed past your token threshold triggers compaction automatically, the summary preserves the actual facts you'd expect (test with something concrete you said earlier, like a filename or a decision), and it's logged/visible when it happened.

**Phase 6 — MCP integration + skills**
Wire in filesystem and memory MCP servers. UE5 MCP comes later, after the core loop is trusted.

*Skills (separate from MCP):* MCP gives you tool-calling capabilities, but a "skill" in the Leon/OpenClaw sense is closer to a reusable instruction set — a packaged way of telling the model how to handle a certain kind of request, not a new tool it can call. This is an orchestration-layer feature, not an MCP feature:
- A `skills/` folder, one markdown file per skill (name, description, instructions — same shape as this project's own file-based skills pattern)
- At request time, orchestrator.py does a lightweight match (keyword or embedding) against skill descriptions and selectively injects the relevant skill's instructions into the system prompt
- Keep it optional/additive — skills should shape *how* the model responds, not bypass the permission layer from Phase 2

*Done when:* an MCP tool call round-trips successfully through your existing permission layer (i.e. Phase 2's gating still applies to MCP tools, not just your hand-written ones), and at least one skill file measurably changes the model's response style/behavior when its keywords are present vs. absent.

**Phase 7 — Background service + UI**
Windows service/tray icon, global hotkey.
*Done when:* the assistant survives a logout/login or reboot without manual restart, and the hotkey/tray icon work when a game or UE5 is running at the same time (the actual point of Phase 3).

**Phase 8 — Voice/wake-word**
Last, once everything above is stable.
*Done when:* the wake word triggers reliably in a normal room (not silent-lab conditions), and a false trigger during active gameplay doesn't interrupt the game or spike GPU usage.

---

## 4. Master prompt template (for Antigravity or OpenCode, Phase 0)

```
Build a minimal FastAPI backend for a local AI assistant.

Requirements:
- Single POST /chat endpoint accepting {"message": str}
- It calls a local Ollama instance at http://localhost:11434 using model "qwen3.5:9b"
  (confirmed official tag, Q4_K_M, 6.6GB — use the ollama Python client, not raw httpx, unless it's unavailable)
- Return the model's plain text response as JSON: {"response": str}
- Include a requirements.txt and a .env.example with OLLAMA_HOST as a configurable var
- No tool-calling, no memory, no auth yet — this is intentionally the smallest
  possible working slice. Do not add anything beyond what's listed here.
- Structure it under backend/app/ per this layout: [paste section 2 above]
```

Keep each Antigravity/OpenCode prompt scoped to exactly one phase from section 3. Feeding it the whole plan at once is how you end up with an overbuilt Phase 4 and an untested Phase 1.

---

## 5. Session hygiene (Antigravity/OpenCode specific)

- Antigravity compacts context **silently and aggressively**, with no token meter — it can forget an earlier decision without telling you. OpenCode's compaction is more transparent (tracked, triggered near the real limit, with a visible summary step), but still: don't rely on either tool's in-session memory as your source of truth.
- **Before starting a new session on a new phase, re-paste (or point the tool at) `PLAN.md` and any `ARCHITECTURE.md` decisions.** Treat these files as the durable record; treat the chat session as disposable.
- If mid-session the agent seems to have forgotten something you established earlier (a file structure, a naming choice, a constraint), don't assume it's still consistent — check the actual files it produced against this plan rather than trusting its own account of what it did.
- **The same caution applies to Antigravity acting on your machine, not just remembering things.** It can run terminal commands and edit files autonomously — review what it's about to run/change before accepting, especially anything touching git, deleting files, or installing packages. This is the same principle your own app's permission layer enforces — worth applying to the tool building it too.

---

## 6. Notes / open decisions to fill in later
- ~~Exact Ollama tag~~ — confirmed: `qwen3.5:9b`, Q4_K_M, 6.6GB
- Concrete GPU/VRAM/CPU thresholds for the resource governor (needs real measurement on your machine, not guessed numbers — remember only ~1.4GB VRAM headroom above the model weights)
- What counts as "complex enough for Heavy Mode" (Phase 4)
- Heavy Mode model choice — still open per the original design doc
