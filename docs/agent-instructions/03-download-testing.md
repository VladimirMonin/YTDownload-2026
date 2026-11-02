# 03 — Download testing

## Offline checks

Follow the canonical [testing procedure](../../.github/instructions/testing.instructions.md)
before import/collection; redirect storage/output/logs into owned synthetic roots.
Run the affected test first; after shared runtime changes run:

```bash
uv run --locked --no-sync pytest tests/ -m "not e2e" -q
```

This must not hit YouTube or any external network service.

## Real YouTube E2E

Real downloads are opt-in only. Ask or use them only when the user explicitly gives a URL and asks to download/test it.

For a real download, verify:

- video file exists;
- requested quality is respected as closely as yt-dlp can provide;
- audio is present when downloading video;
- subtitles are saved when requested;
- description is saved when requested;
- thumbnail is saved when requested;
- metadata JSON exists;
- result paths are returned by the project service.

## Current Q3 status — 2026-11-02

The user supplied one URL after Q2; the old WAITING_FOR_USER_URL state is historical.
Its real media HTTP403 remains **OPEN/BLOCKED**, with no successful full live media
proof. Limited extraction at320 does not prove that1080/1440/2160 are absent at SOURCE.
The source-only increment is independently ACCEPTED_Q3_SOURCE_ONLY_LIVE_BLOCKED;
local synthetic API/source CLI/MCP success and retained real sidecars do not close
this original requirement. See [Q3 verification](../command-first/VERIFICATION.md#q3-source-only-increment).

No further YouTube attempts are authorized in the current closure. The sole Oracle
consultation is complete; missing EJS/Node setup is not a proven403 cause. The
component/player-JS form timed out unanswered: **NOT_GRANTED**, not approval to
install/update/configure/fetch code, retry the URL, ask again or bypass verification/
access. Do not select another video, cookies, credentials or private proxy data.
The unchanged historical Q2 ZIP/EXE does not contain Q3 source changes.

For current source,1440p/2160p are maximum video heights, not exact-resolution
promises. Lower/unknown heights must be reported honestly from infoJSON/ffprobe.
Keep failed/partial outcomes failed: exact newly materialized sidecars may survive
an early error, while preexisting/unlisted/outside-root files must not be adopted.

## Recommended small real gate

Only after explicit authorization, use the user-provided URL and an owned temporary
output directory under the assigned scratch/diagnostics root. Historical example
URLs are not permission. Do not pollute the user's regular downloads.

## Reporting

Report the actual files found and explicitly say if a requested artifact was unavailable from YouTube, failed to download, or was only partially verified.
