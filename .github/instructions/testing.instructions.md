---
applyTo: "tests/**"
name: "TestingInstructions"
description: "Правила написания и запуска тестов"
---

# Тестирование изменения

Каноническая инструкция выбора, изоляции, исполнения и интерпретации тестов. Основание — [философия проекта](../../docs/foundation/project-philosophy.md) и [PFK quality](../../tools/project-foundation/references/quality.md). Конечные обязательные gates — [05-quality-gates](../../docs/agent-instructions/05-quality-gates.md); права на реальную сеть — [03-download-testing](../../docs/agent-instructions/03-download-testing.md).

## Выбрать сценарий, а не число тестов

1. Назвать наблюдаемый успех, существенный отказ, owner/consumer и сохраняемые данные. Прочитать существующий тест и реальные определения/использования до создания fixture.
2. Unit проверяет правило. Integration соединяет настоящие owners. Сценарный тест проходит реальный public entry → Application API → эффект/репозиторий → readback, с явной подменой внешнего yt-dlp/сети. Subject и важное соединение не подменяются заранее заготовленным успехом.
3. До исправления получить baseline; новая регрессия должна показать нужный отказ до реализации. Не удалять имеющийся код ради искусственного RED. После изменения повторить тот же случай, затем затронутые sibling paths. Для структурного refactor допускается исходный зелёный characterization test с честным описанием.
4. Проверять ошибки, частичный исход, отмену/позднее завершение, повтор без двойного эффекта, сохранность, reopen и следующий запрос там, где применимы. `save.called` слабее повторного чтения, `cancel_requested` не доказательство физической остановки.

## Изоляция до collection и import

- Использовать готовое окружение: `uv run --locked --no-sync`. Не делать `uv sync` и не устанавливать зависимости автоматически. Наличие окружения проверяется до запуска; недостающая зависимость — конкретный blocker, не разрешение скачать её.
- Прочитать pytest config, `tests/conftest.py`, module-level setup, plugins и bootstrap. `tmp_path` внутри теста не защищает от раннего `initialize_app()` и загрузки рабочих настроек.
- До запуска процесса назначить явно принадлежащий проверке scratch/diagnostics root; унаследованный `$TMPDIR` сам по себе не доказывает владение. Создать собственные подпапки и перенаправить `APPDATA`/`LOCALAPPDATA`, `HOME`/`USERPROFILE`, `TMP`/`TEMP`/`TMPDIR`, cache, `YTDL_LOG_DIR` и **`YTDL_DATA_DIR`**. Последний выше APPDATA/home в `create_runtime`; унаследованный путь к рабочему профилю недопустим для теста. Не менять реальный профиль ОС или глобальные settings.
- Для offline-запуска задать `UV_OFFLINE=1`, `UV_NO_SYNC=1`, `UV_PYTHON_DOWNLOADS=never`, собственные `UV_CACHE_DIR`/`RUFF_CACHE_DIR`/`MYPY_CACHE_DIR`/`XDG_CACHE_HOME`, `PYTHONDONTWRITEBYTECODE=1`, `QT_QPA_PLATFORM=offscreen`, `FASTMCP_CHECK_FOR_UPDATES=off`, `DO_NOT_TRACK=1`. Сохранить необходимые Windows PATH/SYSTEMROOT/WINDIR/COMSPEC без их полного дампа.
- Не загружать неаудированные pytest plugins: проверенный S1 runner задаёт `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` и `PYTEST_ADDOPTS` с `-p pytestqt.plugin -p no:cacheprovider --basetemp=<новый-абсолютный-owned-path>`. Для Windows-строки ADDOPTS использовать `/` либо корректное quoting: pytest разбирает её через shell-like tokenizer; проверить resolved basetemp внутри своего root до запуска. Не переиспользовать старый basetemp ради очистки.
- Проверить источник `Path.home()`/репозиториев, default output и logging на достигнутом пути. В текущем коде default output — synthetic home/Downloads/YTDownloader либо явный `AppSettings(output_dir=...)`; `YTDL_OUTPUT_DIR` не является продуктовым override. По возможности передавать явные пути/API-параметры; не обещать изоляцию, если код игнорирует выбранный root.
- Все записи/удаления — только синтетические файлы внутри принадлежащего проверке дерева. Не читать настоящие `.env`, settings/history/logs/downloads для заполнения fixture. Не очищать чужие артефакты и не закрывать чужие процессы. Исключать `tests/downloads` до collection (например, `--ignore=tests/downloads`), не обходить и не хешировать его содержимое ради проверки сохранности.
- Сразу после acquire регистрировать cleanup/finally, включая частичный setup: executor, future, subscription, client, server, file handler. Результат с оставшимся собственным сервером не закончен. Не ослаблять guards или assertions ради запуска.

## Команды и границы

Команды выполнять из корня проекта после назначения изоляции. Их наличие в инструкции — проверенный интерфейс существующих файлов/manifest, не обещание runtime PASS:

