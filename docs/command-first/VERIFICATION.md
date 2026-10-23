---
id: ytdl-command-first-verification
title: "YTDownload — фактическая проверка command-first"
kind: verification
status: accepted
created: "2026-10-23"
updated: "2026-10-23"
areas: [testing, isolation, logging, compatibility]
summary: "Независимо принят только S1: isolated offline baseline, log-root/fixtures и bounded smokes; история авторских проверок и явные пределы S2–S6."
code_ref: "0abda8e2959b53561e8327f40c53118c944c94f8"
code_verified_at: "2026-10-23"
verification_scope: "S1 на базе 0abda8e в refactor/command-first; Python candidate bytes сохранены неизменными при независимом review. Документационное завершение отдельно от runtime проверки; S2–S6 не приняты."
related: [ytdl-command-first-plan, ytdl-command-first-contract]
---

# S1 — изолированный исполняемый baseline

## Авторская стадия — 2026-10-23, до независимой приёмки

Следующие разделы сохраняют **авторские проверки, на момент передачи не ACCEPTED**.
Тогда [PLAN §5](PLAN.md) и [CONTRACT](CONTRACT.md) не менялись; S2–S6 не были реализованы.
База — указанный HEAD, ветка `refactor/command-first`. Унаследованные документы и
методический пакет сохранены; автор не stage/commit/push. Позднейшая независимая
приёмка и документационный sync записаны отдельно ниже, не заменяют исходные receipts.

## Что изменено

- `setup_logging`: явный `log_dir` → непустой `YTDL_LOG_DIR` → прежний checkout
  `logs/`. Default stream по-прежнему stdout; CLI сам передаёт stderr либо свой
  JSON-buffer. Formatter, уровни, force-reconfiguration и ротация не изменены:
  `app.log` 10 MiB × 5 backup, `app.error.log` 5 MiB × 3 backup.
- Три simulated-POSIX fixture проверяют настоящие finder wrappers, игнорирование
  vendor `.exe`, аргумент resolver-а и выбранный путь. Подменён только
  host-specific `shutil.which`; platform namespace локален модулю и не меняет
  host `pathlib`. Настоящий native-PATH fallback test сохранён без изменения логики.
  Продуктовый порядок env → vendor → PATH не менялся.
- Synthetic media fixture использует встроенный MPEG-4 и AAC вместо недоступного
  libx264; ошибка генерации теперь FAILED, не SKIPPED. Настоящий FFprobe проверяет
  MP4, video codec/dimensions, audio codec/sample-rate/channels и длительность.
- Новые characterization tests проходят настоящие API/coordinator/JSON owners:
  query defaults/order/filter/serialization, description readback, settings defaults
  и reopen, API defaults против текущих settings-derived defaults GUI-owner-а.
  Только внешний download backend заменён синтетическим. Это не Qt-action E2E и
  не доказательство проигрываемости boundary-artifact из coordinator test.
- Четыре smoke импортируют приложение/Qt/MCP после назначения собственных roots.
  Общий маленький helper восстанавливает окружение и закрывает созданные handlers;
  synthetic файлы сохраняются, не удаляются. Текущий coordinator явно joined через
  его executor: legacy `shutdown(wait=False)` не считается завершённым shutdown.
- CLI help children используют текущий interpreter, inherited isolated env и timeout
  20 s. Discovery ограничен 20 s. Stdio использует текущий interpreter, явный env,
  `keep_alive=False`, timeout 30 s и finally close с отдельным cleanup-limit 10 s.
  Его child вызывает настоящий CLI `main(["server", "stdio"], services=...)` с
  собственными services и finally join; не запускает uv/sync/install. После EOF
  проверяется отдельный child cleanup receipt. Это **реальный stdio discovery**, но
  не доказательство lifecycle неизменённого standalone CLI entrypoint.
- GUI smoke: offscreen construction/show/processEvents/close, снятие подписок и
  deferred deletion даже при частичном конструкторе; затем join координатора.
  Исходники/дизайн GUI не изменялись. `tests/conftest.py` также не менялся.

## Изоляция и evidence

До **каждого** исполняемого test/import процесса задавались новые принадлежащие
прогону APPDATA/LOCALAPPDATA, HOME/USERPROFILE, TMP/TEMP/TMPDIR, cache/output/log
roots; системные PATH/SYSTEMROOT/WINDIR/COMSPEC сохранены. Default output через
`Path.home()` тоже synthetic. `YTDL_OUTPUT_DIR` не объявляется реализованным
продуктовым override: существующий default следует переназначенному home, а
worker tests передают явный `AppSettings(output_dir=...)`.

