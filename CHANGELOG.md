# Changelog

All notable changes to azurlane-agent.

## [Unreleased]

### Added
- Initial repo scaffold: directory structure, pyproject.toml, .gitignore, .mcp.json
- CLAUDE.md with repo conventions, rules, and development workflow
- Vision docs (NORTH_STAR.md, ROADMAP.md, ARCHITECTURE.md) in `docs/`
- Implementation specs and migration plan in `docs/plans/`
- ALAS workflow reference docs in `docs/reference/` (read-only analysis)
- Standalone ADB MCP server (`mcp_server/server.py`) with three tools:
  - `adb_screenshot` -- capture device screen as FastMCP Image (PNG)
  - `adb_tap` -- tap coordinate via adbutils
  - `adb_swipe` -- swipe between coordinates with configurable duration
- `DeviceConnection` class for reusable ADB device handle (connect-once pattern)
- Log parser tool (`mcp_server/log_parser.py`) -- zero-dependency CLI for ALAS log analysis
- Unit tests (`tests/test_adb_tools.py`) covering all three ADB tools and DeviceConnection,
  fully mocked (no real device needed)
- Placeholder directories: `tools/`, `assets/`

### Changed
- .mcp.json updated to point to `mcp_server/server.py` (was referencing old `alas_mcp_server.py`)
- CLAUDE.md updated to match actual repo layout, tool names, and launch commands
