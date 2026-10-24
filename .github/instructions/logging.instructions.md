---
applyTo: "**/*.py"
name: "LoggingInstructions"
description: "Правила логирования в проекте"
---

# Логирование изменения

Каноническая практическая инструкция. Основание — [философия](../../docs/foundation/project-philosophy.md), методика — [PFK quality](../../tools/project-foundation/references/quality.md). Читать перед добавлением события, обработкой исключения, изменением formatter/filter/handler, stdout/stderr, DEV или support-выхода.

## Владельцы и фактический механизм

- `src/core/logging_setup.py::setup_logging` настраивает стандартный `logging`, консоль и ротацию файлов. Прикладные владельцы сообщают факты через `logging.getLogger(__name__)`; отдельный framework/реестр не нужен.
- `DownloadCoordinator` определяет состояние очереди; логи его отражают, но не управляют им. Существующий task ID связывает события. Намерение, принятие, завершение, сохранение и доставка не объединяются словом `done`.
- Legacy `setup_logging`: явный `log_dir` → непустой `YTDL_LOG_DIR` (с `expanduser`) → `logs/` рядом с исходным проектом; default stream остаётся stdout. `initialize_app()`/`create_runtime()` глобальные handlers не настраивают. `runtime.log_dir` следует data root, но сам по себе не устанавливает logging.
- Entry contexts S5 используют stderr. GUI `app._logging` выбирает непустой `YTDL_LOG_DIR` → `YTDL_DATA_DIR/logs` → APPDATA/YTDownloader/logs (home fallback). Standalone writable CLI `_diagnostics` использует log override или выбранный `--data-dir`/environment root/logs. Readonly CLI без override и borrowed CLI без override не создают профиль/implicit file root ради logging. Для JSON owned stream handler подавлен, ошибки возвращаются одним безопасным stderr JSON, диагностика остаётся в явно выбранных owned files; бесконечного `StringIO` нет. Stdio не печатает banner в protocol stdout.
- Каждый context учитывает acquired handlers сразу после создания и только их форматирует/flush/close/remove, в том числе при частичном open failure. Ранее подключённые caller handlers временно отделены и возвращаются; подключённые во время invocation остаются теми же объектами/streams и сохраняют registration. Root/known logger levels восстанавливаются. Owned cleanup error не превращается в успех. S5-R1 независимо проверен normal/body/cleanup cases, physical before/during/after writes и следующей операцией, без пересоздания caller FileHandler(mode='w'). Это не гарантия всех произвольных concurrent logging configurations.
- Ротация: `app.log` 10 MiB и 5 резервных файлов; `app.error.log` 5 MiB и 3 резервных файла. Основной handler следует `YTDL_LOG_LEVEL` (default INFO), error-handler — ERROR+. Возрастной retention не реализован.
- S2 storage/runtime и S3 coordinator/backend/EventBus emitters проверены на настоящих непустых main/error files и stderr с synthetic sentinels. Backend logger принимает сообщения SDK как недоверенное содержимое и пишет только технический level/reason; EventBus не печатает arbitrary event/payload/exception chain. В S3-R1/R2 изменились projection/output namespace, не logging chain; affected native sink case повторно проверен. Это не общий privacy-filter и не аттестация всех third-party/legacy сообщений.
- В S4 application `deletion.*` и infrastructure `trash.move.*` проверены на реальных непустых main/error/configured-stream sinks после formatter/handler/flush. Полезные id/reason_code/moved_count сохраняются, private URL/title/path/proxy/raw-error sentinels отсутствуют. Структурированный result с явно запрошенными paths — не diagnostic log; partial/unknown/save-failure нельзя называть полным success. Safe in-process CLI refusal не доказывает весь standalone/legacy/native Qt stderr: эта граница остаётся отдельно.
- S5 GUI/MCP/CLI изменённые emitters и common safe error mapping проверены через непустые main/error/stderr sinks с flush/readback, чистыми result/protocol channels и полезными id/code/count. Synthetic URL/proxy/title/path/raw-error markers отсутствуют; явный useful result с title/description/path не diagnostic log. Это scoped proof, не blanket legacy/native Qt privacy.
- Наличие централизованного privacy-filter для всех сообщений не доказано. Эта инструкция задаёт обязательства, а не объявляет legacy logs безопасными.

## События и поля

1. От сценария выбрать существенные начало/принятие/исход/отказ/cleanup. Записать producer, ID операции и причину, если они нужны для объяснения. Не логировать каждый progress tick, фокус или repaint.
2. Использовать имена по ответственности (`download.*`, `command_api.*`, `repository.*`, `mcp.*`) и lazy formatting: `logger.info("download.completed id=%d elapsed_ms=%d", task_id, elapsed_ms)`.
3. Допустимы проверенные технические `id`, `stage`, `reason_code`, `status`, enum качества/типа, `transport`, `count`, размеры в байтах, `elapsed_ms`, технический класс исключения. Неизвестное — omitted/null по схеме; реальный 0 остаётся 0. Количество имеет известную область, длительность — источник и единицы.
4. DEBUG — технические детали; INFO — нормальный переход; WARNING — обработанная проблема; ERROR — операция провалилась; CRITICAL — приложение не может продолжать. Terminal-событие не теряется из-за sampling.

## Приватность и каналы

Не записывать ключи/токены/credentials, raw config, URL/прокси, пользовательские пути и имена файлов/папок, названия видео, описание, субтитры, содержимое буфера, промпты и тела внешних ответов. Длина строки и название поля сами по себе не делают содержимое безопасным.

`str(exc)`, exception args/cause, `exc_info=True` и traceback могут включать URL, пути и данные библиотек. Использовать безопасный код/тип; traceback допустим только при доказанной обработке всех затронутых sinks до записи. Не рекомендовать автоматический raw traceback на каждой ошибке.

CLI stdout с заказанным результатом и MCP stdout с протоколом — отдельные контрактные каналы. `print()` допустим для CLI-результата и smoke-отчёта, но не для обхода logging-политики. Диагностика stdio MCP не загрязняет protocol stdout. Не дублировать запрошенное описание/пути в диагностический журнал.

DEBUG не разрешает содержимое. Отдельный DEV content sink и автоматический support export не заявлены реализованными; не придумывать UI «Настройки → Логи → Экспорт». Локальный сбор, сохранение, export и внешняя отправка — разные разрешения. Телеметрию не добавлять, отправлять журналы наружу можно только по отдельному согласованию.

## Проверка настоящего выхода

До import/setup назначить собственные временные `APPDATA`/home/output/log roots по [инструкции тестирования](testing.instructions.md). Рабочие журналы не читать.

На синтетических данных пройти emitter → существующий filter/formatter → реальный handler → flush/drain → readback непустого файла/потока. Проверить одновременно полезные ID/коды/count/duration и отсутствие запрещённых маркеров. Пустой файл, disabled sink и один `caplog` не доказывают файловую приватность. Structured-выход требует parsed records и смысловой связи с фактом, не только суффикса `.jsonl`.

Если меняется общий logging chain, проверить затронутые entrypoints, ошибки стороннего backend и обе группы файлов. При отказе фильтра raw fallback запрещён; диагностика не запускает повтор продукта и не блокирует его бесконечно. I/O failure и недоступный канал описать честно, не объявляя существующий код надёжным одним текстом.

Сохранить команду, raw exit, выбранный путь, наблюдение и limits. Обновлять эту инструкцию при смене owner/channel/units/privacy-chain/retention/DEV/export. Не разворачивать проверку всей подсистемы ради одного count; не выдавать структурный checker документа за privacy PASS.