Использована готовая Windows `.venv`, Python 3.14.2, `uv run --locked --no-sync`,
`UV_OFFLINE=1`, `UV_NO_SYNC=1`, `UV_PYTHON_DOWNLOADS=never`.
Plugin autoload выключен; явно загружен `pytestqt.plugin`, cacheprovider выключен,
у каждого запуска новый `--basetemp`. Это env/runner isolation **до collection**,
не защита одним test `tmp_path` и не monkeypatch продуктового logging setup.

Exact команды, overrides, raw outputs/exits, starting bytes, per-run hashes и frozen
manifest сохраняются владельцами проверки отдельно от Git. Их временные абсолютные
пути, логи и fixture-деревья не являются публикационным payload. Первичный авторский
manifest SHA256: `09e74440c25a557cc919a34b8b304efda04cb3968476c3a2cf828249c3c59d1c`;
он фиксирует исходные 10 Python paths и первоначальную редакцию этого отчёта,
а не позднейший документационный sync. Текст отчёта не заменяет независимую проверку.

## Выполнено

Все команды ниже запускались через описанное pre-import окружение, из корня.
Пересекающиеся прогоны не складываются как уникальные тесты.

| Проверка | Raw exit | Наблюдение |
|---|---:|---|
| Исходные FFmpeg/detection tests | 1 | 21 passed, 3 failed, 1 skipped; те же три Windows fixture failures |
| Новый адресный RED до правок реализации | 1 | Отсутствующий env log-root; native FFmpeg `3165764104`, Unknown encoder libx264; сохранены также авторские fixture/oracle ошибки |
| Финальные logging assertions над сохранёнными pre-fix implementation bytes | 1 | 1 failed, 3 passed; чистый RED именно env log-root, без teardown errors |
| `uv run --locked --no-sync pytest tests/test_logging_setup.py tests/test_ffmpeg_detection.py tests/test_ffmpeg.py tests/test_command_first_characterization.py -q -rs` | 0 | **34 passed**, без skips; characterization после исправления авторского имени DTO-поля изначально GREEN, не product RED |
| `uv run --locked --no-sync pytest tests/ -m "not e2e" -q` | 0 | **111 passed, 7 deselected**, без skips; без Oracle logging-redirect wrapper |
| `uv run --locked --no-sync ruff check --select E,F,I` с 10 фактически изменёнными Python paths | 0 | All checks passed |
| `uv run --locked --no-sync mypy src/ --ignore-missing-imports` | **1** | **35 errors / 16 files**, 59 checked; вывод byte-for-byte совпадает с Oracle baseline, не type PASS |
| `uv run --locked --no-sync python -m scripts.smoke_cli_help` | 0 | 5 help cases; не download/command effects |
| `uv run --locked --no-sync python -m scripts.smoke_mcp` | 0 | 10 tools; без запуска HTTP |
| `uv run --locked --no-sync python -m scripts.smoke_mcp_stdio` | 0 | 10 tools через настоящий stdio client/child; EOF cleanup receipt подтверждён |
| `uv run --locked --no-sync python -m scripts.smoke_gui` | 0 | Offscreen window/events/close; не `app.py` HTTP lifecycle |
| Дополнительные узкие author failure-path probes | 0 | 5 passed: discovery setup/mismatch, частичный GUI constructor, stdio mismatch, CLI help mismatch; cleanup/env restoration проверены |
| Actual sink/media readback probe | 0 | Непустые реальные main/error files и stderr после flush; FFprobe native 0, MPEG-4 320×240, AAC mono 44100 Hz, 1 s |

Из 7 deselected все находятся в `tests/test_download_e2e.py`:
`test_fetch_info_video`, `test_fetch_info_playlist`, `test_download_720p`,
`test_download_audio_only`, `test_download_with_description`,
`test_download_playlist_first_item`, `test_coordinator_queue_while_downloading`.
Причина — opt-in `e2e`, нет разрешения/конкретного URL; deselection не PASS.
Исходный media skip устранён, новых skips нет.

