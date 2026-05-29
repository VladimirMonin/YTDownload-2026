# AGENTS.md — YTDownload 2026

This is the required entry point for AI agents working in this repository.

## Read first

Before making changes, read these project instructions:

1. `docs/agent-instructions/01-project-overview.md`
2. `docs/agent-instructions/02-environment-and-dependencies.md`
3. `docs/agent-instructions/03-download-testing.md`
4. `docs/agent-instructions/04-mcp-and-gui.md`
5. `docs/agent-instructions/05-quality-gates.md`

## Hard rules

- Do not commit, push, release, or run destructive git commands without explicit user permission.
- Do not run real YouTube downloads or network E2E tests unless the user explicitly allows it.
- Do not print secrets, local tokens, or full user config contents.
- Prefer `uv` for environment and commands.
- Keep Linux and Windows behavior separate when working with FFmpeg paths.
- Do not download vendor binaries, install system packages, or run long background servers without user approval.
- Treat `uv.lock` and `.gitignore` changes as intentional only after inspecting the diff; do not bundle accidental dependency or ignore-rule churn into an unrelated commit.
- After touching runtime behavior, run the narrow relevant tests and report what was actually verified.

## Common commands

```bash
uv sync
uv run pytest tests/ -m "not e2e" -q
uv run ruff check --select E,F,I <changed files>
QT_QPA_PLATFORM=offscreen uv run python <gui smoke script>
```

See `docs/agent-instructions/` for the detailed rules.
