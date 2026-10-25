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

## CI isolation — отдельная фаза после provisioning

[Workflow](../workflows/ci.yml) сохраняет Linux/Windows matrix, triggers и прежние
checkout/Python/uv/FFmpeg/dependency installation steps. Они не запускаются агентом
как часть offline-проверки. Затем `Prepare isolated offline checks` (shell Python)
создаёт новый owned root через mkdtemp в RUNNER_TEMP и пишет GITHUB_ENV для следующих
steps: winning YTDL_DATA_DIR, APPDATA/LOCALAPPDATA, HOME/USERPROFILE, temp, XDG config/
data/cache, uv/ruff/mypy caches, logs/smokes, offline/no-sync/no-download/UTF8/
no-bytecode/offscreen/no-track flags. OS essentials не заменяются и не печатаются.

PYTEST_ADDOPTS задаётся целиком, с audited pytestqt.plugin, отключённым plugin
autoload/cacheprovider, `--ignore=tests/downloads`, свежими absolute basetemp/JUnit.
Native paths сериализуются с `/` и shlex.join, включая пробелы. Output default —
созданный synthetic home/Downloads/YTDownloader, а не неработающий YTDL_OUTPUT_DIR.
Продуктовые imports/collection/children offline-фазы начинаются только после этого.
Каждый локальный replay обязан иметь новый root/GITHUB_ENV и собственный bounded
watchdog; не использовать прежний basetemp, private profile или old evidence output.

Изменение процедуры квалифицируется исполнением её actual run bytes и настоящей
API/repository/CLI операцией с competing owned selectors/readback/next writer,
затем фактическими offline commands. YAML parse — только структура. Windows local
runtime не квалифицирует Linux, configured Python3.12, GitHub hosted runner или
remote installation/CI; эти границы указываются отдельно, workflow не dispatch-ится.

S6 independently ACCEPTED в этой offline-границе: actual workflow preparation и
пять последующих команд исполнены на local Windows/Python3.14.2; useful
API/physical media/JSON/readonly CLI/next writer и unchanged competing store
подтверждены отдельно от275-case suite. Hosted CI/Linux/Python3.12/pwsh7 остаются
NOT_RUN. Это применимое evidence для неизменных inputs, не вечный PASS будущих
изменений процедуры и не повод переигрывать принятые S1–S5.

## Команды и границы

Команды выполнять из корня проекта после назначения изоляции. Их наличие в инструкции — проверенный интерфейс существующих файлов/manifest, не обещание runtime PASS:

```bash
uv run --locked --no-sync pytest tests/test_ytdlp_unit.py -q
uv run --locked --no-sync pytest tests/ -m "not e2e" -q
uv run --locked --no-sync ruff check --config pyproject.toml <first-party-python-files>
uv run --locked --no-sync ruff check --select E,F,I <changed-python-files>
uv run --locked --no-sync mypy src/ --ignore-missing-imports
uv run --locked --no-sync python -m scripts.smoke_cli_help
uv run --locked --no-sync python -m scripts.smoke_mcp
uv run --locked --no-sync python -m scripts.smoke_mcp_stdio
uv run --locked --no-sync python -m scripts.smoke_gui
```

Configured first-party gate не заменяется narrow E/F/I: `<first-party-python-files>`
разворачивается в полный заранее проверенный finite manifest отдельных argv по
[quality gates](../../docs/agent-instructions/05-quality-gates.md). Там один владелец
правила scope/PFK; historical S6 lint104 и Q1 first-party106 не смешиваются.

Для адресной проверки заменить test path реальным модулем/case; для lint — непустым списком изменённых Python-файлов. `python -m scripts.*` сохраняет корень в module path. Smoke-скрипты назначают ещё более узкие собственные roots до product/Qt/MCP imports, включая `YTDL_DATA_DIR=<smoke-root>/appdata/YTDownloader`; `YTDL_SMOKE_ROOT` может указать существующий owned parent. Каждый override восстанавливается в finally, включая исходное отсутствие env key. Проверять не только child exit0, но и unchanged competing store/artifact set/no-lock при заранее заданном synthetic data root. Synthetic файлы сохраняются. Это не заменяет раннюю изоляцию pytest/его collection. Проверять side effects до исполнения; для changed child/cleanup paths нужен внешний bounded watchdog и проверка фактического выхода своих детей, не только receipt-флага.

