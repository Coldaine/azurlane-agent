# CLAUDE.md

> You are working on **azurlane-agent** — an LLM-augmented Azur Lane automation system.
> This is the clean repo. All new development happens here. No ALAS imports.

## The North Star (Sacrosanct)

**[docs/NORTH_STAR.md](./docs/NORTH_STAR.md) is the immutable vision document.** All decisions must align with it:

- **Replace ALAS entirely** with a clean, LLM-augmented system built from scratch
- **Deterministic tools first** — OCR, template matching, programmatic navigation handle 90%+ of operations
- **LLM for recovery only** — agent uses VLM (screenshot analysis) when deterministic tools fail
- **Same harness for dev and prod** — MCP tools are the interface for both interactive development and autonomous operation
- **Extract, don't wrap** — ALAS is a reference for understanding behavior, not a runtime dependency

If a proposed change conflicts with NORTH_STAR.md, the change is wrong.

## Repository Layout

```
azurlane-agent/
├── CLAUDE.md              # you are here
├── mcp_server/            # MCP tool definitions (FastMCP)
│   ├── adb_tools.py       # screenshot, tap, swipe (pure ADB)
│   ├── screen_tools.py    # OCR, template matching, state detection
│   └── workflow_tools.py  # login, commission, daily, combat
├── tools/                 # standalone tool implementations
├── docs/
│   ├── NORTH_STAR.md      # sacrosanct vision
│   ├── ROADMAP.md         # phased plan
│   ├── ARCHITECTURE.md    # system diagrams
│   ├── plans/             # implementation specs, migration plan
│   └── reference/         # ALAS workflow analysis (read-only reference)
├── assets/                # game templates, reference images
├── tests/
└── pyproject.toml         # Python 3.10+
```

## The Rules

1. **No ALAS imports.** No `from module.*`. No `import module`. Tools are standalone.
2. **Python 3.10+.** Clean dependency tree. No legacy constraints.
3. **Tool contract.** All tools return this envelope:
   ```python
   {
       "success": bool,
       "data": object | None,
       "error": str | None,
       "observed_state": str | None,
       "expected_state": str
   }
   ```
4. **Deterministic first.** OCR, template matching, pixel checks for normal operations. LLM vision is recovery-only.
5. **ADB is the only interface.** Screenshot, tap, swipe over TCP. No ALAS process, no shared memory, no IPC.

## Current Phase

**Phase 1: Scaffold + Standalone ADB Tools**

The MCP server needs standalone ADB tools (screenshot, tap, swipe) that work without ALAS. These are adapted from the working ALAS-wrapping versions — the ADB layer was already mostly standalone.

Next: behavioral catalog entries, then standalone screen tools (OCR, template matching).

## Sibling Repo

**[Coldaine/ALAS](https://github.com/Coldaine/ALAS)** is the wrapped ALAS fork for daily gameplay. ALAS source lives there. Read it to understand workflows, thresholds, and decision rules. Don't import from it.

## MCP Server

### Launch
```bash
uv run mcp_server/server.py
```

### Environment
- Emulator running with ADB on `127.0.0.1:21503` (MEmu) or LDPlayer equivalent
- `lz4` package installed (screenshot decompression)

### Tool Categories

| Category | Purpose | Tools |
|----------|---------|-------|
| ADB | Device interaction | `adb.screenshot`, `adb.tap`, `adb.swipe` |
| Screen | Deterministic vision | `screen.ocr`, `screen.match_template`, `screen.detect_page` |
| Workflow | Game automation | `workflow.login`, `workflow.commission`, etc. |

## Development Workflow

### Branch and PR Process

```bash
git checkout -b feature/descriptive-name
# make changes, commit incrementally
git push -u origin feature/descriptive-name
```

**Commit prefixes:** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

### Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_adb_tools.py
```

## Approach: Extract, Don't Wrap

The workflow for adding a new tool:

1. **Read ALAS source** in the sibling repo to understand the behavior
2. **Document it** in `docs/plans/` as an implementation-agnostic spec
3. **Build the standalone tool** from the spec — no ALAS imports
4. **Test against live emulator** — same ADB connection the production agent will use

ALAS tells you *what* to do. The behavioral catalog captures *what* in a clean format. Standalone tools implement *what* without *how* ALAS did it.
