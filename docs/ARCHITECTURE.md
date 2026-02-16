# Architecture Overview

> This document implements the vision defined in [NORTH_STAR.md](./NORTH_STAR.md)
> Current project status can be found in [ROADMAP.md](./ROADMAP.md)

## Current State (Monorepo + ALAS Wrapping)

```
┌─────────────────────────────────────────────────────────────────┐
│                        AGENT (dev time)                          │
│              (Claude Code / Gemini CLI)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP (JSON-RPC 2.0 over stdio)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     alas_mcp_server (FastMCP)                     │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ ADB Tools   │  │ State Tools │  │  Template-Match Tools   │  │
│  │ screenshot  │  │ get_state   │  │  match/click_asset      │  │
│  │ tap, swipe  │  │ goto        │  │  (not yet in MCP)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ Python imports from module.*
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       alas_wrapped                               │
│  Full ALAS process loaded into memory                           │
│  OCR, state machine, template matching via ALAS internals       │
└─────────────────────────────────────────────────────────────────┘
```

**Problems with this state:**
- MCP server boots an entire ALAS process and imports from `module.*`
- Tools are coupled to ALAS internals (Python 3.9, heavyweight deps)
- Can't evolve tools without risk of breaking the owner's daily ALAS usage
- Temptation to keep wrapping instead of extracting

---

## Target State (Separate Repos + Standalone Tools)

```
┌─────────────────────────────────────────────────────────────────┐
│                        AGENT                                     │
│         (Claude Code / Gemini CLI / autonomous Gemini)           │
│                                                                  │
│  Same agent for dev AND prod — no separate orchestrator needed   │
│  Uses VLM (screenshot analysis) for recovery when tools fail     │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP (JSON-RPC 2.0 over stdio)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              MCP Server (thin, standalone)                        │
│              Repo: azurlane-agent • Python 3.10+                 │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ ADB Tools   │  │ Deterministic│  │   Workflow Tools      │  │
│  │ screenshot  │  │ Screen Tools │  │   login, commission   │  │
│  │ tap, swipe  │  │ OCR, template│  │   daily, combat       │  │
│  │             │  │ pixel checks │  │   (from catalog spec) │  │
│  └─────────────┘  └──────────────┘  └───────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │ ADB over TCP (exclusive connection)
                             ▼
                     Android Emulator
                    (LDPlayer primary / MEmu fallback)


  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
  │          ALAS (separate repo, separate process)               │
  │  Repo: Coldaine/alas-wrapped (fork of Zuosizhu)              │
  │  Jules auto-syncs upstream every ~2 days                     │
  │  Owner runs for daily gameplay — no agent hooks              │
  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

**Key differences:**
- MCP server is standalone — no ALAS process, no `module.*` imports
- Screen understanding is deterministic (OCR, template matching, pixel checks) — agent VLM is recovery-only
- ALAS runs in a completely separate repo, untouched, auto-synced by Jules
- Same MCP interface for dev (Claude Code testing interactively) and prod (Gemini running autonomously)
- Agent is just an LLM with MCP tools — no custom orchestrator code needed initially

---

## Two-Tier Operation Model

```
Normal flow (90%+):
  Agent → calls deterministic MCP tool → success → next step

Recovery flow (when tools fail):
  Agent → calls deterministic MCP tool → unexpected result
      → Agent takes screenshot via adb.screenshot
      → Agent analyzes screenshot with its own VLM
      → Agent decides: retry / call different tool / log and escalate
```

**Deterministic tools are the workhorse.** They return structured summaries of what they did; the orchestrator reads those summaries and decides next steps without needing to look at the screen. An unknown or unexpected screen *is* a recovery state — the agent uses its own VLM to figure out what happened. This is the recovery layer that ALAS never had.

### Persistent Screen State (MCP Resource)

Deterministic tools continuously OCR known screen elements based on current screen and known positions:
- Coin balance, gem balance, oil balance
- Button states (enabled/disabled/visible)
- Resource counts, timer values

This state is maintained as an MCP resource the agent can query at any time for situational awareness, without needing to take and analyze screenshots.

### ADB Connection Ownership

The standalone MCP server owns the ADB connection exclusively. ALAS and the new agent cannot share a connection to the same emulator simultaneously — one process owns it at a time. Currently the MCP server piggybacks on ALAS's running process; after the repo split, the standalone server manages its own connection.

---

## Repository Structure (Target)

### azurlane-agent (new repo)
```
azurlane-agent/
├── mcp_server/              # MCP tool definitions (FastMCP)
│   ├── adb_tools.py         # screenshot, tap, swipe
│   ├── screen_tools.py      # OCR, template matching, state detection
│   └── workflow_tools.py    # login, commission, daily, combat
├── tools/                   # Standalone tool implementations
│   ├── ocr.py               # Modern OCR (PaddleOCR/EasyOCR)
│   ├── template.py          # Template matching (OpenCV, no ALAS)
│   ├── navigation.py        # Screen state / page detection
│   └── workflows/           # One module per workflow domain
├── docs/
│   ├── NORTH_STAR.md        # Vision (carried over)
│   ├── ROADMAP.md           # Phases (carried over)
│   ├── behavioral_catalog.md # Implementation-agnostic workflow specs
│   └── ...
├── tests/
├── assets/                  # Game assets (templates, reference images)
└── pyproject.toml           # Python 3.10+, clean deps
```

### alas-wrapped (fork repo)
```
Coldaine/alas-wrapped        # Fork of Zuosizhu/Alas-with-Dashboard
├── (standard ALAS structure)
├── config/
│   └── PatrickCustom.json   # Owner's live bot config
└── (minimal patches: config, deploy.yaml, thresholds)
```

---

## Subdomains

### Agent Tooling (Standalone)
- **Status**: Transitioning from ALAS-wrapped to standalone
- **Current**: 8 MCP tools wrapping ALAS internals
- **Target**: Standalone tools with no ALAS dependency
- **Key Doc**: [ROADMAP.md Phase 2](./ROADMAP.md)

### Behavioral Catalog
- **Status**: ⏳ To be written (Phase 1b)
- **Summary**: Implementation-agnostic specs for every ALAS workflow
- **Key Doc**: `docs/plans/behavioral_catalog.md` (planned)

### Upstream Sync (Jules)
- **Status**: ⏳ To be configured (Phase 1a)
- **Summary**: Automated sync of Zuosizhu upstream into the alas-wrapped fork
- **Key Doc**: [ROADMAP.md Phase 1a](./ROADMAP.md)

### Agent Orchestration
- **Status**: Not needed yet — coding agent (Claude Code/Gemini CLI) serves as orchestrator
- **Summary**: Custom orchestrator is optional hardening for Phase 3
- **Key Doc**: [ROADMAP.md Phase 3](./ROADMAP.md)

---

## Development Resources

- [dev/environment_setup.md](./dev/environment_setup.md) - Python 3.9+ setup and launchers
- [dev/testing.md](./dev/testing.md) - Testing philosophy
- [dev/logging.md](./dev/logging.md) - Logging philosophy
- [dev/log_parser.md](./dev/log_parser.md) - Log parser architecture
- [dev/recovery_workflow.md](./dev/recovery_workflow.md) - Upstream-to-wrapped recovery
- [archive/](./archive/) - Historical documentation

## Agent Instructions

- [AGENTS.md](../AGENTS.md) - General agent index
- [CLAUDE.md](../CLAUDE.md) - Claude Code (development orchestrator)
- [GEMINI.md](../GEMINI.md) - Gemini (production orchestrator)
