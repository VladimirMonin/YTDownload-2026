# 04 — CLI, MCP and GUI

S1–S5 are independently accepted within the recorded offline boundaries, including
S5-R1 (preserve caller-owned logging handlers). Final qualification/CI alignment
remains S6. [Verification](../command-first/VERIFICATION.md) owns current facts;
[CONTRACT](../command-first/CONTRACT.md) owns semantics. No GUI redesign, live
YouTube permission, native Trash restore or platform/package certification is implied.

## Existing environment and four smokes

From the project root, establish owned storage/home/temp/cache/log/output roots
**before** collection/import per [testing](../../.github/instructions/testing.instructions.md).
The scripts allocate a narrower owned subtree, including winning YTDL_DATA_DIR;
YTDL_SMOKE_ROOT may name an owned parent. They preserve synthetic files, restore
environment and join/close only their resources. A smoke is not a useful operation.

```bash
uv run --locked --no-sync python -m scripts.smoke_cli_help
uv run --locked --no-sync python -m scripts.smoke_mcp
uv run --locked --no-sync python -m scripts.smoke_mcp_stdio
uv run --locked --no-sync python -m scripts.smoke_gui
```

Help covers five parser/help cases. MCP smoke registers/discovers ten tools without
binding HTTP. Stdio smoke runs a real SDK client/current-interpreter child with
`-m scripts.smoke_mcp_stdio --serve`, complete isolation, keep_alive=False and
bounded discovery/transport cleanup; its injected services are finally joined.
It is discovery parity, not standalone tool-effect or active-job qualification.
GUI smoke creates/shows/processes/closes a real offscreen window; it is not a
visual/manual workflow or the desktop HTTP lifetime test. Qt offscreen is selected
by the script; never leave a long-running app/server behind as a smoke.

## One owner, distinct process modes

`main.initialize_app()` delegates to create_runtime and preserves service keys;
application_api/command_api alias the same facade. Separate processes do not share
a live queue. One canonical data root has one writable lease; a second writer
gets OWNER_BUSY. `--data-dir` selects this process's profile, not attach to GUI.
Readonly history queries/preview read last-saved snapshots without lease,
executor, recovery or writes, including an absent profile. Corrupt JSON is not
silently treated as empty.

```bash
uv run --locked --no-sync python -m src.interfaces.cli --help
uv run --locked --no-sync python -m src.interfaces.cli --json --data-dir <owned-data-root> history list
uv run --locked --no-sync python -m src.interfaces.cli server http --host 127.0.0.1 --port 8765
uv run --locked --no-sync python -m src.interfaces.cli server stdio
```

Standalone queue add flushes one acceptance result before waiting for actual
terminal/persistence. Exit0 means done+persisted; failed/cancelled/unsaved means
exit1 and a safe stderr error, never a second stdout JSON. Usage remains exit2.
Borrowed `cli.main(..., services=...)` returns acceptance without waiting or
closing the caller runtime. Standalone queue cancel returns OWNER_REQUIRED before
creating an empty owner/profile. Cancellation intent is not terminal quiescence.

Canonical stdio uses the command above. Compatibility wrapper:
`uv run --locked --no-sync python mcp_stdio_server.py`. Legacy HTTP module:
`uv run --locked --no-sync python -m src.infrastructure.mcp.server --host 127.0.0.1 --port 8765`.
The earlier spelling `uv run python -m src.interfaces.cli server stdio` refers to
the same entry, not an existing-environment install/sync recipe.

## Canonical MCP factory and ten tools

`src.infrastructure.mcp.server.create_mcp_server` registers one existing API;
CLI bootstrap delegates/reexports it. It never initializes another application.
Contradictory facade aliases refuse. The manifest in
`src/infrastructure/mcp/manifest.py` is the only tool-name/count source;
`scripts/mcp_expected_tools.py` and doc regressions consume it.

Expected tools currently include 10 user-facing tools:

