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

## Recommended small real gate

Only after explicit authorization, use the user-provided URL and an owned temporary
output directory under the assigned scratch/diagnostics root. Historical example
URLs are not permission. Do not pollute the user's regular downloads.

## Reporting

Report the actual files found and explicitly say if a requested artifact was unavailable from YouTube, failed to download, or was only partially verified.
