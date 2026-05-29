# 05 — Quality gates

## Required before saying done

For setup or Linux compatibility work:

- `uv sync` completed or the failure is explained.
- Offline tests passed: `uv run pytest tests/ -m "not e2e" -q`.
- Changed Python files pass at least narrow lint for syntax/import errors:
  `uv run ruff check --select E,F,I <changed files>`.
- If GUI behavior is affected, run a GUI smoke.
- If MCP behavior is affected, run an MCP tool-discovery smoke.

## Known baseline caveat

The full project currently has existing `ruff` and `mypy` findings. Do not present the full lint/type baseline as newly introduced without checking changed-file scope.

## Git policy

- Inspect `git status --short` before final report.
- Inspect diffs for `.gitignore` and `uv.lock` explicitly when they are modified.
- Do not commit or push unless explicitly asked.
- Separate generated artifacts from intentional source changes.
- Do not include dependency lockfile updates unless dependency resolution/update is part of the task or the user approves it.
- Do not include broad `.gitignore` rewrites unless the ignore policy change is part of the task.

## Evidence format

In final reports, separate:

- changed;
- verified;
- not verified;
- risks or next step.
