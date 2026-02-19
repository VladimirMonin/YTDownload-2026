---
applyTo: "**/*.py"
name: "LoggingInstructions"
description: "Правила логирования в проекте"
---

# 📋 Logging Instructions

**Главное:** Логи — история выполнения, не debug-болтовня. Lazy formatting (`%s`, НЕ f-string).

---

## 🔒 Конфиденциальные данные — НИКОГДА не логируем

- ❌ Текст транскрипций, ответы API, содержимое буфера обмена
- ❌ API ключи, токены, credentials
- ❌ Пользовательские промпты (содержимое)
- ❌ Тексты запросов к LLM и ответы от LLM
- ❌ **Имена файлов пользователя** (названия записей, видео, документов — могут быть личными)
- ❌ **Пути к файлам** (полные И относительные — содержат имя пользователя ОС, структуру папок)
- ❌ **Названия папок пользователя** (раскрывают контекст использования)
- ❌ **Имена промпт-файлов** (раскрывают цели: `medical_notes.md`, `legal_contract.md`)
- ❌ `sys.executable` (содержит путь к home directory)
- ❌ Каждое нажатие кнопки / фокус виджетов

## ✅ Логируем (безопасные данные)

- ✅ ID (UUID) — `job_id=%s`, `transcription_id=%s`
- ✅ Статистику — chars, words, segments, tokens, chunks, duration
- ✅ Названия моделей — `model=%s` (whisper, LLM)
- ✅ Имена устройств — `device=%s` (cuda, cpu, mps)
- ✅ Расширения файлов — `ext=%s` (.mp4, .wav) — безопасно
- ✅ Булевы флаги — `is_video=%s`, `is_temp=%s`, `ok=True`
- ✅ Время выполнения — `elapsed_ms=%d`
- ✅ Количественные метрики — `count=%d`, `total=%d`, `percent=%d`

---

## Формат по слоям

| Слой           | Уровень     | Формат                                                      |
| -------------- | ----------- | ----------------------------------------------------------- |
| UI (`src/ui/`) | INFO        | `ui.record.start`, `ui.file.drop count=%d`                  |
| Services       | INFO        | `job.transcribe.done elapsed_ms=%d words=%d`                |
| Infrastructure | INFO/WARN   | `whisper.model.load model=%s device=%s`                     |
| Workers        | DEBUG/ERROR | `worker.transcription.start`, `...failed` + `exc_info=True` |

---

## Уровни

| Уровень  | Когда                                    |
| -------- | ---------------------------------------- |
| DEBUG    | Детали для разработчика                  |
| INFO     | Нормальный ход выполнения                |
| WARNING  | Проблема, но работаем                    |
| ERROR    | Операция провалилась (+ `exc_info=True`) |
| CRITICAL | Приложение падает                        |

---

## Антипаттерны

- `print()` → `logger.info()`
- `logger.info(f"...")` → `logger.info("... %s", var)` (lazy!)
- `logger.info("Transcription: %s", text)` → ЗАПРЕЩЕНО (пользовательские данные)
- `logger.info("file=%s", path.name)` → ЗАПРЕЩЕНО (имена файлов пользователя)
- `logger.info("saved to: %s", full_path)` → ЗАПРЕЩЕНО (путь содержит home dir)
- `logger.info("prompt=%s", prompt_file)` → ЗАПРЕЩЕНО (раскрывает цели использования)

---

## Файлы логов

| Файл            | Уровень | Размер            |
| --------------- | ------- | ----------------- |
| `app.log`       | INFO+   | 10 MB × 5 бэкапов |
| `app.error.log` | ERROR+  | 5 MB × 3 бэкапа   |

**Дебаг с пользователем:** Настройки → Логи → DEBUG → воспроизвести → "Экспорт диагностики"

---

**Конец Logging Instructions**
