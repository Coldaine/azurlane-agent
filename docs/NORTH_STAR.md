# NORTH STAR

## Vision

- **Replace the entire ALAS application** with an LLM-augmented automation system
- ALAS represents 9 years of expert engineering: Chinese OCR, pixel matching, mask detection
- That work encodes **implicit workflows and a state machine** that reliably automates Azur Lane
- We extract that implicit knowledge into **explicit, programmatic tools**
- LLM usage is reserved for **recovery**: stuck states, errors, unexpected situations

## Requirements

- **Deterministic tools first**: Normal operation uses fast, reliable programmatic tooling
- **LLM for recovery only**: Orchestrator intervenes when tools fail or state is unexpected
- **Tool ambiguity**: Same tools work whether Claude Code drives (dev/test) or Gemini runs autonomously
- **Full context on failure**: When LLM intervenes, it has access to screen state, recent history, and intended action
- **Fix or log**: LLM either resolves the issue manually or records it for human review

## Transition Constraint

**ALAS must remain a fully functional installation throughout development.** The owner actively uses it for daily gameplay. The LLM-augmented system is being built *alongside* ALAS, not on top of it. This constraint holds until the new system fully replaces ALAS.

The project is splitting into two repos to enforce clean separation: **alas-wrapped** (fork of Zuosizhu, auto-synced by Jules every ~2 days) for daily gameplay, and **azurlane-agent** (new, clean, Python 3.10+) for the MCP server, standalone tools, and behavioral catalog. See [ROADMAP.md](./ROADMAP.md) Phase 1a for details.

## Architecture

Two-tier model hierarchy:
1. **Orchestrator**: Gemini (CLI or LangGraph wrapper) - makes decisions, calls tools, handles recovery
2. **LLM Vision** (Gemini Flash): Screen understanding when deterministic tools fail — cheap enough for live use

**Terminology note**: "Vision" in this project means two distinct things:
- **Deterministic template-matching** (`match_asset`, `click_asset`): OpenCV-based, fast, no LLM. These are regular tools in the deterministic layer, not a fallback.
- **LLM vision** (Gemini Flash analyzing a screenshot): Used for recovery only, when deterministic tools (including template-matching) fail or return unexpected state.

When this document says "LLM for recovery only," it means the *LLM vision* tier. Template-matching tools are deterministic and belong in the normal operation path alongside `goto` and `ensure_main`.

**Single-harness principle**: The MCP server is the same interface for development and production. Claude Code (dev) and Gemini (prod) both call the same MCP tools. Every dev session is also an integration test of the production path. No custom orchestrator is needed yet — the coding agent already calls tools, reads results, decides next steps, and recovers from errors. Custom hardening (retry policies, scheduling, durable state) is optional for later.

## Approach

**Extract, don't wrap.** ALAS is a reference implementation, not a runtime dependency. The goal is to study ALAS's behavior — thresholds, search patterns, asset paths, state transitions — and rewrite that logic as clean, standalone tools that don't import from `module.*` or depend on ALAS internals.

The progression:
1. **Now (wrapping)**: Import from `alas_wrapped/` to prove tool contracts work and understand the behavior. This is pragmatic but temporary.
2. **Behavioral catalog**: Document every ALAS workflow as implementation-agnostic requirements — the *what*, not the *how*. This is the bridge between "reading ALAS source" and "writing standalone code."
3. **Extraction**: Rewrite each tool as standalone code, guided by the behavioral catalog. ALAS is the reference for *what* to do, not a library to call.
4. **Cutover**: Standalone tools cover enough workflows that the bot no longer touches `alas_wrapped/`. ALAS remains installed for the owner's direct gameplay use only.

ALAS is a Python 3.9 legacy codebase with tight internal coupling, implicit global state, and heavyweight dependencies. The longer tools depend on it at runtime, the harder it becomes to cut over. Each new tool should move toward standalone where feasible.

## End-State Architecture

When extraction is complete, the system looks like this:

- **ALAS runs separately** for the owner's daily gameplay — in its own repo (`alas-wrapped`), auto-synced with upstream by Jules. No hooks, no MCP wiring, no modifications.
- **New bot code** lives in a **separate, clean repo** (`azurlane-agent`). Python 3.10+, clean dependency tree. It depends only on **ADB** (screenshot, tap, swipe) and its own logic. No `from module.*` imports. No ALAS process running.
- **Screen understanding** is **deterministic first**: OCR (PaddleOCR or similar), template matching, pixel checks for known screens. These handle 90%+ of operations. An unknown or unexpected screen *is* a recovery state — the agent uses its own VLM (screenshot analysis) to figure out what happened.
- **The MCP server** is a thin layer over ADB and standalone tools — not a wrapper around a running ALAS process. It doesn't boot `AzurLaneAutoScript`, doesn't load ALAS's OCR into memory, doesn't import from `module.*`.
- **The behavioral catalog** is the spec that standalone tools are built against. When someone asks "how does commission collection work?", the answer comes from the catalog, not from reading `module/commission/commission.py`.
- **ADB connection ownership**: The standalone MCP server owns the ADB connection exclusively. ALAS and the new agent cannot share an ADB connection to the same emulator simultaneously — one process owns it at a time. When the new system is running, ALAS is not connected. This must be planned for during the transition (see [ROADMAP.md](./ROADMAP.md)).
- **Persistent screen state**: Deterministic tools continuously OCR known screen elements (coin balance, gem balance, oil balance, etc.) based on the current screen and known positions. This state is maintained as an MCP resource the agent can query at any time, giving it situational awareness without needing to analyze screenshots.

## Behavioral Catalog

The behavioral catalog (`docs/plans/behavioral_catalog.md`) is the critical bridge document. It captures every ALAS workflow as **implementation-agnostic requirements** that standalone tools can be built against.

For each workflow domain (login, commission, daily, combat, etc.), the catalog documents:
- **Preconditions**: What screen/state must be true before starting
- **Steps**: The sequence of screens, taps, waits, and decisions — described in terms of what the user sees, not ALAS function names
- **Decision rules**: How ALAS decides what to do (thresholds, timers, config flags)
- **Asset references**: Which images/templates are matched, what they look like, where on screen they appear
- **Postconditions**: What state the game should be in when done
- **Error cases**: What can go wrong and how ALAS handles it (retry, skip, escalate)

The catalog is written by reading ALAS source code module-by-module and extracting the behavioral specification. It is the single document that makes standalone tool development possible without constantly re-reading ALAS internals.

## Runtime Architecture

The orchestrator executes tools via MCP. Tools are either:
- **Standalone deterministic tools**: Navigation, workflow automation, screen parsing — built from the behavioral catalog, no ALAS dependency. These are sophisticated tools that return structured summaries of what they did (success/failure, observed state, expected state). The orchestrator reads those summaries and decides next steps — it does not need to look at the screen when tools succeed.
- **ADB primitives**: Screenshot, tap, swipe — thin wrappers over ADB.
- **Persistent screen state** (MCP resource): OCR reads known screen values (balances, resource counts, button states) based on current screen and known positions. Updated continuously. The agent queries this resource for situational awareness without needing VLM.

**Normal flow**: Agent calls tool → tool returns structured summary → agent updates its plan and moves on. No LLM vision involved. Fast, cheap, reliable.

**Recovery flow**: Tool returns unexpected state, or agent encounters a screen it has no tool for. An unknown screen *is* a recovery state. The agent takes a screenshot, analyzes it with its own VLM, and either calls more tools to fix the situation or logs for human review.

The same tool interface serves both development (Claude Code) and production (autonomous Gemini).
