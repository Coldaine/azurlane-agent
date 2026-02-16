# ALAS Transition Roadmap

> Derived from [NORTH_STAR.md](./NORTH_STAR.md) vision and [ARCHITECTURE.md](./ARCHITECTURE.md) status.

This roadmap tracks the transition from a legacy Python automation script to a clean, LLM-augmented system built from scratch.

## Phases

| Phase | Focus | What happens | Status |
|-------|-------|-------------|--------|
| **Phase 1** | Repo split + behavioral catalog | Separate ALAS from agent code. Document what ALAS does as implementation-agnostic specs. | 🛠️ **Current** |
| **Phase 2** | Standalone tool development | Build clean deterministic tools (OCR, navigation, workflows) in the new repo, guided by the catalog. MCP server exposes them. | ⏳ Next |
| **Phase 3** | Autonomous operation | Agent (Gemini/Claude) drives the bot via MCP tools. Custom orchestrator hardening (scheduling, retries, durable state) only if needed. | ⏳ Planned |

**Key Principle**: The MCP server is the same interface for development and production. When you use Claude Code to build and test tools, you're calling MCP. When the autonomous agent runs the bot, it calls the same MCP. There is no dev/prod split — every development session is also an integration test of the production path.

---

## Phase 1: Repo Split + Behavioral Catalog (Current)

### 1a. Repository Split

Split the current monorepo into two:

