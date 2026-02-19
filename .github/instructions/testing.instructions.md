---
applyTo: "tests/**"
name: "TestingInstructions"
description: "Правила написания и запуска тестов"
---

# 🧪 Testing Guidelines

## Структура тестов

```
tests/
├── downloads/          # Скачанные файлы (gitignored)
├── conftest.py         # pytest fixtures
├── test_ytdlp_unit.py  # Unit тесты (без сети)
├── test_download_e2e.py  # E2E: реальные загрузки
└── test_ffmpeg.py      # Проверка FFmpeg
```

---

## Типы тестов

### Unit Tests

- Без сетевых вызовов
- Мокируем yt-dlp и FFmpeg
- Для: парсеры, валидаторы, модели, репозитории

### E2E Integration Tests

- **Реальные загрузки** с YouTube
- Test URL: `https://youtu.be/6BW4lo7f71I` (ролик)
- Test Playlist: `https://youtube.com/playlist?list=PL6plRXMq5RABbVCM0dn23PTKO13WcXnbf`
- Проверка через FFmpeg: `ffprobe -v quiet -print_format json -show_streams file.mp4`
- Тестируем: 1080p, 720p, audio only

---

## Правила

1. **Fixtures** для пути к FFmpeg: `PROJECT_ROOT / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe"`
2. **E2E тесты** помечать: `@pytest.mark.e2e` + skip без сети
3. **Downloads** очищать после тестов (или хранить в `tests/downloads/`)
4. **Проверяй через FFprobe**: контейнер, кодеки, длительность

---

## Запуск

```bash
# Все тесты кроме e2e
uv run pytest tests/ -v -m "not e2e"

# Только unit тесты
uv run pytest tests/test_ytdlp_unit.py -v

# E2E (реальная сеть)
uv run pytest tests/test_download_e2e.py -v -m e2e

# Все
uv run pytest tests/ -v
```

---

## Пример e2e проверки

```python
@pytest.mark.e2e
def test_download_1080p(tmp_path, ffprobe_path):
    """Скачивает реальное видео и проверяет через ffprobe."""
    service = YtDlpService(settings_with_1080p)
    result = service.download("https://youtu.be/6BW4lo7f71I", tmp_path)
    assert result.success
    video_file = next(tmp_path.rglob("*.mp4"))
    info = probe_video(ffprobe_path, video_file)
    assert info["height"] == 1080
```

---

**Конец Testing Instructions**