Первые авторские logging-fixture teardown errors (phase-local stderr capture),
ошибочное DTO-поле `text` вместо `description_text`, последующая host Path-flavour
ошибка fixture и два narrow E501 сохранены с исходными exits; исправлены без
ослабления предметных assertions. Счёт baseline `69 ruff findings` принадлежит
Oracle: полный ruff в S1 повторно не запускался. Mypy проверен заново и остался
**красным**, но новых owned findings нет; чужой baseline-долг не исправлялся.

## Пределы и передача

- Это proof path-selection/nonempty log sinks, **не privacy-filter/redaction proof**.
  Фильтр не добавлен, инъекция raw URL/proxy/exception с обещанием очистки не
  проверялась. Полная logging/privacy-chain проверка остаётся последующим срезам.
- Oracle cancellation RED сохранён неизменным для S3; incorrect cancelled/done
  behavior не зафиксировано как желаемое. Coordinator/backend/repositories/API
  source в S1 не менялись.
- Libx264 support не появился; vendor binaries не менялись. Нативное Linux
  исполнение и Windows-fixture simulation — разные границы.
- Все собственные executor/client/stdio process/Qt subscriptions/window resources
  завершены на достигнутых путях. Synthetic evidence оставлено намеренно. Это не
  новая продуктовая гарантия runtime close и не проверка active-download shutdown.
- **Авторский NOT_RUN на момент передачи:** live YouTube/network E2E, реальные download/cancel effects через MCP,
  connected S2–S6 schedules, managed HTTP / `app.py` server lifecycle, native Trash,
  Linux runtime/CI, packaged EXE, visual/manual GUI, полный legacy privacy audit,
  независимая приёмка. Ни установки, ни изменения lockfile/ignore, ни коммиты не
  выполнялись.

## Независимая стадия — 2026-10-23

**Verdict: ACCEPTED только S1.** Проверены фактический diff/новые файлы,
definitions/consumers, сохранность product precedence, реальные API/coordinator/JSON
связи characterization и безопасность добавленных scripts. Не требовались будущие
S2–S6 как gate S1. API/coordinator/backend/repositories и conftest не изменялись;
Oracle cancellation RED не переисследовался и не закреплён как желаемое поведение.

До запусков независимо сверены все 11 frozen paths и SHA первичного manifest,
созданы собственные immutable copies/архив. Runtime Python bytes оставались теми же
во время всех проверок и последующего docs-only завершения. Reviewer использовал
новые собственные roots; авторские runtime outputs не засчитывались как свежий PASS.

| Свежая независимая проверка | Raw exit | Наблюдение / граница |
|---|---:|---|
| Адресные logging/detection/FFmpeg/characterization tests | 0 | **34 passed, 0 skips** |
| `uv run --locked --no-sync pytest tests/ -m "not e2e" -q` | 0 | **111 passed, 7 deselected, 0 skips**; JUnit node IDs сохранены отдельно |
| `ruff check --select E,F,I` всех 10 изменённых Python paths через locked/no-sync | 0 | Новых обязательных lint findings нет |
| `mypy src/ --ignore-missing-imports` через locked/no-sync | **1** | Exact output byte-for-byte равен Oracle: **35 errors / 16 files**, не type PASS |
| Четыре `uv run --locked --no-sync python -m scripts.smoke_*` | 0 каждый | CLI 5 help cases; MCP 10 tools; настоящий stdio discovery/EOF; offscreen GUI, не HTTP/visual |
| Те же 5 адресных failure-injection cases в новом дереве | 0 | Реальный setup/discovery/GUI constructor/help/stdio mismatch cleanup, не ещё 5 уникальных продуктовых tests |
| Независимый sink/media readback | 0 | Actual default stdout и explicit stderr раздельными OS pipes; main files по 194 bytes, error по 100; native FFprobe 0: MPEG-4 320×240 + AAC mono 44100 Hz, MP4 1.000000 s |

Все перечисленные процессы имели внешний 100 s Windows Job watchdog. Он не
сработал; до закрытия own Job не осталось активных PID, наблюдавшиеся handles
подтвердили фактический выход. В stdio, включая mismatch, проверены и child finally
receipt, и actual process exit; это не сертификат standalone CLI shutdown/active
backend cancellation. Существующие `StdioTransport` env/keep_alive/close declarations
также сверены с установленной зависимостью.