- FFmpeg/FFprobe искать через `src.infrastructure.ffmpeg` и существующие fixtures: env → explicit/default vendor с платформенным именем → PATH. Для frozen onedir default vendor идёт от resolved реального EXE, не cwd/_internal/_MEIPASS; source-root policy сохранена. Не hardcode Windows `.exe` для Linux. Если проверяется медиарезультат, читать реальные container/codec/duration через ffprobe, не доверять суффиксу.
- Реальный YtDlpService пишет в `output_root/download-<task_id>/…`. Fixtures для positive/partial/collision и unrelated/newer отрицательных случаев должны действительно достигать нужного namespace, а не проходить лишь из-за outside-root. Для SDK cancellation/final-hook/no-overwrite проверять установленный guard и реальные физические effects/readback; successful hook сам по себе не доказывает принадлежность файла. Мгновенный completion между query selection и mapping проверять на непустом результате из одного snapshot.
- Для S4 deletion основной OS-edge — реальный перенос своих synthetic files в owned recoverable tree с byte readback, не `called`/scripted success. Проверять token/no-token, exact known paths и сохранность unlisted/parent, roots/links/shared/activity, same-name identity replacement, первый move + второй fail и atomic-save failure после moves с cache/disk/reopen/следующей операцией. Папки не очищать. Native Qt capability не доказывает native Trash move/restore; последний может остаться честным NOT_RUN по PLAN S4, без просмотра пользовательской Корзины или permanent fallback. No-token compatibility cases проверяют настоящий refusal/id/mode и сохранность; S5 positive CLI/MCP/GUI cases передают ровно token своего preview, без auto-token/bypass в fixture.
- S5 connected cases используют настоящий CLI subprocess/parser/bootstrap/API/repositories, acceptance до release и terminal/persistence/native exits; borrowed CLI не закрывает runtime. Реальный SDK stdio проверяет useful tools/token/reopen/EOF; managed loopback HTTP — disconnect versus cancel, stop/join/port reuse/foreign bind. Qt cases исполняют настоящие existing controls/signals/modal, settings и startup cleanup. Это offline edge-substituted proofs, не live/codec/visual qualification.
- При logging ownership проверять SAME early/late caller objects, streams, registration и before/during/after file bytes; finally закрывает только acquired handlers. Нужны normal/body/owned-cleanup-error и actual partial-open failure с последующей полезной операцией/writer. Не восстанавливать caller созданием нового FileHandler(mode='w') и не ослаблять assertions.
- CLI help smoke доказывает разбор/help, не загрузку. MCP discovery/parity доказывает реестр, не side effect. Реальный stdio tool call с синтетическим хранилищем — отдельная полезная integration boundary.
- GUI smoke — только offscreen создание/события/закрытие; без `app.py` с долгим event loop и без заявления о полном интерактивном GUI. В текущем refactor он нужен лишь для сохранности совместимого bootstrap, не для переработки интерфейса.
- Реальные E2E помечены `e2e` и запускаются только с отдельным разрешением и URL. Старые примеры URL не являются разрешением. Полный suite без `-m "not e2e"` по умолчанию запрещён.

## Console onedir: отдельная native-граница Q2

Сборка/guards описаны в [build instructions](build_system.instructions.md).
Standalone EXE не равен Python entry или source-tree smoke. Квалифицируется весь
manifest-bound onedir, не один файл: полный relative member/type/size/hash set,
existing FFmpeg/FFprobe/licenses/provenance, canonical imports/registrars. Только
новые собственные внешние work/dist/relocation paths, без clean/replacement,
установок/скачивания. Relocation — отдельная папка с пробелами и ещё один cwd.

Для **нового изменённого** artifact разрешённая проверка из готовой `.venv`, после
всех pre-import selectors выше, выглядит так (пути заменить своими новыми owned):

```powershell
uv run --locked --no-sync python -m scripts.smoke_cli_exe --exe 'C:\OwnedPackage\YTDownloadCLI\ytdl.exe' --work-root 'C:\OwnedChecks\q2-native-new'
```