| Repo | Contents | Maintenance |
|------|----------|-------------|
| **alas-wrapped** (fork of Zuosizhu) | Running ALAS install for daily gameplay. Clean fork with minimal patches (config, deploy.yaml, thresholds). | **Jules** (Google's agentic CI) auto-syncs with upstream every ~2 days. Compares upstream changes, merges them into the fork without breaking patches, creates PRs for review. |
| **azurlane-agent** (new, clean) | MCP server, standalone tools, behavioral catalog, orchestrator logic, docs. Python 3.10+, no ALAS imports. | Claude Code + owner for active development. |

**Why split now**: Having ALAS code in the same repo makes it too easy to keep importing from `module.*`. Separate repos enforce the "extract, don't wrap" constraint at the filesystem level.

**Jules upstream sync workflow**:
```
Zuosizhu/Alas-with-Dashboard (upstream)
        │
        │  Jules checks every ~2 days
        ▼
Coldaine/alas-wrapped (fork)
        │
        │  Jules: compare, merge, test, create PR
        ▼
Owner reviews PR → merge
```

Jules handles the mechanical work: new events, asset updates, bug fixes from upstream. The patches the fork needs are small and predictable (config paths, deploy.yaml overrides). Jules can learn these patterns and apply them automatically.

### 1b. Behavioral Catalog

Write `docs/plans/behavioral_catalog.md` in the new repo. This is the bridge document that makes standalone tool development possible.

For each ALAS workflow domain, document:
- **Preconditions**: What screen/state must be true before starting
- **Steps**: Sequence of screens, taps, waits, decisions — described as what the user sees, not ALAS function names
- **Decision rules**: Thresholds, timers, config flags that drive behavior
- **Asset references**: Which images/templates, what they look like, where on screen
- **Postconditions**: Expected state when done
- **Error cases**: What can go wrong, how to handle it

Priority domains (in order):
1. **Login** — already partially spec'd in `phase_0_login_tool_spec.md`
2. **Commission** — collect and submit
3. **Daily rewards** — mail, missions
4. **Combat** — start, auto, exit patterns
5. **Tactical training** — classroom management

### ADB Connection Transition

Currently the MCP server piggybacks on ALAS's running process — it uses ALAS's already-established ADB connection through Python objects. When we separate into two repos, the standalone MCP server needs its own ADB connection. ALAS and the agent cannot share a connection to the same emulator simultaneously.

**Transition plan**: During Phase 1-2, development and testing happen when ALAS is not running (or ALAS is stopped first). By Phase 3 cutover, the agent owns the ADB connection exclusively and ALAS is no longer connected.

**Emulator migration**: LDPlayer will be the primary emulator — no UAC prompts after initial install, enabling automated startup. MEmu remains as fallback.

### Phase 1 Success Criteria

- [ ] Two separate repos exist and are operational
- [ ] Jules is configured and successfully syncs at least one upstream update
- [ ] Behavioral catalog covers login and commission workflows
- [ ] MCP server boots in the new repo with ADB primitives working (screenshot, tap, swipe)

---

## Phase 2: Standalone Tool Development

### Goal

Build clean, deterministic tools in the new repo that replicate ALAS's game automation — guided by the behavioral catalog, with zero ALAS imports.

### Tool Stack

- **ADB layer**: Screenshot, tap, swipe (already working, just needs to move to new repo). The standalone MCP server owns the ADB connection exclusively — ALAS and the agent cannot share a connection to the same emulator simultaneously.
- **Screen understanding**: Deterministic first — OCR (PaddleOCR or similar), template matching where assets are stable, pixel/color checks for simple state detection. These are fast, cheap tools that handle 90%+ of operations.
- **Persistent screen state** (MCP resource): OCR reads known screen values (coin balance, gem balance, oil balance, button states, etc.) based on current screen and known positions. Maintained as a continuously-updated resource the agent can query for situational awareness.
- **Workflow tools**: Login, commission, daily, combat — each built to the behavioral catalog spec. These are sophisticated tools that return structured summaries of what they did.
- **State detection**: Know what screen we're on, what buttons are visible, what text is present

### Tool Contract (Required)

All tools return:
- `success: bool`
- `data: object | null` (diagnostic info on failure)
- `error: str | null` (non-null on failure)
- `observed_state: str | null`
- `expected_state: str`

### Two-Tier Operation

```
Agent calls deterministic MCP tool
        │
        ├── Success → agent moves to next step
        │
        └── Failure / unexpected state
                │
                ▼
        Agent uses its own vision (screenshot analysis) to understand
                │
                ├── Can recover → calls more tools to fix
                └── Can't recover → logs with full context for human review
```

**Deterministic tools are the workhorse.** They return structured summaries; the orchestrator reads those summaries and decides next steps without needing to look at the screen. An unknown or unexpected screen *is* a recovery state — the agent uses its own VLM to understand what happened. This is the recovery layer that ALAS never had.

### Phase 2 Success Criteria

- [ ] At least one complete workflow (login → main lobby) works end-to-end with standalone tools
- [ ] MCP server in new repo exposes gameplay tools alongside ADB primitives
- [ ] Agent (Claude Code or Gemini CLI) can drive a workflow interactively via MCP
- [ ] No imports from ALAS codebase

---

## Phase 3: Autonomous Operation

### Goal

An LLM agent runs the bot autonomously via MCP tools, with the same interface used during development.

### Why No Custom Orchestrator (Yet)

The coding agent (Claude Code, Gemini CLI) already *is* an orchestrator — it calls tools, reads results, decides next steps, recovers from errors. A custom orchestrator (retry policies, scheduling, durable state via LangGraph) is optional hardening for later, not a prerequisite. The agent can run the bot as soon as the tools are good enough.

### What "Production" Looks Like

1. Configure an LLM agent (Gemini) with access to the MCP server
2. Give it a task: "run daily commissions, collect rewards, do 3 combat sorties"
3. Agent calls deterministic tools to execute each step
4. When something goes wrong, agent looks at a screenshot and recovers
5. Agent logs everything — what it did, what it saw, what went wrong

This is the same workflow as development, just unattended.

### Phase 3 Success Criteria

- [ ] Agent completes a full daily routine (login, commissions, daily, combat) without human intervention
- [ ] Recovery from at least one common failure mode (unexpected popup, connection error)
- [ ] Run log produced that human can review after the fact

---

## Development Constraints

1. **ALAS must keep working.** The owner uses it for daily gameplay. The new system is built alongside, not on top of, ALAS.
2. **Extract, don't wrap.** ALAS is a reference for understanding behavior, not a runtime dependency. No `from module.*` in the new repo.
3. **Deterministic tools first.** Screen understanding defaults to OCR/template matching/pixel checks — fast and cheap. Agent VLM is recovery-only.
4. **Same harness for dev and prod.** MCP tools are the interface for both interactive development and autonomous operation. Don't build something then repackage it.

---

## Future Enhancements

- [ ] **Tactical Training Scheduling**: Schedule different ships for training (rotate through classroom rather than always training whoever is assigned).
- [ ] **LangGraph hardening**: Durable execution, sub-graphs, retry policies — only when needed for reliability.
- [ ] **LDPlayer migration**: Switch from MEmu to LDPlayer as primary emulator (no UAC prompts after install). Update ADB serial, config, and launcher scripts.

---

## Non-Goals (Out of Scope)

- **GUI/Dashboard**: We don't build or maintain a web UI.
- **Python 3.9 compatibility**: The new repo is Python 3.10+ only.
- **Upstream contributions**: We maintain a downstream fork; we don't PR back to Zuosizhu.
- **Multi-game support**: Azur Lane only.