Независимые observer errors сохранены отдельно: первый MSYS tar вызов raw128
неверно трактовал drive-colon; исправлен только `--force-local`. Первые два pytest
прогона raw0 использовали Windows backslashes в ADDOPTS, которые tokenizer убрал;
они создали только собственные synthetic basetemp-деревья в неверном месте.
Деревья перенесены без удаления, runner исправлен на `/` с проверкой resolved root,
и затронутые selection/failure cases повторены с результатами выше. Первый media
readback raw1 был missing-fixture-path observer assertion; после верного isolated
pytest-tree тот же media oracle прошёл. Product/test assertions не ослаблялись и
кандидат ради этих ошибок не менялся.

### Документационное завершение и остаток

Тот же Reviewer согласовал foundation entry/философию, инструкции testing/logging,
module/no-sync команды 02/04/README, текущие storage/default/delete/privacy сведения
руководства и навигацию PLAN/CONTRACT/этого отчёта. Отдельный прямой проектный grant
на selective commit/push уже принятого среза отражён в AGENTS/agent-team/PLAN/gates;
это не разрешение на main/force/tags/release, установку или live E2E. Исторические
Oracle/author результаты сохранены как стадии, а не переписаны в новый PASS.

**Остаётся NOT_RUN/не принято:** S2–S6 и весь предлагаемый runtime contract;
полная privacy/redaction-chain; forced rollover; канонический standalone CLI/HTTP
lifetime и реальные MCP tool effects; native Trash; live YouTube; Linux runtime/CI;
packaged EXE и визуальный/ручной GUI. Full Ruff69 — переиспользованный Oracle
baseline, не свежий прогон. Новых owned type failures нет, глобальный mypy RED не скрыт.

Документальные gates после sync: read-only PFK project checker — raw0, 18 явно
выбранных Markdown документов, findings0; pack checker — raw0, 71 текстовый input,
8 `not_checked` (3 Obsidian views и 5 wiki-link sources), не renderer/сетевая проверка.
Полный импорт сравнен побайтно с предоставленным локальным PFK 0.3.0: **74/74 файла**,
включая LICENSE/UPSTREAM/оба donor notices; исходный и импортированный пакеты не
редактировались. Existing doc/manifest regression — raw0, **4 passed**, assertions
и code/tests не менялись. Это структурные/адресные checks, не повторный product PASS.

Состояние публикации и remote CI сообщаются отдельно после exact commit/ref readback;
этот отчёт не обещает CI PASS. Дальнейший срез — S2 по PLAN и назначенному циклу,
без повторной приёмки неизменённых уже принятых S1 bytes.

# S2 — авторский кандидат runtime / persistence ownership

## База и граница — 2026-10-23

**READY_FOR_REVIEW, не независимый ACCEPTED S2.** Принятый S1 выше не переоткрыт.
Новая база — `813f2b357c029b331ebf1483eb34022853f0cb8b`, ветка
`refactor/command-first`; исходный main `0abda8e` остаётся отдельным историческим
baseline. Прямой grant `YTDL_REVIEW_FINISH_20261023` применён: Coder не владеет
index/commit/push; после независимого принятия документационное завершение и
selective Git-доставка принадлежат тому же Reviewer. В этом авторском S2 commit,
push и изменения main не выполнялись. PLAN/CONTRACT, инструкции и pack не менялись.

## Реализовано и наблюдалось

- `src/bootstrap.py::create_runtime`: явный canonical root → `YTDL_DATA_DIR` →
  APPDATA/YTDownloader → home/YTDownloader. Пустые env roots не выбирают cwd.
  Явные settings overrides и backend/remover factories; default yt-dlp импортируется
  лениво только фабрикой исполнения. Создание API/runtime не настраивает logging,
  не открывает окно/порт. `main.initialize_app` делегирует и сохраняет все прежние
  keys, добавляет runtime; оба facade aliases указывают на один API.
- Application/domain больше не импортируют concrete yt-dlp infrastructure.
  Используется существующий `IDownloadService`; legacy result type исправлен на
  path-map с `list[Path]` для subtitles. Typed completed/cancelled/failed outcome
  и backend mapping всё ещё S3, а не второй параллельный протокол.
- `ApplicationRuntime`: owned/borrowed lifetime, admission guard, explicit close,
  detached settings, settings save до публикации новых defaults, context manager.
  Owned join освобождает ресурсы; `wait=False` сохраняет lease, пока не выполнен
  реальный join. Borrowed wrapper не закрывает coordinator/ресурсы caller-а.
  Переходный executor shutdown hook сохраняет реальный cleanup существующих S1
  smoke consumers, без GC/finalizer и без изменения их source.
