# AGENTS.md — YTDownload 2026

Обязательная точка входа для всех агентов. Рабочий проект — корень этого репозитория, не каталог методического пакета.

## Сначала прочитать

1. [Философия проекта](docs/foundation/project-philosophy.md): command-first, сохранность, проверка, приватность.
2. [Обзор](docs/agent-instructions/01-project-overview.md) и [окружение](docs/agent-instructions/02-environment-and-dependencies.md).
3. [Тестирование](.github/instructions/testing.instructions.md), [права на реальные загрузки](docs/agent-instructions/03-download-testing.md), [quality gates](docs/agent-instructions/05-quality-gates.md).
4. [Логирование](.github/instructions/logging.instructions.md) перед изменением событий/ошибок/выходов; [CLI/MCP/GUI](docs/agent-instructions/04-mcp-and-gui.md) для соответствующих входов.
5. [Команда Pi](docs/agent-team.md) при агентной разработке. Полная навигация — [docs/engineering.md](docs/engineering.md).

## Архитектурное правило

Сначала независимый Application API и предметные правила; CLI, MCP и GUI — его адаптеры. Ядро не зависит от Qt, CLI-парсера и MCP SDK. Общий код не равен общей живой очереди между процессами. Владелец состояния, время жизни, ошибки, отмена и эффекты определяются явным контрактом, а не названием паттерна.

В этой задаче GUI не перерабатываем. Сохраняем действующие точки входа и форматы данных; минимальное совместимое подключение к ядру требует регрессионной проверки. Исторический `docs/cli_mcp_unification_plan.md` не источник фактов о текущем коде.

S1–S6 независимо приняты в согласованной offline-границе; S5-R1 закрыт на исправленном целом срезе. CLI/MCP/GUI вызывают один Application API, передают matching deletion token и явно различают owned/borrowed lifetime. CLI query — readonly snapshot, standalone add ждёт terminal/persistence, standalone cancel требует live owner; отдельный data root не означает attach. Удаление обрабатывает только записанные файлы через recoverable Trash port, сообщает partial/persistence outcomes и не удаляет папки. GUI и embedded HTTP заимствуют один runtime; только desktop entry закрывает его. Logging contexts закрывают только собственные handlers, сохраняя ранние и поздние caller objects. S6 завершил конечные proofs и CI isolation/module-command alignment: actual local Windows/Python3.14.2 argv/env, не hosted CI/Linux/Python3.12/pwsh7. На границе S6 native Trash move/restore, live/codec, EXE/manual visual и whole legacy privacy оставались NOT_RUN; последующие Q2 результаты не переписывают эту историю. Текущее состояние и пределы — [VERIFICATION](docs/command-first/VERIFICATION.md); нормативные PLAN/CONTRACT сохраняют требования, а не заменяют фактическую приёмку.

Q1 независимо технически принят на точном замороженном срезе: mypy — exit0/68 source files, configured Ruff E/F/I/UP — exit0 по 106 first-party Python files, changed31 E/F/I — exit0, full offline — 291 passed/7 e2e deselected/0 skipped. Исторические 34/57 findings S6 сохранены в VERIFICATION; новый полный first-party scope учёл также build helper. Imported PFK checker/recursive whole-root lint не объявлены PASS. Эти результаты относятся к точному принятому Q1, не автоматически к будущему working tree.

Q2 независимо ACCEPTED_Q2_LOCAL_OFFLINE: полный Windows x64 console onedir (759 files), relocation без dev/Python/PATH assistance, все11 CLI leaves в fresh native71-row aggregate и8 complementary commands. Свежие source gates: affected42, offline308/7 e2e deselected/0 skipped, mypy0/68, configured1090, changed6 E/F/I0, четыре module smokes0. Local MP4 MPEG-4+AAC / audio-only AAC/M4A и persistence/reopen проверены, не YouTube/720p/remote sidecars. Native Trash вернул PARTIAL_DELETE/TRASH_UNAVAILABLE, UNKNOWN: own source исчез, history сохранена; destination/recoverability/restore не подтверждены. Keep-files отдельно сохранил recorded bytes. HTTP Ctrl+C — native1/INTERRUPTED. GUI build/дизайн/visual, иные платформы/CI и legal redistribution certification этим не приняты. Полный ZIP — только новый контейнер тех же bytes, не rebuild; EXE отдельно непереносим.