Это не harmless help: default выполняет queries/deletions/media/servers, создаёт
own synthetic stores/media, обращается к native Trash только на tiny own fixture,
использует настоящий EXE/yt-dlp/own loopback HTTP и SDK. До повторного использования
прочитать verifier. Ему нужен независимый outer deadline/native identity/handle
observer и finally/join; внутренние timeouts/receipt-флаги не заменяют наблюдение
реального выхода. Windows Ctrl+C controller действует только на собственную вновь
созданную console, не чужие окна/процессы. Никакого Bin inspection/permanent fallback.

Child environment — OS essentials и owned roots без dev Python/.venv/uv/checkout/
FFmpeg PATH, PYTHONPATH/PYTHONHOME/VIRTUAL_ENV/YTDL_FFMPEG_* assistance. Для SDK stdio
проверять actual spawned argv/env, не только constructor options. Source Python
может подготовить labelled fixture и наблюдать клиент, но не подменять EXE/API.
`--sections queries media servers` — полный набор; выбор `--sections servers`
не проверяет остальные phases, они остаются NOT_RUN в этом receipt.

Q2 независимо принят: fresh full native71-row aggregate/all11 leaves и8 отдельных
complementary commands, physical MP4 MPEG-4+AAC / AAC-M4A audio-only, real persistence/
reopen/404 failure; offline308/7 e2e deselected/0 skipped, affected42, mypy0/68,
configured1090, changed6 E/F/I0, четыре source module smokes0. Пересечения не
складываются. HTTP Ctrl+C — native1/INTERRUPTED со stop/port reuse/next owner,
stdio EOF — native0. Native Trash — PARTIAL_DELETE/TRASH_UNAVAILABLE UNKNOWN:
source исчез/history сохранена, recoverability/restore не проверены; keep-files
отдельно сохранил реальные recorded files. Не ретраить неизвестный эффект вслепую.

Local fixture не YouTube/720p/remote sidecar proof. External gate —
WAITING_FOR_USER_URL / NOT_RUN, без выбора sample/solver download. GUI build/visual,
иные платформы/hosted CI/optional extras/whole legacy privacy/legal redistribution
не квалифицированы. Уже принятые runtime gates не повторяются ради документации,
Git или ZIP recontainer тех же payload bytes: проверяются affected final docs,
полный ZIP member/SHA/CRC set и неизменность accepted source/artifact.

## Доказательства и завершение

Сохранять exact command, cwd, версию/базу, fixture/selection, env overrides без секретов, raw exit и наблюдение. Native exit runner-а фиксировать до formatter/pipe. FAILED, PASSED, SKIPPED, deselected, NOT_RUN, blocked и отменённое различать. Пересекающиеся прогоны не складывать как уникальные тесты.

Первый отказ не стирать; отличать дефект приложения от setup/assertion/данных/окружения на основе причины. Старые lint/mypy findings отдельно от новых: baseline должен быть сопоставимым. Ни warning «legacy», ни один passing subset не отменяют новый обязательный провал.

После исходного изменения общего API/владельца состояния/bootstrap выполнять полный offline-suite и затронутые CLI/MCP/совместимые GUI gates. При узком corrective recheck переиспользовать достаточную неизменную часть evidence после сверки source/assertions/env и выполнять только affected regression/gates; не выдавать ранее выполненные suite/type checks за свежий полный прогон. Для локальной правки не повторять весь мир; переиспользовать только evidence с неизменными существенными inputs. Изменённые mapper/fixture/observer требуют affected recheck.

Для логирования нужны одновременно полезный непустой actual output и отсутствие запрещённых synthetic sentinels после flush, по [инструкции логирования](logging.instructions.md). `caplog` и структурная проверка Markdown не заменяют persistent-output proof.

Автор актуализирует контракт/инструкции и освобождает связный кандидат. Независимая приёмка — назначенному Pi Reviewer, не автору. При достаточном результате остановиться; не добавлять бесконечную программу проверок. Эта инструкция не разрешает установку, сеть, выпуск, commit или публикацию.