- Exclusive stdlib OS lease на canonical data root получена **до** загрузки mutable
  caches. Второй настоящий writer process получает OWNER_BUSY без изменения store;
  read-only процесс одновременно читает snapshot. После реального close следующий
  процесс открывает тот же root. Lock-файл не unlink-ается. Mutation guard не даёт
  старой repo-reference писать после освобождения lease и ждёт начатую запись.
- JSON adapters: same-dir own temp → flush/fsync/close → atomic replace → detached
  cache. При injected отказе до replace прежние disk bytes и memory snapshot
  остаются прежними, возвращается PERSISTENCE_FAILED. Повреждённый JSON сохраняется
  и отвергается с STORAGE_CORRUPT, не превращается в defaults. Отсутствующий store
  и повреждённый — разные случаи. Чтения/записи не отдают mutable cache objects.
  Собственные failed temp-файлы сохраняются; их handles закрыты, автоматического
  обхода/удаления таких файлов не добавлено. Media+JSON транзакция не обещается.
- Recovery только после writable lease: queued/downloading/merging → failed с
  INTERRUPTED, безопасным сообщением/временем. Terminal records и реальные synthetic
  media/.part bytes не изменены, backend/replay/cleanup не запускались. Read-only
  не пишет/не восстанавливает/не создаёт lease или executor; отсутствующий root не
  создаётся. Ошибка recovery/corrupt startup/factory setup освобождает acquired
  resources, и следующий writer после исправления только своей fixture открывается.
- Один pure domain owner URL/quality/type/flag/settings normalization. Explicit
  CLI/MCP defaults 720p/video/False сохранены; local None берётся из settings,
  False не превращается в True; audio defaults и explicit audio проходят то же
  правило. Admission persistence error не публикует task/acceptance и не вызывает
  backend; следующий запрос работает, допустимые gaps ID не превращаются в дубли.
- Общие settings/history фасады, конкретные command return types, безопасные error
  codes; bool ID не читает запись 1. Исправлена потеря description_path в details/
  file-path DTO, настоящий sidecar прочитан после reopen. Добавлены backward-readable
  `HistoryEntry.output_root` и `error_code`; artifact_paths attribution остаётся S3.
- Изменённые repository/backend-error emitters проверены через реальные file/error
  handlers и отдельный stderr pipe: непустые ID/reason codes присутствуют, synthetic
  URL/proxy/title/path/exception markers отсутствуют. Это локальная проверка safe
  emitters, **не** новый privacy-filter или аудит всей legacy logging chain.

## Проверки S2

Применён тот же pre-process isolation contract: собственные APPDATA/LOCALAPPDATA,
HOME/USERPROFILE, TMP/TEMP/TMPDIR/cache/log/output roots до import/collection/children;
existing `.venv` Python 3.14.2, offline/locked/no-sync/no-download, no-bytecode/UTF8,
offscreen/no-updates/no-track. `PYTEST_ADDOPTS` использует абсолютный forward-slash
basetemp, resolved root проверен до процесса. Неаудированные plugins не загружаются.

Final gates и новые process/cleanup proofs дополнительно выполнялись под bounded
100 s Windows Job watchdog, применённым только к собственному subprocess tree.
Он не сработал; перед закрытием Job живых own PID не было, наблюдённые handles
подтвердили выход. У stdio final gate наблюдено 6 own processes, все native exit0.
Source/assertion hashes, JUnit node IDs, child stdout/stderr/native exits и exact
env/commands сохранены в локальном S2 evidence, не в Git.

