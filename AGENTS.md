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

S1–S6 независимо приняты в согласованной offline-границе; S5-R1 закрыт на исправленном целом срезе. CLI/MCP/GUI вызывают один Application API, передают matching deletion token и явно различают owned/borrowed lifetime. CLI query — readonly snapshot, standalone add ждёт terminal/persistence, standalone cancel требует live owner; отдельный data root не означает attach. Удаление обрабатывает только записанные файлы через recoverable Trash port, сообщает partial/persistence outcomes и не удаляет папки. GUI и embedded HTTP заимствуют один runtime; только desktop entry закрывает его. Logging contexts закрывают только собственные handlers, сохраняя ранние и поздние caller objects. S6 завершил конечные proofs и CI isolation/module-command alignment: actual local Windows/Python3.14.2 argv/env, не hosted CI/Linux/Python3.12/pwsh7. Native Trash move/restore, live/codec, EXE/manual visual и whole legacy privacy остаются NOT_RUN. Текущее состояние и пределы — [VERIFICATION](docs/command-first/VERIFICATION.md); нормативные PLAN/CONTRACT сохраняют требования, а не заменяют фактическую приёмку.

## Жёсткие границы

- До записи проверить `git status`, ветку и действующих владельцев; чужие изменения не перезаписывать. Рефакторинг — в отдельной ветке после документации и плана Oracle.
- Coder не stage/commit/push. После независимого ACCEPTED того же среза назначенный Reviewer завершает затронутую документацию/инструкции и является единственным владельцем index/commit/push в `refactor/command-first`. Сохранять только явно принятые пути; проверять parent, содержимое commit и remote ref. Это прямое проектное разрешение не распространяется на main, force, tags, release, изменение remote/visibility или destructive Git.
- Не выполнять реальные YouTube-загрузки/сетевые E2E без явного разрешения и конкретного URL. Проверки — на собственных синтетических данных, с изоляцией **до** collection/import/config access.
- Не читать/печатать secrets, токены, `.env`, личные settings/history/logs и загрузки ради диагностики. Не менять рабочие данные. Продуктовые удаления проверяются только в собственных временных деревьях.
- Не устанавливать/обновлять пакеты, не скачивать vendor binaries, не менять системное ПО и глобальные Pi/Hermes settings без отдельного разрешения. Использовать готовую `.venv` и `uv run --locked --no-sync`.
- FFmpeg искать штатным модулем с учётом Windows/Linux, не считать `.exe` универсальным путём.
- Изменения `uv.lock` и `.gitignore` требуют объяснения и отдельного просмотра; случайный churn не включать. Методический `tools/project-foundation/` при обычной разработке read-only.
- Не оставлять собственные фоновые серверы/потоки после проверки; не закрывать чужие процессы. Предпросмотр и запрос отмены не выдавать за состоявшийся эффект.
- CLI/MCP stdout оставлять для результата/протокола; диагностику отделять и не логировать пользовательское содержимое.

## Исполнение и завершение

Oracle (`openai-codex/gpt-6-astra`, `xhigh`) составляет полный план/контракт; Coder и независимый Reviewer (`openai-codex/gpt-6.1-sol`, `max`) работают в отдельных постоянных Pi-сессиях. После передачи Hermes — только оркестратор. Обязательные замечания возвращать тому же кодеру, существенные неясности — Oracle. Не подменять независимую приёмку авторскими тестами. После ACCEPTED тот же Reviewer выполняет документационное завершение и разрешённую selective Git-доставку без нового запроса согласия; при rejection не сохраняет отклонённый runtime. Локальная приёмка, commit, push/readback и remote CI — отдельные факты. Подробности — [команда Pi](docs/agent-team.md).

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