```bash
uv run --locked --no-sync pytest tests/test_ytdlp_unit.py -q
uv run --locked --no-sync pytest tests/ -m "not e2e" -q
uv run --locked --no-sync ruff check --select E,F,I <changed-python-files>
uv run --locked --no-sync mypy src/ --ignore-missing-imports
uv run --locked --no-sync python -m scripts.smoke_cli_help
uv run --locked --no-sync python -m scripts.smoke_mcp
uv run --locked --no-sync python -m scripts.smoke_mcp_stdio
uv run --locked --no-sync python -m scripts.smoke_gui
```

Для адресной проверки заменить test path реальным модулем/case; для lint — непустым списком изменённых Python-файлов. `python -m scripts.*` сохраняет корень в module path. Smoke-скрипты назначают ещё более узкие собственные roots до product/Qt/MCP imports, включая `YTDL_DATA_DIR=<smoke-root>/appdata/YTDownloader`; `YTDL_SMOKE_ROOT` может указать существующий owned parent. Каждый override восстанавливается в finally, включая исходное отсутствие env key. Проверять не только child exit0, но и unchanged competing store/artifact set/no-lock при заранее заданном synthetic data root. Synthetic файлы сохраняются. Это не заменяет раннюю изоляцию pytest/его collection. Проверять side effects до исполнения; для changed child/cleanup paths нужен внешний bounded watchdog и проверка фактического выхода своих детей, не только receipt-флага.

- FFmpeg/FFprobe искать через `src.infrastructure.ffmpeg` и существующие fixtures: env → vendor с платформенным именем → PATH. Не hardcode Windows `.exe` для Linux. Если проверяется медиарезультат, читать реальные container/codec/duration через ffprobe, не доверять суффиксу.
- Реальный YtDlpService пишет в `output_root/download-<task_id>/…`. Fixtures для positive/partial/collision и unrelated/newer отрицательных случаев должны действительно достигать нужного namespace, а не проходить лишь из-за outside-root. Для SDK cancellation/final-hook/no-overwrite проверять установленный guard и реальные физические effects/readback; successful hook сам по себе не доказывает принадлежность файла. Мгновенный completion между query selection и mapping проверять на непустом результате из одного snapshot.
- Для S4 deletion основной OS-edge — реальный перенос своих synthetic files в owned recoverable tree с byte readback, не `called`/scripted success. Проверять token/no-token, exact known paths и сохранность unlisted/parent, roots/links/shared/activity, same-name identity replacement, первый move + второй fail и atomic-save failure после moves с cache/disk/reopen/следующей операцией. Папки не очищать. Native Qt capability не доказывает native Trash move/restore; последний может остаться честным NOT_RUN по PLAN S4, без просмотра пользовательской Корзины или permanent fallback. Два legacy API-based confirm без token проверяют настоящий refusal/id/mode и сохранность; positive adapter token wiring — S5, не auto-token в fixture.
- CLI help smoke доказывает разбор/help, не загрузку. MCP discovery/parity доказывает реестр, не side effect. Реальный stdio tool call с синтетическим хранилищем — отдельная полезная integration boundary.
- GUI smoke — только offscreen создание/события/закрытие; без `app.py` с долгим event loop и без заявления о полном интерактивном GUI. В текущем refactor он нужен лишь для сохранности совместимого bootstrap, не для переработки интерфейса.
- Реальные E2E помечены `e2e` и запускаются только с отдельным разрешением и URL. Старые примеры URL не являются разрешением. Полный suite без `-m "not e2e"` по умолчанию запрещён.

## Доказательства и завершение

Сохранять exact command, cwd, версию/базу, fixture/selection, env overrides без секретов, raw exit и наблюдение. Native exit runner-а фиксировать до formatter/pipe. FAILED, PASSED, SKIPPED, deselected, NOT_RUN, blocked и отменённое различать. Пересекающиеся прогоны не складывать как уникальные тесты.

Первый отказ не стирать; отличать дефект приложения от setup/assertion/данных/окружения на основе причины. Старые lint/mypy findings отдельно от новых: baseline должен быть сопоставимым. Ни warning «legacy», ни один passing subset не отменяют новый обязательный провал.

После исходного изменения общего API/владельца состояния/bootstrap выполнять полный offline-suite и затронутые CLI/MCP/совместимые GUI gates. При узком corrective recheck переиспользовать достаточную неизменную часть evidence после сверки source/assertions/env и выполнять только affected regression/gates; не выдавать ранее выполненные suite/type checks за свежий полный прогон. Для локальной правки не повторять весь мир; переиспользовать только evidence с неизменными существенными inputs. Изменённые mapper/fixture/observer требуют affected recheck.

Для логирования нужны одновременно полезный непустой actual output и отсутствие запрещённых synthetic sentinels после flush, по [инструкции логирования](logging.instructions.md). `caplog` и структурная проверка Markdown не заменяют persistent-output proof.

Автор актуализирует контракт/инструкции и освобождает связный кандидат. Независимая приёмка — назначенному Pi Reviewer, не автору. При достаточном результате остановиться; не добавлять бесконечную программу проверок. Эта инструкция не разрешает установку, сеть, выпуск, commit или публикацию.