| Проверка | Raw exit | Факт / граница |
|---|---:|---|
| Repository regression до реализации | 1 | **7 failed, 2 passed**: cache aliasing, suppress write failure и corrupt-as-default; те же assertion bytes затем GREEN |
| Metadata persistence regression до узкого исправления | 1 | **1 failed**: StorageError ошибочно принимался за optional fetch failure; реальный код продолжал download и не сообщал persistence_error_ids |
| `uv run --locked --no-sync pytest tests/test_repository_ownership.py tests/test_application_runtime.py tests/test_core_import_boundary.py -q -rs` | 0 | **38 passed**, 0 skips; реальные repositories/runtime/processes, не prebuilt success |
| Адресные existing API/query/command/model/characterization cases | 0 | **58 passed**, перекрываются с full suite; граница fake backend только внешняя |
| `uv run --locked --no-sync pytest tests/ -m "not e2e" -q` | 0 | **149 passed, 7 deselected, 0 skips** на финальных S2 Python bytes |
| `uv run --locked --no-sync ruff check --select E,F,I` + все 22 изменённых Python paths | 0 | All checks passed |
| `uv run --locked --no-sync mypy src/ --ignore-missing-imports` | **1** | **34 errors / 15 files**, 65 checked; новых findings нет, старый nullable executor finding устранён его S2 typing seam; не type PASS |
| Четыре `uv run --locked --no-sync python -m scripts.smoke_*` | 0 каждый | CLI help 5; MCP discovery 10; настоящий stdio discovery/EOF 10; offscreen GUI, не HTTP/visual/tool-effect E2E |

Fresh import-boundary children запрещали PySide/Qt, FastMCP, uvicorn, argparse,
yt-dlp и выполняли полезный direct query/sidecar read; отдельный composed writable
child прошёл API → настоящий coordinator/repositories → injected backend artifact →
close → fresh readback, не создавая QApplication. Настоящие first/second/read-only/
next writer processes имеют отдельные сохранённые receipts с native exit0;
OWNER_BUSY проверен как прикладной refusal, а не выведен из одного shell exit.

Metadata fault исправлен **до** download-stage повторным пробросом StorageError,
не ослаблением теста. Сохранились exact RED/финальные GREEN assertions и cleanup.
Терминальная сохранённость после media effect и полный outcome/cancellation state
machine этим случаем не аттестованы — они относятся к S3.

Семь e2e cases перечислены в S1 выше; markers/отказы от реальной сети сохранены.
В `tests/test_download_e2e.py` сделана только сигнатурная совместимость factory/
AppSettings arguments и соответствующих imports, assertions не переписаны; тела
live tests **NOT_RUN**. Существующий S1 characterization изменил только boundary
injection вместо concrete-backend monkeypatch, его assertions сохранены.
Пересекающиеся 38/58/149 не суммируются как уникальные tests.

Первый S2 lint выявил owned formatting/import findings и существующие e2e signature-
связанные unused settings/imports; необходимые argument adaptations исправлены без
общего cleanup baseline. Четыре первых новых Windows mypy findings по Unix fcntl
ветке устранены штатным `sys.platform` guard, не suppress/ignore. Финальный mypy
сопоставлен по location/cause с Oracle35: только удалённый старый executor finding,
новых нет. Full Ruff69 не переисполнялся и не объявляется свежим PASS.

## Оставшиеся границы и передача

S3 ещё должен завершить cancellation/terminal outcomes, task/live DTO overlays,
future/event ordering, controlled pool-cap change after drain и полные shutdown
schedules. В S2 pool сохраняет первоначальный cap, а новые defaults фиксируются
per admission; unsafe replacement работающего executor не используется. Default
close cancel=True пока вызывает legacy cancel path, не доказывая его правильность;
S2 ownership proofs используют explicit drain cancel=False и настоящий join.

S4 deletion policy/Trash/token и S5 CLI/MCP/GUI ownership wiring не реализованы.
Remover port/factory — только injection seam, новая операция удаления не включена.
Legacy destructive delete не объявлен безопасным. CLI/MCP transports, GUI, backend
mapping/cancellation, EventBus, smokes, lockfile/dependencies и pack не редактировались.

**NOT_RUN:** независимая S2 приёмка; S3–S6 connected schedules; live YouTube/network
E2E, native Trash, managed HTTP/app.py server lifecycle, canonical standalone CLI
active-job lifetime, Linux runtime/CI, package/EXE, visual/manual GUI, полный legacy
privacy audit. Publication/remote CI S2 не запускались Coder-ом. Исходные Oracle,
author S1 и Reviewer S1 artifacts неизменны. Exact frozen S2 manifest/report переданы
Hermes для того же независимого Reviewer; это не само-ACCEPT и не начало S3.

# S2-R1 — узкий авторский integration repair

Исходный S2 получил независимый **NEEDS_CHANGES**, не ACCEPTED: inherited
`YTDL_DATA_DIR` обходил более узкое smoke-поддерево. Настоящий MCP smoke возвращал
exit0, но выполнял законный writable recovery синтетического competing profile.
Исторический S2 кандидат/отчёт и independent RED сохранены неизменными. Следующий
результат — **repair READY_FOR_REVIEW**, не итоговая приёмка всего S2.