Нет конкретного пользовательского URL — external YouTube WAITING_FOR_USER_URL / NOT_RUN, без права выбирать sample. Это не блокирует local delivery. Уже принятые product gates не повторяются ради prose/Git/ZIP-доставки; выполняются только затронутые final-byte проверки документов и идентичности payload. Команды запуска и сборки — [README](README.md) и [build instructions](.github/instructions/build_system.instructions.md).

## Жёсткие границы

- До записи проверить `git status`, ветку и действующих владельцев; чужие изменения не перезаписывать. Рефакторинг — в отдельной ветке, связными согласованными срезами. Достаточный существующий план переиспользовать; Oracle не является обязательной стадией каждой задачи.
- Coder не stage/commit/push. После независимого ACCEPTED того же среза назначенный Reviewer завершает затронутую документацию/инструкции и является единственным владельцем index/commit/push в `refactor/command-first`. Сохранять только явно принятые пути; проверять parent, содержимое commit и remote ref. Это прямое проектное разрешение не распространяется на main, force, tags, release, изменение remote/visibility или destructive Git.
- Не выполнять реальные YouTube-загрузки/сетевые E2E без явного разрешения и конкретного URL. Проверки — на собственных синтетических данных, с изоляцией **до** collection/import/config access.
- Не читать/печатать secrets, токены, `.env`, личные settings/history/logs и загрузки ради диагностики. Не менять рабочие данные. Продуктовые удаления проверяются только в собственных временных деревьях.
- Не устанавливать/обновлять пакеты, не скачивать vendor binaries, не менять системное ПО и глобальные Pi/Hermes settings без отдельного разрешения. Использовать готовую `.venv` и `uv run --locked --no-sync`.
- FFmpeg искать штатным модулем с учётом Windows/Linux, не считать `.exe` универсальным путём.
- Изменения `uv.lock` и `.gitignore` требуют объяснения и отдельного просмотра; случайный churn не включать. Методический `tools/project-foundation/` при обычной разработке read-only.
- Не оставлять собственные фоновые серверы/потоки после проверки; не закрывать чужие процессы. Предпросмотр и запрос отмены не выдавать за состоявшийся эффект.
- CLI/MCP stdout оставлять для результата/протокола; диагностику отделять и не логировать пользовательское содержимое.

## Исполнение и завершение

Coder и независимый Reviewer — агенты в отдельных постоянных Pi-сессиях: `openai-codex/gpt-6.1-sol`, `max`. Oracle — `openai-codex/gpt-6-astra`, `xhigh`; вызывать только при конкретных затруднениях, существенной неясности или безрезультатном ремонте, а не для планирования каждого следующего среза. Кодеру давать средние–крупные связные задачи с достаточной проверкой результата. Hermes — только оркестратор; доработка возвращается тому же Coder, повторная проверка — тому же Reviewer.

Не подменять независимую приёмку авторскими тестами. Reviewer сначала возвращает технический ACCEPTED для точного замороженного кандидата и освобождает пересекающиеся ресурсы, затем в той же беседе завершает документацию/инструкции, selective commit и разрешённый push/readback. После технического ACCEPTED кодер может сразу брать следующий непересекающийся срез, пока Reviewer завершает предыдущий; ждать окончания документации или push без реальной зависимости не нужно. Принятые байты не меняются до commit, index имеет одного владельца, непринятый следующий срез не попадает в доставку. При rejection — исправление и повторная проверка теми же агентами, без публикации отклонённого кода. Техническая приёмка, документация, commit, push/readback и remote CI — отдельные факты. Подробности — [команда Pi](docs/agent-team.md).

После изменения выполнять адресную регрессию, затем затронутые обязательные проверки. Команды запускаются в изолированной среде по инструкции тестирования:

```bash
uv run --locked --no-sync pytest tests/ -m "not e2e" -q
uv run --locked --no-sync ruff check --select E,F,I <changed-python-files>
uv run --locked --no-sync python -m scripts.smoke_cli_help
uv run --locked --no-sync python -m scripts.smoke_mcp
uv run --locked --no-sync python -m scripts.smoke_mcp_stdio
uv run --locked --no-sync python -m scripts.smoke_gui
```

`<changed-python-files>` заменяется реальным непустым списком. Наличие команды здесь не утверждение о её сегодняшнем PASS. Полный lint/mypy baseline и новые ошибки различать, не прятать обязательный провал. Актуализировать затронутые контракт/руководство/инструкции. Завершение: что работает, что реально проверено (raw exit и граница подмены), независимый verdict, что NOT_RUN и почему. План, написанный тест и работающий сценарий — разные результаты.
