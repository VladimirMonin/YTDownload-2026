---
id: ytdl-engineering-index
title: "YTDownload — инженерная документация"
kind: navigation
status: accepted
created: "2026-10-23"
updated: "2026-10-23"
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
| Как создавать и исполнять тесты, изоляция и доказательства | [Тестирование](../.github/instructions/testing.instructions.md) |
| Права на реальные сетевые загрузки | [Download testing](agent-instructions/03-download-testing.md) |
| События, поля, каналы и проверка журналов | [Логирование](../.github/instructions/logging.instructions.md) |
| CLI/MCP/GUI smoke и границы их доказательства | [Входы приложения](agent-instructions/04-mcp-and-gui.md) |
| Обязательные конечные gates, baseline и Git | [Quality gates](agent-instructions/05-quality-gates.md) |
| Назначение Oracle/Coder/Reviewer и способы запуска Pi | [Команда Pi](agent-team.md) |
| Методики и формы, не runtime приложения | [Project Foundation Kit](../tools/project-foundation/README.md) |

## Рефакторинг command-first

[PLAN](command-first/PLAN.md) и [CONTRACT](command-first/CONTRACT.md) подготовлены Oracle по исходной базе. Это план и предлагаемый поведенческий контракт, не сертификат реализации. Работа идёт в `refactor/command-first`; независимо приняты S1 (offline baseline), S2 (construction/ports/storage), S3 (cancellation/outcomes, pool lifetime, consistent snapshots/task-ID attribution) и S4 (token-bound exact-file deletion, partial/persistence outcomes, lazy Trash boundary). Нормативные PLAN/CONTRACT сохранены; актуальный disposition приведён в VERIFICATION. Полный будущий контракт этим не принят: успешная token-проводка CLI/MCP/GUI и полный lifetime остаются S5, final matrix — S6. Native Trash move/restore и общая legacy privacy не аттестованы. Фактические этапы и границы — [VERIFICATION](command-first/VERIFICATION.md); порядок документационного завершения и selective Git-доставки принятых срезов — [команда Pi](agent-team.md).

[Прежний план CLI/MCP](cli_mcp_unification_plan.md) сохраняется как историческое основание; его описания «CLI ещё нет» не следует принимать за текущий факт.

Нативные `.github/instructions/` сохраняют свой формат `applyTo/name/description`. Новые долговечные документы используют паспорт из [схемы пакета](../tools/project-foundation/references/metadata.md). Не надо массово переписывать старое руководство или stamping-ом объявлять его актуальным.