Изменены только `scripts/smoke_support.py`, `tests/test_application_runtime.py` и
этот append-only раздел. В существующий общий `paths` добавлен `YTDL_DATA_DIR =
root/appdata/YTDownloader` до application imports. Существующий finally теперь
сохраняет/восстанавливает и этот env key. Product root precedence, recovery,
coordinator/repositories, adapters и все остальные original S2 bytes не менялись;
второй bootstrap/mode/runner в продукте не добавлен.

На неизменённом helper получены два свежих содержательных RED в новых полностью
синтетических roots: копия immutable reviewer control и новый genuine smoke
subprocess regression, raw1 каждый. В обоих actual smoke child native0/10 tools,
но история queued→failed/INTERRUPTED, появился lock. После одно-строчного исправления
тот же control — raw0: id9 остался queued, history bytes идентичны, lock не появился.
Регрессия дополнительно проверяет точную неизменность набора store artifacts.

| Fresh delta check | Raw exit | Наблюдение |
|---|---:|---|
| Reviewer control, rebound только на новый author root, RED → GREEN | 1 → 0 | Actual smoke child0; unchanged history/no-lock invariant восстановлен |
| Новая genuine-smoke regression + present/absent env × normal/exception restoration | 0 | **5 passed**, реальные runtime/lease и file-handler resources закрыты, прежний env восстановлен |
| `uv run --locked --no-sync pytest tests/test_application_runtime.py -q -rs` | 0 | **30 passed**,0 skips на финальных repair bytes; старые assertions сохранены |
| Четыре `uv run --locked --no-sync python -m scripts.smoke_*` | 0 каждый | CLI help5, MCP10, actual stdio discovery/EOF10, offscreen GUI |
| `uv run --locked --no-sync ruff check --select E,F,I scripts/smoke_support.py tests/test_application_runtime.py` | 0 | Одна первоначальная E501 исправлена только переносом строки assertion, без изменения oracle |

До imports/collection/children назначены own home/appdata/temp/cache/log/output/
YTDL_DATA_DIR, offline/no-sync/no-download/UTF8/no-bytecode/offscreen flags. Competing
profile тоже целиком synthetic; рабочий профиль не читался. Абсолютный forward-slash
basetemp проверен. Независимый от изменяемого helper bounded100s Job supervisor
подтвердил actual own process exits и отсутствие live own PID до закрытия Job;
watchdog emergency cleanup не потребовался. Для stdio наблюдены6 процессов native0.

Прежние независимые38/149, storage/core/lease/type34 и accepted S1/pack результаты
**retained**, не свежий повтор. Полный offline149, mypy и широкие baseline/core/pack
матрицы ради этой delta не запускались. 5/30 и пересекающиеся smokes не суммируются.
Остаток S3–S6, live E2E/HTTP/native Trash/Linux/package/visual/privacy пределы не
изменены. Commit/push Coder не выполнял. Complete successor manifest и raw/node/source
receipts переданы Hermes в новом repair evidence root. Тот же Reviewer должен
проверить достаточную delta и дать текущий whole-S2 verdict, затем при ACCEPTED
выполнить документационное завершение и разрешённую selective Git-доставку.

# S2 — независимая приёмка coherent successor после R1

**ACCEPTED только S2 в границах PLAN.** Это итог для successor с первоначальными
S2 owners и узким helper repair, не отдельное принятие только одной строки.
Первоначальный NEEDS_CHANGES и все RED/observer receipts сохранены исторически;
они не переписаны в PASS. S1 и полный PFK не принимались/импортировались повторно.

Идентичность runtime-кандидата: primary SHA256
`d3edc43a3774c4368463a6bbcdbfaa6a78f4898e60f32efbb870fbbbd5f67eed`, база
`813f2b357c029b331ebf1483eb34022853f0cb8b`, 24 paths. Из исходного S2 **21 путь
побайтно неизменен**; в runtime tests сохранены прежние definitions/assertions/
decorators AST, добавлены только две definitions/пять cases и необходимые imports.
Helper изменён ровно одним root override; product priority/recovery не изменялись.
Весь прежний VERIFICATION сохранён как byte prefix; этот вывод — отдельная стадия.

## Закрытие R1 и fresh delta

