---
applyTo: "**"
name: "ConceptInstructions"
description: "Концепция YT Downloader"
---

# 🎬 YT Downloader — Project Concept

**Stack:** Python 3.12+ | PySide6 | yt-dlp | FFmpeg (vendor) | UV

---

## 📂 Project Structure

```
src/
├── core/           # EventBus, LoggingSetup
├── domain/         # Models, Protocols (pure Python, без UI/сети)
│   ├── models/     # DownloadTask, VideoInfo, AppSettings, HistoryEntry
│   └── protocols/  # IDownloadService, IHistoryRepository, ISettingsRepository
├── infrastructure/ # yt-dlp wrapper, FFmpeg checker, JSON repos
├── application/    # DownloadCoordinator (оркестрация загрузок)
└── ui/             # PySide6 GUI
    ├── managers/   # DownloadManager, HistoryManager
    ├── widgets/    # UrlInputWidget, DownloadItemWidget, HistoryWidget,
    │               # SettingsDialog, DownloadOptionsWidget
    └── utils/      # TablerIcons, Theme, PathHelper

tests/              # Pytest: unit + e2e с реальными загрузками
resources/
├── fonts/          # JetBrainsMono, NotoSans (OFL)
└── icons/tabler/   # Tabler SVG icons (MIT)
vendor/
└── ffmpeg/bin/     # ffmpeg.exe, ffprobe.exe, ffplay.exe (LGPL)
```

---

## 🏗️ Architecture (4 Layers)

```
┌─────────────────────────────────────┐
│ UI: PySide6 Widgets + Qt Signals   │  ← Thread-safe via Signal Bridge
├─────────────────────────────────────┤
│ Application: DownloadCoordinator   │  ← Оркестрация, бизнес-логика
├─────────────────────────────────────┤
│ Domain: Pure Python (Protocols)    │  ← Без UI/network зависимостей
├─────────────────────────────────────┤
│ Infrastructure: yt-dlp / FFmpeg    │  ← Реализация протоколов
└─────────────────────────────────────┘
```

**Key Principles:**

- **Protocol-based** — интерфейсы через ABC/Protocol
- **Event-driven** — EventBus для cross-layer коммуникации
- **Dependency Injection** — через конструкторы (main.py = DI Container)
- **Thin Orchestrator** — MainWindow ≤ 400 строк, только shell + wiring

---

## 🎯 Features

| Feature                                                     | Статус |
| ----------------------------------------------------------- | ------ |
| Single video download                                       | ✅     |
| Playlist download                                           | ✅     |
| Quality selection (Best / 1080p / 720p / 480p / Audio Only) | ✅     |
| Video+Audio merge или Audio Only                            | ✅     |
| Optional: субтитры (язык из настроек)                       | ✅     |
| Optional: описание + thumbnail                              | ✅     |
| Структура: `OutDir/VideoTitle/video.mp4 + ...`              | ✅     |
| JSON history                                                | ✅     |
| Proxy settings                                              | ✅     |
| Progress per item                                           | ✅     |
| Dark/Light theme                                            | ✅     |

---

## 📂 Download Output Structure

```
output_dir/
├── PlaylistName/           # Для плейлистов
│   ├── 001 - VideoTitle/
│   │   ├── video.mp4
│   │   ├── info.json
│   │   ├── description.txt
│   │   ├── thumbnail.webp
│   │   └── ru.vtt          # Субтитры по языку из настроек
│   └── 002 - VideoTitle/
│       └── ...
└── VideoTitle/             # Для одиночных видео
    ├── video.mp4
    ├── info.json
    └── ...
```

---

## 🔧 Entry Points

| Файл      | Назначение                                       |
| --------- | ------------------------------------------------ |
| `app.py`  | Thin entry: logging → QApplication → main window |
| `main.py` | DI Container: `initialize_app()` → dict сервисов |

---

## ⚙️ Key Config (AppSettings)

- `output_dir: Path` — папка загрузки
- `proxy: str` — прокси (socks5://... или http://...)
- `quality: str` — "best" | "1080p" | "720p" | "480p" | "audio"
- `download_type: str` — "video" | "audio"
- `subtitle_lang: str` — "ru", "en", "kk", ...
- `save_subtitles: bool`
- `save_description: bool`
- `save_thumbnail: bool`
- `max_concurrent: int` — параллельность загрузок

---

## 📖 Agent Workflow

1. Читай `concept.instructions.md` перед любой работой
2. Domain layer — без PySide6 и network импортов
3. Qt Signals только в UI layer (QObject)
4. EventBus в Core, Qt Signals только в UI
5. Context7 для библиотек API
6. FFmpeg находится в `vendor/ffmpeg/bin/` — используй оттуда

---

**Конец Concept Instructions**
