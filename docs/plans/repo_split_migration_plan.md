# Repo Split Migration Plan

Concrete steps to split the ALAS monorepo into two repos.

## Current State

One monorepo (`Coldaine/ALAS`) with everything:

```
ALAS/
├── upstream_alas/           # submodule → Zuosizhu/Alas-with-Dashboard
├── alas_wrapped/            # modified ALAS (Python 3.9, the running bot)
├── agent_orchestrator/      # MCP server, tools (Python 3.10+)
├── docs/                    # vision, roadmap, architecture, plans, dev guides, archive
├── CLAUDE.md                # agent instructions
├── AGENTS.md                # index file (redundant)
├── GEMINI.md                # production orchestrator instructions (premature)
├── CHANGELOG.md
├── FORK_CHANGES.md          # tracks Dashboard fork changes vs upstream
└── todo.md
```

## Target State

Two repos:

### Repo 1: `Coldaine/ALAS` (this repo — becomes alas-wrapped)

The daily-gameplay fork. Jules auto-syncs upstream. Minimal agent docs.

```
ALAS/
├── upstream_alas/           # submodule → Zuosizhu (unchanged)
├── alas_wrapped/            # the running bot (unchanged)
├── config/                  # deploy.yaml etc.
├── CLAUDE.md                # minimal — just "this is the wrapped ALAS fork" context
├── CHANGELOG.md             # history stays here
├── FORK_CHANGES.md          # stays — tracks Dashboard patches
├── alas.bat                 # launcher stays
└── .mcp.json                # removed (MCP server moves to new repo)
```

What gets **removed** from this repo:
- `agent_orchestrator/` → moves to new repo
- `docs/` → vision/roadmap/architecture/plans move to new repo; archive can be deleted
- `AGENTS.md` → deleted
- `GEMINI.md` → deleted
- `docs/DOC_GUIDE.md` → deleted
- `todo.md` → deleted

### Repo 2: `Coldaine/azurlane-agent` (new, clean)

All new development. MCP server, standalone tools, behavioral catalog.

```
azurlane-agent/
├── CLAUDE.md                # authoritative agent instructions (adapted)
├── CHANGELOG.md             # starts fresh
├── mcp_server/              # renamed from agent_orchestrator
│   ├── adb_tools.py
│   ├── screen_tools.py
│   └── workflow_tools.py
├── tools/                   # standalone tool implementations
├── docs/
│   ├── NORTH_STAR.md        # carried over (sacrosanct)
│   ├── ROADMAP.md           # carried over + updated
│   ├── ARCHITECTURE.md      # carried over + updated
│   └── plans/               # behavioral catalog, tool specs
├── assets/                  # game assets for template matching
├── tests/
└── pyproject.toml           # Python 3.10+, clean deps
```

---

## Step-by-Step Migration

### Phase A: Doc Cleanup (this repo, do first)

**Goal**: CLAUDE.md is the single authoritative instruction file. Remove redundant agent docs.

1. **Delete `AGENTS.md`** — it's just an index that points to CLAUDE.md and GEMINI.md. Unnecessary indirection.

2. **Delete `GEMINI.md`** — production orchestrator doesn't exist yet. When it does, it'll live in the new repo. Premature.

3. **Delete `docs/DOC_GUIDE.md`** — its structure is superseded by the repo split. The new repo will have its own simpler doc structure.

4. **Delete `todo.md`** — stale.

5. **Update CLAUDE.md** — strip it down to just what's needed for *this* repo post-split (the wrapped ALAS fork). Remove references to azurlane-agent, MCP server development, behavioral catalog, tool extraction — all that moves to the new repo's CLAUDE.md.

6. **Commit**: `docs: consolidate agent instructions into CLAUDE.md, remove redundant docs`

### Phase B: Create the New Repo

**Goal**: `Coldaine/azurlane-agent` exists on GitHub with the right structure.

1. **Create repo on GitHub**: `gh repo create Coldaine/azurlane-agent --public --clone`

2. **Initialize structure**:
   ```bash
   cd azurlane-agent
   mkdir -p mcp_server tools docs/plans tests assets
   ```

3. **Copy vision docs from this repo**:
   ```bash
   cp ../ALAS/docs/NORTH_STAR.md docs/
   cp ../ALAS/docs/ROADMAP.md docs/
   cp ../ALAS/docs/ARCHITECTURE.md docs/
   ```

4. **Copy agent_orchestrator code** (will be refactored):
   ```bash
   cp -r ../ALAS/agent_orchestrator/* mcp_server/
   ```
   Then remove ALAS-wrapping code, keep ADB primitives.

5. **Copy relevant plans**:
   ```bash
   cp ../ALAS/docs/plans/phase_0_login_tool_spec.md docs/plans/
   ```