Настоящий control с pre-existing synthetic YTDL_DATA_DIR и child
`python -m scripts.smoke_mcp` теперь даёт raw0/native child0/tools10. Сохранены
история id9 queued/error_code=None, точные bytes, полный artifact map и отсутствие
нового lock в competing profile. Before/after SHA256 одинаков:
`2ac4c771c03df0911257dadf01c09f0f6214f6e2b7ac034b531a8b9e5c2af81e`.
Это проверка сохранности вместе с настоящим успехом smoke, не child-exit-only proof.

| Свежая независимая проверка | Raw exit | Граница |
|---|---:|---|
| Исходный R1 control, новые own roots и дополнительные сохранённые artifact/no-lock predicates | 0 | Реальный smoke child0, competing store неизменен |
| `uv run --locked --no-sync pytest tests/test_application_runtime.py -q -rs` | 0 | **30 passed, 0 skips**, включая present/absent × normal/exception restoration и реальные runtime/lease/file-handler cleanup |
| Четыре `uv run --locked --no-sync python -m scripts.smoke_*` | 0 каждый | Help5, MCP10, настоящий stdio discovery/EOF10, offscreen GUI; не tool effects/HTTP/visual |
| `uv run --locked --no-sync ruff check --select E,F,I scripts/smoke_support.py tests/test_application_runtime.py` | 0 | Два affected Python paths, не повтор full lint |
| Read-only source/assertion/receipt reconciliation | 0 | Coherent identity и применимость прежних proofs, не дополнительное runtime coverage |

Новый reviewer root назначался до imports/collection/children; competing профиль
тоже entirely synthetic. Внешний 100 s Job supervisor не зависит от исправляемого
helper; все наблюдённые own handles signaled, active PID до закрытия Job — 0,
watchdog emergency cleanup не потребовался. В stdio наблюдалось8 процессов native0.
Resources закрыты на normal/exception путях; приложение/HTTP с длительным loop не
запускались. Профиль пользователя не читался и не использовался как fixture.

## Согласование всей исходной матрицы S2

| Обязательство | Основание принятия текущего successor |
|---|---|
| Construction/imports/useful queries/legacy aliases | Unchanged protected core + retained fresh-interpreter blocked-SDK и useful direct/composed proofs; fresh affected runtime/wrapper checks |
| Owned/borrowed admission/close/join/no late writer | Retained in-flight storage/canonical-alias/drain и stale-reference proof; fresh прежние runtime cases и новый real helper/resource cleanup |
| Реальный межпроцессный lease | Retained first/second/readonly/next процессы, OWNER_BUSY/unchanged store/native0 и lock identity; lock/guard source неизменен |
| Atomic fail-closed JSON/detached copies/settings | Retained storage/readback/fault proofs на тех же adapter/model bytes; fresh relevant runtime cases |
| Writable-only orphan recovery/startup cleanup | Fresh прежние recovery/corrupt/factory cases; retained read-only/import/process proof; R1 больше не направляет smoke к competing store |
| Existing port/factory, pure rules/defaults, persist before admission, description/DTO compatibility | Protected core/queries/models/assertions; retained full149/compatibility и fresh affected runtime cases |
| Test/source/privacy boundaries | Старые assertion/marker identities сохранены; retained реальные safe changed-emitter sinks. Новый env override не создаёт privacy filter и не аттестует весь legacy output |

**Retained, не свежие повторы:** прежние независимые38/full149 (7 e2e deselected,
0 skips), storage/core/native/readback и type34. Их source/receipt hashes и
существенные conditions сверены; ранее выполненные149 не названы новым154 или
сложены с fresh30. Mypy остаётся inherited raw1/34 errors/15 files, без новых
location/cause findings. Full149, mypy, broad storage/core/S1/foundation/pack checks
ради этого delta не переисполнялись. Initial RED и прежние collector/alias ошибки
остались отдельной историей, не новыми product failures.

S3 cancellation/outcomes/live overlays/pool-cap-after-drain, S4 Trash/token и S5
complete CLI/MCP/GUI ownership ещё не реализованы/не приняты. Live YouTube/E2E,
native Trash, Linux runtime/CI, package/EXE, manual/visual GUI, forced rollover и
полная legacy privacy-chain — NOT_RUN. Документационное завершение выполняет тот же
Reviewer; actual commit/push/ref readback и remote CI сообщаются отдельно, без
выдуманного CI PASS. Следующий разрешённый срез выбирает оркестратор после release.
