---
id: ytdl-engineering-index
title: "YTDownload — инженерная документация"
kind: navigation
status: accepted
created: "2026-10-23"
updated: "2026-10-25"
areas: [engineering, documentation]
summary: "Канонические правила разработки, философия, роли Pi и переход к command-first."
---

# Инженерный вход

[AGENTS.md](../AGENTS.md) — обязательный первый файл для агента. [Пользовательское руководство](README.md) остаётся отдельным документом; эта страница его не заменяет.

| Что нужно | Владелец |
|---|---|
| Причины решений, архитектурные принципы, стратегия проверки и приватность | [Философия проекта](foundation/project-philosophy.md) |
| Стек, текущие точки входа | [Обзор проекта](agent-instructions/01-project-overview.md) |
| Python/uv и FFmpeg | [Окружение](agent-instructions/02-environment-and-dependencies.md) |
| Полный standalone console пакет, CLI build target и сохранённый GUI default | [Build instructions](../.github/instructions/build_system.instructions.md), [быстрый запуск CLI](../README.md) |
| Как создавать и исполнять тесты, изоляция и доказательства | [Тестирование](../.github/instructions/testing.instructions.md) |
| Права на реальные сетевые загрузки | [Download testing](agent-instructions/03-download-testing.md) |
| События, поля, каналы и проверка журналов | [Логирование](../.github/instructions/logging.instructions.md) |
| CLI/MCP/GUI smoke и границы их доказательства | [Входы приложения](agent-instructions/04-mcp-and-gui.md) |
| Обязательные конечные gates, baseline и Git | [Quality gates](agent-instructions/05-quality-gates.md) |
| Назначение Oracle/Coder/Reviewer и способы запуска Pi | [Команда Pi](agent-team.md) |
| Методики и формы, не runtime приложения | [Project Foundation Kit](../tools/project-foundation/README.md) |

## Рефакторинг command-first

[PLAN](command-first/PLAN.md) и [CONTRACT](command-first/CONTRACT.md) подготовлены Oracle по исходной базе. Это план и предлагаемый поведенческий контракт, не сертификат реализации. Работа идёт в `refactor/command-first`; независимо приняты S1 (offline baseline), S2 (construction/ports/storage), S3 (cancellation/outcomes, pool lifetime, consistent snapshots/task-ID attribution), S4 (token-bound exact-file deletion, partial/persistence outcomes, lazy Trash boundary) и весь S5 (реальные CLI/stdio/HTTP/GUI consumers, token wiring и явный adapter lifetime). S5-R1 закрыт: logging contexts сохраняют те же ранние/поздние caller handlers и закрывают только свои. PLAN явно разделяет исходный Oracle snapshot, исторические status notes и принятые S1–S5; нормативные semantics CONTRACT неизменны. Текущий disposition приведён в VERIFICATION. S6 и конечная offline-миграция независимо приняты: actual CI preparation/commands, useful composed API/JSON/readonly CLI/next writer и final gates квалифицированы на local Windows/Python3.14.2 с unchanged source/assertion-bound S1–S5 reuse. Существующие matrix/triggers/install recipe сохранены; hosted CI/Linux/configured Python3.12/pwsh7 wrapper не исполнялись и не названы PASS. На завершении S6 mypy34/full configured lint57 были открытым debt, не PASS; historical receipts сохранены. Следующий Q1 независимо технически принят без ослабления config: mypy0/68, configured first-party1060 (включая build helper и новый test), changed31 E/F/I0, full291/7 e2e deselected/0 skips и четыре module smokes0. Imported PFK checker/recursive whole-root lint — NOT_RUN. Это frozen Q1 snapshot. Q2 независимо ACCEPTED_Q2_LOCAL_OFFLINE для Windows x64 console onedir: полный759-file runtime, relocation и11 CLI leaves в fresh native71-row aggregate плюс8 complementary commands, offline308/7 e2e deselected/0 skips, mypy0/68, configured1090, changed6 E/F/I0, четыре module smokes0. Реальный own loopback transfer дал MP4 MPEG-4+AAC и audio-only AAC/M4A, history/info JSON/reopen; это не YouTube/720p/remote sidecars. Native delete-files — PARTIAL_DELETE/TRASH_UNAVAILABLE UNKNOWN, source исчез/history сохранена, не recoverable-success; keep-files физически проверен отдельно. HTTP Ctrl+C — native1/INTERRUPTED, с остановкой/port reuse/next owner. Полный ZIP — контейнер того же accepted payload, не сборка по будущему doc commit. GUI default/spec сохранены, GUI build/visual не выполнялись. Техническая приёмка, local package, selective commit/literal remote readback и remote CI jobs — разные факты. External YouTube ждёт конкретного пользовательского URL; native Trash destination/restore, Linux/CI/иные платформы, optional remote features, GUI/manual visual, whole legacy privacy и legal redistribution certification не аттестованы. Фактические этапы и границы — [VERIFICATION](command-first/VERIFICATION.md); порядок документационного завершения и selective Git-доставки принятых срезов — [команда Pi](agent-team.md).

[Прежний план CLI/MCP](cli_mcp_unification_plan.md) сохраняется как историческое основание; его описания «CLI ещё нет» не следует принимать за текущий факт.

Нативные `.github/instructions/` сохраняют свой формат `applyTo/name/description`. Новые долговечные документы используют паспорт из [схемы пакета](../tools/project-foundation/references/metadata.md). Не надо массово переписывать старое руководство или stamping-ом объявлять его актуальным.