6. **Copy useful reference docs** (optional, for extraction work):
   ```bash
   cp -r ../ALAS/docs/alas_tooling_workflows/ docs/reference/
   cp ../ALAS/docs/ALAS_CONFIG_REFERENCE.md docs/reference/
   ```

7. **Write new CLAUDE.md** for the agent repo — this is the authoritative doc for all new development. Contains:
   - North Star summary (brief, links to docs/NORTH_STAR.md)
   - Current phase and what to work on
   - Tool contract (the envelope shape)
   - MCP server setup/launch
   - Testing commands
   - "Extract, don't wrap" principle
   - No ALAS imports rule

8. **Write `pyproject.toml`** — Python 3.10+, deps: `fastmcp`, `adbutils`, `opencv-python`, `Pillow`, `lz4`. Dev deps: `pytest`.

9. **Initial commit and push**.

### Phase C: Clean Up This Repo

**Goal**: This repo is just the wrapped ALAS fork. No agent development artifacts.

1. **Remove `agent_orchestrator/`** — it's in the new repo now.
   ```bash
   git rm -r agent_orchestrator/
   ```

2. **Remove docs that moved** — vision, plans, architecture:
   ```bash
   git rm -r docs/  # everything moved or archived
   ```
   Exception: if any docs are this-repo-specific (like `docs/dev/recovery_workflow.md` for upstream sync recovery), keep those.

3. **Remove `.mcp.json`** — MCP server is in the new repo.

4. **Slim down CLAUDE.md** to just:
   - "This is the ALAS wrapped fork for daily gameplay"
   - Setup instructions (venv, config, launcher)
   - Jules sync info
   - FORK_CHANGES.md reference
   - "All new tool development happens in azurlane-agent"

5. **Commit**: `chore: remove agent code and docs (moved to azurlane-agent)`

6. **Push**.

### Phase D: Wire Up Cross-Repo References

1. **New repo's CLAUDE.md** should reference this repo for:
   - ALAS source reading (behavioral catalog work)
   - Asset paths (templates live in alas_wrapped/)
   - Config reference

2. **Optionally add this repo as a submodule** in the new repo:
   ```bash
   cd azurlane-agent
   git submodule add https://github.com/Coldaine/ALAS.git alas-reference
   ```
   This gives the new repo read access to ALAS source for extraction work. Remove the submodule once extraction is complete.

3. **Update new repo's MCP server** to connect to ADB directly (not through ALAS process). The ADB tools (screenshot, tap, swipe) are already mostly standalone — they just need the ALAS import chain removed.

### Phase E: Configure Jules (Deferred)

Jules setup for auto-syncing upstream into this repo. This is a separate task — the repo split doesn't block on it.

---

## What Stays Where (Quick Reference)

| Item | This repo (ALAS) | New repo (azurlane-agent) |
|------|-------------------|---------------------------|
| `upstream_alas/` submodule | YES | NO |
| `alas_wrapped/` code | YES | NO (read-only reference via submodule) |
| `agent_orchestrator/` | NO (removed) | YES (as `mcp_server/`) |
| `docs/NORTH_STAR.md` | NO | YES |
| `docs/ROADMAP.md` | NO | YES |
| `docs/ARCHITECTURE.md` | NO | YES |
| `docs/plans/` | NO | YES |
| `docs/archive/` | NO (delete) | NO (dead weight) |
| `CLAUDE.md` | YES (minimal) | YES (authoritative) |
| `CHANGELOG.md` | YES (history) | YES (starts fresh) |
| `FORK_CHANGES.md` | YES | NO |
| `GEMINI.md` | NO (delete) | NO (premature) |
| `AGENTS.md` | NO (delete) | NO (premature) |
| `config/` | YES | NO |
| `alas.bat` | YES | NO |
| `.mcp.json` | NO (remove) | YES (new) |
| `pyproject.toml` | NO | YES |
| Standalone tools | NO | YES |
| Behavioral catalog | NO | YES |

## Order of Operations

1. **Phase A first** (doc cleanup) — low risk, clears the noise
2. **Phase B next** (create new repo) — can start building there immediately
3. **Phase C after B** (clean this repo) — only after new repo has everything it needs
4. **Phase D as needed** (cross-repo wiring)
5. **Phase E deferred** (Jules)

## Decision: Do We Rename This Repo?

Option 1: **Keep as `Coldaine/ALAS`** — no URL breakage, GitHub redirects, etc.
Option 2: **Rename to `Coldaine/alas-wrapped`** — clearer intent, matches docs.

Recommendation: Keep as `ALAS` for now. Rename later if it matters. The important thing is the new repo name (`azurlane-agent`) is clear.

## What Can Be Done Right Now (This Session)

- Phase A (doc cleanup) — delete redundant files, update CLAUDE.md
- Draft the new repo's CLAUDE.md content
- Draft pyproject.toml for the new repo

Creating the actual GitHub repo (Phase B) requires `gh` auth and is a manual step.
