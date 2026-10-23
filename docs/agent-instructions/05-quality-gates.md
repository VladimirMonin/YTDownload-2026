# 05 — Quality gates

## Required before saying done

For runtime refactoring (including the command-first migration):

- Reuse the existing environment via `uv run --locked --no-sync`; no dependency installation/update without separate permission.
- Establish pre-import isolation according to the [testing instruction](../../.github/instructions/testing.instructions.md).
- Offline tests passed: `uv run --locked --no-sync pytest tests/ -m "not e2e" -q`.
- Cross-platform CI should run the offline suite on Linux and Windows when workflow files are present.
- Changed Python files pass at least narrow lint for syntax/import errors:
  `uv run --locked --no-sync ruff check --select E,F,I <changed Python files>`.
- If GUI behavior is affected, run a GUI smoke.
- If MCP behavior is affected, run an MCP tool-discovery smoke.
- Shared API/bootstrap changes also require real offline application/adapter behavior,
  not only help/discovery. Inspect actual state/results and relevant failure/cleanup.
- Run and baseline-attribute `uv run --locked --no-sync mypy src/ --ignore-missing-imports`;
  full-project legacy findings remain visible, new owned type/lint failures require repair.
- The assigned independent Pi Reviewer evaluates the frozen coherent candidate;
  author tests are not independent acceptance. GUI redesign and live YouTube E2E are out of scope.

## Known baseline caveat

The full project currently has existing `ruff` and `mypy` findings. Do not present the full lint/type baseline as newly introduced without checking changed-file scope.

## Git policy

- Inspect `git status --short` before final report.
- Inspect diffs for `.gitignore` and `uv.lock` explicitly when they are modified.
- Coder does not stage/commit/push. The same independent Reviewer, after ACCEPTED, finishes affected docs/instructions and selectively commits/pushes only the accepted slice to `refactor/command-first` under the explicit project grant in [agent-team](../agent-team.md). No additional approval per accepted slice; no main/force/tags/release or destructive Git grant.
- Inspect exact index paths/content/parent before commit, and outgoing history/destination/policies before push. Read back the actual remote ref; report local acceptance, commits, publication and CI separately. No blanket add, foreign artifacts or machine-local evidence.
- Separate generated artifacts from intentional source changes.
- Do not include dependency lockfile updates unless dependency resolution/update is part of the task or the user approves it.
- Do not include broad `.gitignore` rewrites unless the ignore policy change is part of the task.

## Evidence format

In final reports, separate:

- changed;
- verified;
- not verified;
- risks or next step.
