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
- For first-party type/lint hardening, also run configured Ruff without replacing
  its E/F/I/UP selection: `uv run --locked --no-sync ruff check --config pyproject.toml <first-party-python-files>`.
  Validate the complete finite metadata inventory before reading/copying bodies:
  tracked first-party `.py` in root/build/src/scripts/tests plus explicit new files.
  Pass literal separate argv paths; include `build/build.py`, never exclude
  application/tests to get green. Only the verified unchanged imported PFK checker
  is outside this first-party gate. Its own lint/recursive whole-root result is
  separately NOT_RUN unless actually checked. Q1 bound105 tracked +1 new =106;
  future slices derive their own inventory, not a permanently fixed count.
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
  not hosted/Linux/Python3.12/pwsh7. At S6, mypy34/full configured lint57 were
  inherited debt, not PASS; authored65 E/F/I was a separate gate. Subsequent Q1
  independently closed those causes plus the newly included build I001: mypy0/68,
  configured1060, changed31 E/F/I0 and full291/7 e2e deselected/0 skips. Historical
  RED/debt receipts remain intact. These are frozen-slice facts, not a green claim
  for unaccepted parallel Q2 work. Future changes require their own affected
  qualification. GUI redesign/build/visual, live/native Trash/platform/package
  qualification are not implied by Q1.

## Baseline and scope caveat

Do not assume that historical findings remain current, or that one narrow green
command proves whole-root green. Q1's exact first-party106 configured Ruff and68-file
mypy are independently exit0; original34/57 (plus build1 in the Q1 full inventory)
remain historical evidence, not hidden failures or a retroactive PASS. Imported
PFK checker/recursive whole-root lint remains NOT_RUN. See the current
[verification](../command-first/VERIFICATION.md) for frozen identity and limits.
Prose-only completion reuses accepted product results and checks only affected
final document bytes/links/literal consumers; no new acceptance loop for the same slice.

## Git policy

- Inspect `git status --short` before final report.
- Inspect diffs for `.gitignore` and `uv.lock` explicitly when they are modified.
- Coder does not stage/commit/push. The same independent Reviewer, after ACCEPTED, finishes affected docs/instructions and selectively commits/pushes only the accepted slice to `refactor/command-first` under the explicit project grant in [agent-team](../agent-team.md). No additional approval per accepted slice; no main/force/tags/release or destructive Git grant.
- Technical ACCEPTED and delivery are separate phases of the same Reviewer session. Once technical acceptance and conflicting-resource release are confirmed, Coder may start the next authorized nonconflicting medium–large slice while Reviewer finishes the previous documentation/commit/push. Do not impose a publication wait without a real dependency; consult Oracle only for actual unresolved problems.
- Keep the accepted source bytes frozen until commit and the index exclusively owned by Reviewer. Explicitly separate next-slice and closing-document paths; do not stage unaccepted successor work or demand whole-worktree cleanliness merely because it exists. Serialize only actual overlapping writes.
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
