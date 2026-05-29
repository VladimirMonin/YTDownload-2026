# 03 — Download testing

## Offline checks

Run by default after code changes:

```bash
uv run pytest tests/ -m "not e2e" -q
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

Use one short or user-provided video and a temporary output directory under `tmp/` or a clearly named diagnostics folder. Do not pollute the user's regular downloads unless requested.

## Reporting

Report the actual files found and explicitly say if a requested artifact was unavailable from YouTube, failed to download, or was only partially verified.