- `list_downloads`
- `get_download`
- `search_downloads`
- `search_with_description`
- `get_file_paths`
- `get_transcript`
- `read_description`
- `add_download`
- `cancel_download`
- `delete_download`

Actual offline SDK stdio checks go beyond discovery: useful get/list/description,
missing-id error, token preview/refusal/keep-files apply, durable reopen and native
child exit. In-process tools prove genuine shared-runtime add/cancel and structured
partial deletion. Active owned stdio EOF triggers cooperative shutdown and terminal
save; HTTP request/client disconnect does not cancel accepted Jobs.

## GUI and managed HTTP lifetime

MainWindow and its API-backed managers borrow the supplied runtime. The constructor
attaches EventBus→Qt bridges and restores list_tasks before embedded HTTP admission;
IDs deduplicate existing cards. History queries/delete/settings/theme use the API,
not repository fallback or mutations of a borrowed settings object. Existing
controls/dialog/layout/theme remain unchanged; filter state survives refresh.

HTTPServerHandle owns only its actual socket, uvicorn.Server and non-daemon thread.
Use close/join and check the result; repeated close is safe, a borrowed runtime
remains usable. Foreign bind failures do not stop foreign listeners. Desktop
entry owns its runtime: close admission, stop/join transport, detach window bridges,
then final cooperative runtime join/lease release. Partial startup/open/close
failure cannot be reported as clean success. Blocking external work may delay
shutdown; no hard stop deadline or thread kill is promised.

Logging contexts own only acquired handlers, not early/late caller objects.
Partial file-open and cleanup failure, actual next writes and usable next owner
are required evidence; see [logging](../../.github/instructions/logging.instructions.md).

## Token-bound deletion in all adapters

Preview has no effect. CLI/MCP apply needs explicit consent, the same ID/mode and
the returned token. Boolean/token does not authenticate a person. Example commands
are a manual workflow, never permission for an agent to alter a user's files:

```bash
uv run --locked --no-sync python -m src.interfaces.cli --json history delete 42 --keep-files --preview
uv run --locked --no-sync python -m src.interfaces.cli --json history delete 42 --keep-files --confirm --plan-token TOKEN_FROM_PREVIEW
```

MCP first calls delete_download(id, delete_files, confirm=False), then only after
consent repeats the ID/mode with confirm=True and plan_token. GUI prepares both
existing checkbox modes before opening the existing modal; No preserves bytes,
Yes forwards the selected plan and changed state returns STALE_PLAN. Never
manufacture a fresh token inside apply or fall back to repository.delete.

Only recorded media/sidecars may move to recoverable Trash; directories/unlisted
files remain. Keep-files removes only history and still requires a matching plan.
Legacy folder-only attribution, unsafe/shared/linked/live targets safely refuse.
Partial/unknown moves or history-save failure retain structured counts/state and
recovery=repreview; obtain fresh consent rather than retrying an old token.
Installed lazy QtCore capability and synthetic recoverable moves do **not** prove
native Trash move/restore. Never enumerate a user's bin or use permanent fallback.

## Evidence limits and network permission

Connected checks use real parser/API/coordinator/repositories/files/SDK/Qt, replacing
only external download/Trash edges with controlled owned fixtures. They verify
native CLI outcomes, actual stdio, loopback HTTP effects/disconnect/quiescence/
port reuse, real Qt actions/modal/settings and partial startup/cleanup failures.
Nonempty safe file/stderr sinks and clean result/protocol stdout are separate
from handler ownership; neither certifies whole legacy/native Qt diagnostics.

Live URL/download/sidecar/codec validation needs explicit permission and a concrete
URL under [download testing](03-download-testing.md). Linux runtime/remote CI,
packaging/EXE/manual visual and native Trash restore remain NOT_RUN. HTTP defaults
to 127.0.0.1; single-user unauthenticated local operation is not a security claim
for an untrusted network. Never leave owned servers/threads after a check.
