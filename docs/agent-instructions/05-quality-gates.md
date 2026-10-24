# 05 — Quality gates

## Required before saying done

For runtime refactoring (including the command-first migration):

- Reuse the existing environment via `uv run --locked --no-sync`; no dependency installation/update without separate permission.
- Establish pre-import isolation according to the [testing instruction](../../.github/instructions/testing.instructions.md).
- Offline tests passed: `uv run --locked --no-sync pytest tests/ -m "not e2e" -q`.
- CI retains its Linux/Windows matrix and original triggers/provisioning. Its post-install isolation step must establish winning owned selectors and plugin/offline policy before product imports/collection/children; four smokes use module invocations. Qualify changed procedure locally, not only YAML shape. Local Windows evidence is not Linux/Python3.12/remote CI execution.
- Changed Python files pass at least narrow lint for syntax/import errors:
  `uv run --locked --no-sync ruff check --select E,F,I <changed Python files>`.
  For final S6, derive the nonempty cumulative authored set from the original PLAN
  code_ref to the final worktree, not only the CI/Markdown delta. Exclude only the
  verified unchanged imported PFK payload; record exact paths and provenance.
- If GUI behavior is affected, run a GUI smoke.
- If MCP behavior is affected, run an MCP tool-discovery smoke.
- Shared API/bootstrap changes also require real offline application/adapter behavior,
  not only help/discovery. Inspect actual state/results and relevant failure/cleanup.
- File-effect changes require useful correctly-tokened real API/repository/file/readback
  proofs, no-effect preview/refusal, exact scope/preservation, identity staleness,
  partial move and history-save failure, plus a usable next operation. A success flag
  without physical recoverable bytes is insufficient. Native Trash capability,
  synthetic OS-edge moves and actual native move/restore must be reported separately;
  an unqualified native restore remains NOT_RUN per PLAN S4, never permanent fallback.
- Run and baseline-attribute `uv run --locked --no-sync mypy src/ --ignore-missing-imports`;
  full-project legacy findings remain visible, new owned type/lint failures require repair.
- On a bounded repair, preserve the previous verdict/RED and verify unchanged source/assertion/environment applicability before reusing passed checks. Run the named delta regression and affected sibling gates, not full suite/type/foundation replays without new impact. A child smoke exit0 cannot replace competing-store preservation/no-lock and real cleanup evidence.
- For adapter/lifetime changes verify actual native CLI acceptance/terminal/exits,
  real SDK stdio tools and EOF, managed loopback HTTP effects/stop/join/port reuse,
  actual offscreen Qt actions/modal/settings, and partial setup/close failures.
  Borrowed runtime and early/late caller handlers must remain the same usable
  objects; prove actual after-context writes and owned release, not reconstruction.
  Disclosure of substituted network/Trash edges and scoped privacy limits remains required.
- The assigned independent Pi Reviewer evaluates the frozen coherent candidate;
  author tests are not independent acceptance. S1–S6 and final command-first
  migration are independently accepted in the recorded offline boundary (S5-R1
  closed). Actual CI preparation/commands were qualified on local Windows/Python3.14.2,
  not hosted/Linux/Python3.12/pwsh7. Mypy34/full configured lint57 remain visible
  inherited debt, not PASS; authored65 E/F/I is a separate gate. Future changes
  require their own affected qualification. GUI redesign, live YouTube/native
  Trash/platform/package qualification are not implied by completion.

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
