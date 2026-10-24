---
id: ytdl-command-first-verification
title: "YTDownload — фактическая проверка command-first"
kind: verification
status: accepted
created: "2026-10-23"
updated: "2026-10-24"
areas: [testing, isolation, logging, compatibility]
summary: "S1–S6 и конечная offline-миграция независимо приняты; actual local Windows CI procedure квалифицирована, historical RED/debt и native/live/platform/package пределы сохранены."
code_ref: "0187eb90b15802460dae44098ee914a7129765a8"
code_verified_at: "2026-10-24"
verification_scope: "Accepted S5 база и exact S6 manifest15e6992a; final offline ACCEPTED после independent actual CI prep/probe/full275/authored65/type+full-lint attribution/four smokes/docs. Hosted/Linux/Python3.12/pwsh7/native Trash/live/EXE/manual visual не квалифицированы."
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

# S3 — авторское выполнение / cancellation / outcomes

**READY_FOR_REVIEW, не независимый ACCEPTED.** База — принятый и опубликованный S2
`5772f8fc4def3e6ed17f20787b0ebc276b765abe` в `refactor/command-first`. Предшествующие
отчёты/отказы/RED/accepted stages неизменны; весь прежний этот файл — byte prefix.
Coder не stage/commit/push. Тот же Reviewer должен независимо принять coherent S3,
после чего завершить affected docs/instructions и разрешённую selective доставку.

## Реализованные owners и совместимость

- Coordinator регистрирует token/record до submit. Admission gate допускает worker
  после queued notifications и future registration; wait включает worker return и
  callbacks. Cancel running — intent, terminal только после quiescence. Completion
  и cancel сериализованы; независимый failed не маскируется token-ом. Late progress
  не меняет terminal. Повторный cancelled идемпотентен, done/failed — conflict.
- Один executor до полного drain, следующий cap применяется к следующему admission
  после реального join старого pool. Полный detached settings snapshot фиксирован
  при приёме; backend получает отдельные phase copies. Network/service calls и
  EventBus callbacks вне coordination locks. Subscriber failures изолированы.
- Единственный IDownloadService теперь возвращает domain DownloadOutcome с typed
  completed/cancelled/failed, known paths и safe code; legacy path accessor сохранён.
  Existing injected path maps поддержаны с той же строгой media validation, empty
  не success. Форматные строки/URL semantics backend сохранены. Newest-folder и
  directory-scan attribution удалены. Attribution — hooks этой попытки, explicit
  postprocessed media и exact sidecars; existing ambiguous final files отказаны,
  leftovers/known partial files не удаляются. Playlist partial сохраняет известные
  результаты, а не объявляется done/отсутствием эффекта.
- Штатный yt-dlp DownloadCancelled проходит настоящий ignoreerrors/playlist guard;
  match/PP/progress boundaries проверяют token. Финальный file hook сохраняет факт
  эффекта, не бросает cancellation в SDK guard, объявляющий любую Exception failure.
- Terminal done только после save. После media-effect/save-failure live query/task
  сообщает failed/PERSISTENCE_FAILED/result_persisted=False/known files, done event
  отсутствует; close возвращает persistence debt и всё же освобождает ресурсы.
- API добавляет detached task/wait DTO и authoritative status/artifact overlays.
  Новые nullable measurements отличают неизвестное от реального0; legacy bridge
  получает числа. Старый query-only facade не требует coordinator. Exact legacy
  wire keys сохранены, если новых execution facts нет; known False/[]/errors не
  скрываются. HistoryEntry расширен только artifact_paths с backward read default.
  Старые runtime/characterization/ytdlp-unit tests не переписаны/не ослаблены.

## Реальные owner schedules, не success-fakes ядра

| Требование | Проверенный путь / наблюдение |
|---|---|
| Max1 A blocked fetch, B queued; cancelB | Public API → настоящий coordinator/JSON; B backend не вызывается, task/history cancelled; A history остаётся downloading до release |
| CancelA blocked fetch / до service registration | Immediate cancel_requested, timeout wait не отменяет/не терминализует; после release нет download stage, wait/readback cancelled; следующий useful task done |
| Immediate / completion-before-cancel / cancel-before-completion | queued→started→persisted done, ALREADY_TERMINAL; обратный порядок cancelled с retained file; independent failed остаётся failed; callbacks drained, late progress не воскресил task |
| Empty/foreign и distinct outputs / playlist / postprocessing | Настоящие owned bytes/JSON/readback; foreign newer bytes не меняются; real YtDlpService с fake YoutubeDL edge, final audio hooks и two-item complete/partial playlist через API |
| Terminal replace failure после media bytes | Единственная fault на actual os.replace; file retained, no done, live PF/False, next admission работает, close debt виден |
| Update settings при A/B | A/B output/proxy/options прежние, C новые при старом cap1; после drain D/E одновременно при cap2, no overlapping active generations |
| Active+queued close / повтор / subscriber / admission | wait=False удерживает lease, запросы/terminal честные, wait=True join, повтор safe, subscriber exception/другой thread reader не блокируют owner, новый runtime того же root |

Дополнительно executor submission refusal сохраняет known id/failed state и не
оставляет stale pending; history-only cancel/preview/wait требуют OWNER_REQUIRED.
Основные schedules сохраняют настоящие repositories/files/JSON. Подмена — внешний
backend/yt-dlp; terminal storage fault — узкий OS replace отказ, executor fault —
только refusal на native submission boundary. API/queue/repos не заменены успехом.

## Final-byte fresh gates

| Команда | Raw exit | Факт |
|---|---:|---|
| Addressed lifecycle/outcome/runtime/characterization/unit/query set | 0 | **82 passed**,0 skips |
| `uv run --locked --no-sync pytest tests/ -m "not e2e" -q -rs` | 0 | **177 passed,7 deselected,0 skips** |
| `uv run --locked --no-sync ruff check --select E,F,I` +13 actual changed Python files | 0 | All checks passed |
| `uv run --locked --no-sync mypy src/ --ignore-missing-imports` | **1** | **34 errors/15 files**,66 checked; exact previous34 location/cause rows, new0/removed0; не type PASS |
| Четыре module smokes через locked/no-sync | 0 каждый | CLI help5, MCP10, actual stdio discovery/EOF, offscreen GUI; не S5 tool-effect/lifetime acceptance |
| Read-only source/assertion/node/native/sink/type audit | 0 | Final Python bytes совпадают с source receipts; два meaningful RED AST сохранены, старые три test files exact |

Прогоны перекрываются, counts не суммируются. Полный gate оправдан общим worker/
backend/DTO/EventBus изменением, а не повторной приёмкой S1/S2. Сохранены: первый
fixture TypeError settings_overrides, затем genuine Oracle queued-cancel RED;
ранние owned lint errors, два incomplete fake-YoutubeDL API failures, один exact
legacy wire-shape failure и full query-only4 failures. Все исправлены у указанного
owner/fixture без ослабления assertions. Отдельный meaningful SDK-guard cancel RED
стал GREEN на том же oracle после source fix. Historical raw receipts не затёрты.

До collection/imports/children назначены synthetic home/appdata/temp/cache/log/
output/data-root, включая исправленный S2-R1 smoke override. Existing Python3.14.2,
offline/no-sync/no-download/no-bytecode/UTF8/offscreen, audited plugins, абсолютный
forward-slash basetemp проверен. Outer100s own Job supervisor наблюдал native exits;
watchdog не срабатывал, live own PID до Job close0. Barriers отпущены/join в finally,
partial setup/failure paths не оставляют owned executors/leases/children. Реальные
nonempty main/error files и stderr changed coordinator/backend/EventBus emitters
содержат useful id/codes и не содержат synthetic URL/content/path/exception markers;
stdout diagnostic child пуст. Это не full legacy/third-party privacy certification.

**NOT_RUN:** independent S3 acceptance/publication/remote CI, S4/S5/S6, live YouTube/
network E2E (семь исходных e2e cases deselected), native Trash, managed HTTP/app.py,
Linux runtime/CI, packaging/EXE/manual visual GUI, full Ruff и legacy privacy audit.
Synthetic marker media подтверждает attribution/retention, не codecs/quality live
YT result. Cooperative cancellation не обещает bounded stop или media rollback.
Исходные S1/S2/Oracle artifacts и принятое несвязанное поведение сохранены. Кандидат
и source/test/resources передаются тому же Reviewer; S4 не начинается.

# S3 repair-01 — R1/R2 после независимого NEEDS_CHANGES

Исходный14-path S3 получил независимый **whole-S3 NEEDS_CHANGES**: повторный
post-filter live overlay нарушал status selection (R1); native yt-dlp skip-existing
с final hook присваивал B файл одновременно работающей A (R2). Оба исходных causal
raw1, включая actual SDK guard, сохранены неизменными; ранние same-title setup
failures не объявлены attribution RED и не переисполнялись. Ни один прежний этап
этого файла не переписан. Следующее — **авторский repair READY_FOR_REVIEW**, не
независимый whole-S3 ACCEPTED и не разрешение Coder на Git-доставку.

Узкая дельта: только API, yt-dlp service, два существующих S3 test files и этот append.
Coordinator и остальные cumulative S3/base bytes сохранены. API несёт одну detached
пару entry/task через projection→query/status selection→limit→DTO, не читает live
state заново в mapper. Public сигнатуры/legacy wire/query-only/nullable facts прежние.

Backend выводит файлы внутри `output_root/download-<task_id>/…` и принимает known
paths только из этого пространства. Existing leased owner уже выдаёт разные IDs
разным admissions; root/settings/format selection/URL и legacy result fields не
перепроектированы. Различные задачи не делят check→effect→final-hook destination;
A path не становится B artifact даже при failed/cancelled. Это private naming внутри
заданного output, без locks вокруг network, нового registry/queue, overwrite/delete
или миграции старой истории. Между отдельными profiles по-прежнему нужны раздельные
output roots согласно CONTRACT, общей межпроцессной очереди не добавлено.

| Fresh repair proof | Raw | Наблюдение |
|---|---:|---|
| Исходный live-filter control, только новый owned root | 0 | Непустой filtered row остаётся downloading; ordinary worker уже done/persisted, полезный следующий task/JSON/readback/close |
| Новый copied same-title observer с явно сохранённым source diff | 0 | Native B теперь True/True, физические A+B эффекты, оба done/persisted с независимыми paths, bytes A сохранены |
| Пять connected R1/R2 pytest cases | 0 | Status/search mapper interleaving; native same-title complete/cancelled/failed, own partial retention и no foreign intersection |
| Whole lifecycle/outcome/query/characterization/history-CLI modules + два directly affected runtime consumers + format-string class | 0 | **51 passed**,0 skips; no API/queue/repository success-fakes |
| `ruff check --select E,F,I` четырёх actual changed Python files через locked/no-sync | 0 | All checks passed |
| `mypy` только api.py/ytdlp_service.py, `--follow-imports=silent --ignore-missing-imports` через locked/no-sync | 0 | Два owned source files без findings; не global type PASS |

R2 observer не форсирует устранённый same-path skip checkpoint: после независимого
naming правильная проверка — genuine B effect/bytes и native success/download=True,
а прежний no-shared-attribution invariant сохранён. SDK processing/format selection/
FileDownloader.download no-overwrite guard/final hooks не переписаны. Три native
pytest schedules проверяют также cancelled/failed B с собственными retained partial
bytes, без paths A, настоящим owner/JSON/reopen и finally release/join.

Пути старых test fixtures скорректированы только под новый private output prefix;
позитивные postprocessing/playlist/cancel/error assertions не ослаблены. Whole affected
набор повторяет meaningful original schedules и actual sink proof, counts51/5 не
суммируются. Scope/reference/source/assertion/native receipts сохранены отдельно от Git.

Прежние независимые82/177/four smokes/type34 остаются **retained**, не fresh replays:
новые R1/R2 и affected consumers проверены выше; неизменные coordinator/runtime/
storage/DTO/events/import/lifetime boundaries сверены по exact source/assertion
identity. Public API signatures, transports/bootstrap/smoke scripts/DTO не менялись;
проверки help/discovery/offscreen не достигают изменённых query mapper/download
naming, поэтому four smokes повторно не запускались. Full177, full mypy34/15 и
S1/S2/pack/full Ruff не повторялись. Global mypy остаётся inherited raw1.

До imports/collection/всех детей назначены новые synthetic home/appdata/temp/cache/
log/output/YTDL_DATA_DIR и absolute forward-slash basetemp, offline/no-sync/no-download/
no-bytecode/UTF8/offscreen flags; копия прежнего outer100s own Job watcher rebound.
Watchdog не срабатывал, observed handles exited/live-before-close0; finally cleanup
завершён. Реальные профили/медиа не читались и не менялись. Cumulative14 successor,
старые pre-S3 identities/три absence, узкая repair delta и protected bytes заморожены.
Все строки исходной S3 матрицы согласованы в handoff как fresh/retained/limit, но
текущий whole-S3 verdict принадлежит тому же Reviewer. Code/tests/resources освобождены;
Coder не stage/commit/push, S4/S5/S6/live E2E/HTTP/Trash/Linux/package не начинались.

# S3 — независимый whole-slice ACCEPTED после R1/R2

**ACCEPTED для всего исходного S3 на coherent successor**, не только для двух
локальных controls. Исторический NEEDS_CHANGES и genuine raw1 остаются фактами
прежних bytes. Весь прежний VERIFICATION сохранён как byte prefix; Oracle
требования не изменялись ради GREEN. S4–S6 не реализованы/не приняты.

Runtime identity: cumulative14 paths, primary SHA256
`4351da41fdf3a61318974d8799fdd0f60ab489f09d2537fb2074334d2ada9522`, accepted base
`5772f8fc4def3e6ed17f20787b0ebc276b765abe`. Независимо проверены14 worktree/copy/tar
bindings,5-path repair,9 unchanged S3 и28 unchanged pre-S3 paths. Старые test
assertions/decorators/definitions сохранены; изменения исходных fixtures только
добавляют task namespace, включая meaningful unrelated/newer отрицательные cases.
Public signatures и format/safe-dirname helpers прежние. Executable backend delta
к отвергнутому S3 — только RHS root assignment; hooks/guard/cancel/error mapper
не переписаны. Независимый freeze произведён до любых новых product producers.

## Что независимо закрыто

- **S3-R1:** одна detached entry/task пара используется до query/status selection,
  limit и pure mapping. Тот же исходный control теперь raw0: непустой selected row
  остаётся downloading, пока ordinary worker уже done/persisted; bytes, next useful
  operation, JSON и close подтверждены. List/search regression дополнительно
  сохраняет title/False flag/None persistence/[] artifacts одной прежней версии.
- **S3-R2:** реальный backend использует `output_root/download-<admitted task_id>/…`.
  Native causal A/B observer адаптирован ровно к устранению same-path destination:
  оба installed FileDownloader guards теперь возвращают True/True, media physical
  effects A+B и независимые bytes/JSON, не missing-checkpoint shortcut. Пересечения
  artifact ownership нет; A SHA256 прежний
  `6ceef77fe77881e4ebbf282fefc20e253be65dc1dcb4cda895ddb1456730d99d`.
  Native done/cancelled/failed B имеют собственные непустые retained paths и readback,
  A не изменяется. Исходный skip-existing RED не запускался заново/не переименован.

Task IDs выдаются существующим единственным leased history owner с устойчивым
next_id; это не новая очередь/registry или exception, отложенный до S4. Новый
видимый layout отражён в README/руководстве, старые files/records не мигрируют.
Selected output root, quality selectors, relative templates, URL/default/JSON/ID
contracts сохранены. Между разными profiles output roots по исходному CONTRACT
раздельны; hostile filesystem sandbox/общий межпроцессный output не обещаны.

## Fresh независимые проверки corrective delta

| Actual command / boundary | Raw | Факт |
|---|---:|---|
| Original live-filter control, новый owned root | 0 | Selection/result consistency, непустая строка и useful next/reopen/cleanup |
| Native same-title observer с сохранённой exact semantic delta | 0 | Installed SDK pipeline + unchanged no-overwrite guard; genuine A+B media/bytes/JSON, A unchanged |
| `pytest` двух named list/search и native done/cancelled/failed regressions через locked/no-sync | 0 | **5 passed**,0 failures/errors/skips |
| Whole lifecycle/outcome/API-query/characterization/history-CLI modules + two affected runtime consumers + format-string class | 0 | **51 passed**,0 failures/errors/skips; real API/coordinator/repositories/files |
| `ruff check --select E,F,I` четырёх changed Python files через locked/no-sync | 0 | Текущая correction, не full Ruff PASS |
| `mypy api.py ytdlp_service.py --follow-imports=silent --ignore-missing-imports` через locked/no-sync | 0 | Два owned source files, не global type PASS |
| Source/assertion/observer/receipt/JUnit/native/whole-matrix reconciliation | 0 | Метаданные применимости, не extra runtime coverage |

Все product children получили собственные winning YTDL_DATA_DIR/appdata/home/
profile/temp/cache/log/output roots до imports/collection. Absolute forward-slash
Windows basetemp проверен до pytest, plugin autoload выключен, offline/no-sync/
no-download/no-bytecode/UTF8/offscreen/no-track/no-update flags сохранены.
Независимый outer100s Job watcher перепроверен/rebound; actual own native exits и
signaled handles/live-before-close0 подтверждены без emergency watchdog cleanup.
Все barrier releases/joins/leases/handlers закрыты. Реальной сети/профиля/медиа нет.

Одно raw1 было только в metadata observer: ошибочный duplicate lookup отдельного
watchdog_sha256 вместо уже проверяемого historical sha256 map. Raw/начальная версия
сохранены; исправлена только schema lookup, metadata-only rerun0 без product replay.
Author observer raw CRLF digest и его LF-normalized delta digest независимо
согласованы; это не изменение SDK/контроля или ложная raw equality.

## Вся исходная матрица S3 и границы reuse

| Обязательство | Current successor basis |
|---|---|
| Useful positive/API→owner→edge→file→JSON/reopen | Fresh controls/whole outcome/lifecycle positives и next useful operation |
| Max1 queued-cancel и blocked fetch без раннего terminal/нового download | Fresh исходные lifecycle cases; unchanged coordinator/token/lease + retained originals |
| Before registration/immediate/both orders/monotonic/exactly-once after callback drain | Fresh whole lifecycle; public wait/close/next task, без private clear |
| Typed attribution/PP/playlist/partial/cancel-vs-failure | Fresh whole outcome, installed guard/next-playlist boundary; R2 native complete/cancelled/failed собственные effects |
| Terminal save after physical effect/no done/False/known paths/next/readonly | Fresh осмысленный os.replace failure; one-snapshot R1 repaired selection/limit; unchanged storage/outcome debt semantics |
| Per-admission settings/mutation isolation/actual old cap until drain/new pool | Fresh causal lifecycle A/B/C/D/E; unchanged executor/resource owner |
| Active+queued close/repeat/denial/subscriber/outside locks/next root owner | Fresh lifecycle + affected runtime consumers; unchanged other runtime proofs retained |
| Submit refusal/owner/id/default/legacy/query-only/nullable0 | Fresh refusal/next useful, whole API/CLI query/characterization and actual measured0 case; current signatures/source bindings |
| Diagnostics/import/storage/platform limits | Fresh same real nonempty main/error/stderr sink proof on corrected backend, no forbidden synthetic content; unchanged import/lease/storage source evidence retained. Not global privacy/platform claim |

**Retained, НЕ свежий replay:** прежние независимые82/177 (7 e2e deselected,0 skips),
full mypy raw1/34 exact inherited findings/15 files и four module smokes. Их exact
source/assertions/fixtures/env/receipts сопоставлены; изменённые root/projection
пути и их consumers проверены заново выше. Core/coordinator/runtime/DTO/events/
bootstrap/transports/scripts/manifest bytes неизменны. Help/discovery/offscreen
не достигают active download naming/mapper, affected CLI result modules — fresh.
5/51/177 не складываются; новый full182 не заявлен. Никаких повторных S1/S2/pack/
full baseline runs ради зелёного отчёта. Scoped type0 не превращает global raw1 в0.

Independent acceptance, documentation closure, local commit, remote publication/
ref readback и CI — отдельные факты. Same Reviewer завершает affected docs и их
final-byte checks по проектному grant, без нового approval loop; actual delivery
сообщается отдельно. Remote zero checks никогда не называются CI PASS.

NOT_RUN/deferred: S4 delete/Trash/token, S5 complete standalone/embedded/GUI adapter
lifetime/tool effects, S6 final matrix; live YouTube/network E2E, codec/FFmpeg media
quality, Linux/remote CI, packaged EXE/manual visual GUI, full legacy privacy.
После disposition/delivery S3 следующий срез назначает Hermes; S4 здесь не начат.

# S4 — авторский кандидат, обязательный gate BLOCKED

База: `4aee42352e10c0664f25588303da937c03713200`, ветка
`refactor/command-first`. Это реализация и авторские наблюдения, **не независимая
приёмка S4**. Coder не stage/commit/push; S5 wiring не начат. Предшествующий текст
и исторические отчёты/отказы сохранены, не переименованы в новый PASS.

## Реализованная граница API

- `prepare_delete_download` возвращает detached exact-file plan/missing/count и
  детерминированный token. `delete_download(..., expected_plan=...)` повторно
  строит план до первого эффекта; нет token — `CONFIRMATION_REQUIRED`, изменения
  существенных inputs/замена — `STALE_PLAN`. Token не авторизация, registry,
  clock expiry и автоматического повторного согласия нет.
- Использован существующий coordinator mutation lock: authoritative task/pending
  state, root/record/identity/shared/ancestry checks перед каждым эффектом. Даже
  keep-files нельзя удалять незавершённую запись. Неизвестная область legacy
  nonterminal не угадывается по текущим defaults read-only reader-а.
- Только записанные artifacts/legacy media/sidecars; без scan/newest/rmtree,
  permanent unlink, directory cleanup или миграции старых файлов. Folder-only
  legacy отказывает. Direct links, symlink/junction/reparse ancestry, unsafe
  roots/outside/directories/shared attribution отказывают; aliases не расширяют
  область. Это не hostile filesystem sandbox и не media+JSON транзакция.
- Существующий file-remover port подключён default bootstrap-ом к ленивому
  инфраструктурному QtCore Trash adapter, без QApplication/Qt imports в core.
  Проверяются capability и установленная tuple return form, нет fallback delete.
- Сначала индивидуальные известные moves, затем durable history delete. Partial,
  unknown и save failure возвращают safe structured result/counts/repreview,
  не ложное deleted=True и не rollback. Старые result keys/defaults сохранены.

## Connected доказательства S4

| Риск / наблюдение | Авторский результат |
|---|---|
| Exact media/sidecars, parent/sibling/unlisted preservation | Реальные fixture-directory Trash moves и bytes, JSON/reopen, никакого tree deletion |
| Preview/keep-files/confirmation | Store/media bytes сохранены, matching record-only token удаляет только запись; no/wrong token отказывает |
| Roots/links/shared/unfinished | Public API отказы без эффектов; реальные native direct/ancestor symlinks и Windows junction внутри root; cancel intent не quiescence |
| ID/bool и все stale dimensions | ID/mode/root/default-root/record/file-set/size/mtime/identity/replacement; clone size/mtime сохранены, новый inode защищён |
| Second move failure | Первый реально перемещён/recoverable, второй на месте, запись сохранена, PARTIAL_DELETE и следующий preview/keep-files работают |
| History replace failure после moves | PERSISTENCE_FAILED, старые disk/cache/reopen, bytes в synthetic trash; retained uncommitted temp закрыт, не объявлен authoritative store |
| Missing/zero/aliases | Честные counts/files_removed, настоящий target dedupe; spelling/hardlink shared-attribution bypass отвергнут |
| Replay/lost response/new target | После success NOT_FOUND без действия; старый token после partial/new same-name file отказывает |
| Infrastructure/headless | Реальный adapter с подменой только Qt OS call, actual lazy/core import checks и native capability без QApplication |
| Diagnostics | Настоящие application/adapter emitters → formatter/handlers/flush, непустые main/error files и configured stream; ID/code/count есть, synthetic sensitive markers отсутствуют |

Последний addressed run: **63 passed**, raw/native0, 0 skips. Он включает новые
safe-delete/file-remover modules, два разрешённых direct API consumers и core
import boundary. Не складывается с полным прогоном или прежними S3 totals.

## Обязательные gates и незакрытая граница

- Full offline command выполнен: **raw/native1, 237 passed, 2 failed, 7 e2e
  deselected, 0 skips**. Оба failures — неизменённые adapter portions
  `test_history_manager_delete_uses_shared_command_api` и
  `test_cli_history_delete_confirm_json`: старый unsafe success без plan token
  теперь получает controlled refusal. Они вне текущего direct-API edit ceiling.
  **Gate не PASS и не waived**: через Hermes запрошен только test-expectation
  exception для этих двух узлов, без adapter wiring/API bypass/skip/xfail.
- E,F,I по всем десяти changed Python files: raw0. Full mypy: raw1, **те же34
  findings/15 files**, checked68; exact location/cause comparison new0/removed0.
  Первоначальная новая bool/int annotation ошибка исправлена, не скрыта baseline.
- Четыре module smokes реально выполнены raw0: help, MCP discovery, stdio parity,
  offscreen GUI construction. Последующая private deletion-guard коррекция их
  не достигается; это применимые receipts, не новая S5 lifecycle/tool acceptance.
- После gates удалены только лишние EOF blank lines command_api; identical
  compiled-code binding сохраняет применимость receipts, без runtime rerun ради
  нового зелёного ярлыка. Diff-check исправление и исходный raw2 сохранены.

Сохранены meaningful no-token RED→GREEN и два active-preview RED→GREEN. Отдельный
ранний raw1 был ошибочным новым test oracle о пустом temp-каталоге: принятый atomic
writer сохраняет uncommitted candidate после replace failure; проверка теперь
наблюдает его валидные bytes и закрытый handle, не меняет S2 repository. Initial
lint/type failures и все попытки/источники/argv/env/native receipts сохранены в
локальном `coder-evidence/s4/`; cumulative freeze и полный отчёт — там и в
`coder-s4-result.md`. Все owned test workers/children/leases/handlers освобождены,
watchdog emergency cleanup не потребовался.

**Статус: BLOCKED, не READY_FOR_REVIEW**, пока Hermes не разрешит конкретную
двухузловую test-only дельту и обязательный full gate не будет закрыт на successor.
Это не новый архитектурный approval gate и не разрешение ослабить API.

NOT_RUN: native Trash move/restore (нет проверенного portable restore через
установленный QFile; пользовательская Корзина не тронута), live network/YouTube,
codec quality, Linux/runtime/remote CI, packaging/manual visual GUI, full legacy
privacy, S5–S6. Qt capability=True не выдан за состоявшийся Trash effect. Текущие
CLI/MCP/GUI token/lifetime/fallback wiring остаются отдельным S5, не безопасной
аттестацией всех legacy adapters.

# S4 completion-01 — авторский successor READY_FOR_REVIEW

Предыдущая BLOCKED-стадия и её raw1 остаются выше без изменений. Hermes разрешил
ровно два test-only изменения: HistoryManager/CLI ожидания старого confirm без
plan token. Runtime/source/ports/bootstrap/GUI/MCP/CLI wiring не менялись; S5
positive token/lifetime matrix не заменена текущими compatibility refusals.

В `tests/test_cli_command_api.py` изменены только
`test_history_manager_delete_uses_shared_command_api` и
`test_cli_history_delete_confirm_json`, их локальные fixture/assertion setup и два
необходимых imports. Real manager и real parser вызывают тот же shared API с
прежними ID4/ID3, delete_files=True, без token. Прозрачный observer вызывает
исходный bound method, не подменяет результат: наблюдается настоящий
CONFIRMATION_REQUIRED, а не ранний parser/owner/unsafe-scope error. CLI в этом
in-process вызове возвращает1, stdout пуст, stderr — safe error/hint JSON; это не
новая standalone process/lifecycle аттестация. Проверены неизменные cache/history
JSON bytes/reopen, media/unlisted/sibling/parent bytes и директории. Собственные
CLI log handlers закрываются в finally, borrowed handlers восстанавливаются.

Свежие affected проверки, owned pre-import isolation и тот же bounded native Job
supervisor, только в `coder-evidence/s4/completion-01/`:

| Команда / граница | Raw/native | Результат |
|---|---:|---|
| `uv run --locked --no-sync pytest tests/test_cli_command_api.py -q -rs` | 0 | **14 passed**,0 skips; correctly-tokened direct-API positives сохранены |
| `uv run --locked --no-sync ruff check --select E,F,I tests/test_cli_command_api.py` | 0 | Actual changed file, без общего reformat/suppression |
| `uv run --locked --no-sync pytest tests/ -m "not e2e" -q` | 0 | **239 passed,7 e2e deselected,0 skips**; прежние два обязательных failures закрыты |

Whole-S4 ledger не сокращён до двух новых GREEN. Прежние addressed63, exact
full-mypy34/15/new0/removed0, остальные unchanged-file lint facts, четыре smokes,
real adapter/native capability/link/junction/preservation/sink witnesses применимо
retained с source/assertion/receipt binding. Отдельных повторов63/177/mypy/smokes
нет. Full239 по требованию содержит те же выбранные cases, пересекающиеся counts
не складываются. Global mypy остаётся raw1, не type PASS; capability не Trash
move/restore. Native Trash, CI/platform/live/codec/legacy-privacy ограничения не
менялись.

Заморожен весь cumulative11 successor (не два delta paths): exact copies/tar,
предыдущие9 candidate bytes и40 protected bytes неизменны, original preimages и
четыре absences сохранены. Весь предыдущий VERIFICATION — byte prefix. Primary
manifest — `coder-evidence/s4/completion-01/final/candidate-manifest.json`, отчёт —
`coder-s4-completion-01-result.md`. Все own test resources освобождены, index пуст.
Coder не stage/commit/push; независимой whole-S4 приёмки ещё нет. Следующий владелец
— тот же Reviewer; READY_FOR_REVIEW не ACCEPTED и не разрешение начать S5.

# S4 — независимая приёмка целого среза

**Whole-S4 ACCEPTED на одном cumulative successor.** Это не приёмка только двух
исправленных compatibility tests. Исторические BLOCKED/RED и весь предшествующий
текст сохранены без переписывания. Нормативные PLAN/CONTRACT не ослаблены и не
редактировались при документационном завершении; текущее состояние отмечено здесь.
S5 positive adapter confirmation/lifetime и S6 final matrix остаются будущими.

Приняты 10 Python paths и фактическое дополнение этого журнала: Application API /
command policy, isolated deletion helper, DTO/port, lazy infrastructure remover,
minimal bootstrap и три затронутых test modules. Проверены реальные определения,
consumers и сохранность остальных source bytes. Source/tests/index до technical
verdict были read-only; документационное завершение не содержит runtime repairs.

## Реализованный scope

- Preview не меняет files/history. Применение требует того же ID/режима и matching
  `expected_plan`; token связывает record/root/file-set/identity, но не удостоверяет
  пользователя. Без token — CONFIRMATION_REQUIRED; изменённое ожидание — STALE_PLAN.
- Только явно записанные media/sidecars: modern/legacy paths dedupe-ятся без
  shared/alias escape. Папки, parent, unlisted/siblings сохраняются; folder-only
  legacy запись не порождает directory scan. Keep-files удаляет лишь запись.
- Небезопасные roots, outside/directory/direct/ancestor link/reparse/shared targets
  и active/nonterminal/unquiesced работа блокируют эффект. Cancel intent не terminal.
  Проверки повторяются перед каждым move в общей mutation boundary.
- После реального первого move и отказа второго — PARTIAL_DELETE с известными
  moved/failed/unknown/missing facts и retained record, не ложный полный success.
  После moves и failed history-save — PERSISTENCE_FAILED, явный history_deleted,
  cache/disk/reopen semantics и usable repreview. Media+JSON не crash-atomic.
- Уже перемещённые bytes остаются восстановимыми на OS-edge; автоматического
  rollback/retry нет. Старый token не трогает replacement после partial/lost response;
  успешный replay получает NOT_FOUND без нового filesystem effect. Ноль moves даёт
  files_removed=False, а True не означает исчезновение папки.
- Default Trash adapter остаётся lazy infrastructure-only QtCore, без QApplication,
  установки пакета или permanent-delete fallback. Поддержка и фактический результат
  проверяются отдельно; synthetic effect не называется native Trash qualification.

## Свежие независимые проверки

Все product processes запускались через existing venv/locked/no-sync с offline /
no-download flags, winning owned data/home/temp/cache/log/output roots до imports
и collection, audited plugins, absolute Windows basetemp и bounded native Job
watcher. `tests/downloads` исключён до collection; пользовательские данные не читались.

| Проверка | Raw exit | Факт / граница |
|---|---:|---|
| Useful correctly-tokened exact-files и keep-files positives | 0 | **2 passed**, настоящие policy/repository/files/JSON/reopen |
| Whole safe-delete/remover/CLI-command/core-boundary modules | 0 | **75 passed**,0 failures/errors/skips; включает оба revised consumers |
| Full offline `pytest tests/ -m "not e2e" -q` с исключением data folder | 0 | **239 passed,7 e2e deselected,0 skips**; тот же выбранный case Counter, что сохранённый прежний full239 |
| E,F,I по всем 10 changed Python files | 0 | Без suppression и без объявления full lint PASS |
| `mypy src/ --ignore-missing-imports` | 1 | Те же **34 inherited findings/15 files**, checked68; exact location/cause equality с принятым S3 и авторским S4, new0/removed0 |
| Четыре module smokes | 0 each | Help5/discovery10/real stdio parity/offscreen construction; не S5 tool effects/lifetime |
| Независимый actual completed-task → delete → reopen → next keep-files control | 0 | Две настоящие управляемые задачи, media/sidecar moves2 с byte readback, parent/unlisted/sibling сохранены, useful next operation |
| Default bootstrap без shell/backend imports и actual installed Qt capability | 0 | Lazy default без QApplication; capability=True, не native move/restore |
| Source/AST/JUnit/native/fixture/type/sink reconciliation | 0 | Применимость и артефакты, не дополнительное runtime coverage |

2/75/239 пересекаются и не суммируются. Новая обязательная full/type/smoke проверка
выполнена независимо; авторские14/63/239 её не заменяют. Неизменённые S1–S3 owners /
storage/lifecycle/outcome/format facts применимо сохранены, без отдельного replay
прошлых срезов, foundation pack или архитектурного survey.

## Исходная матрица и существенные границы

| Обязательство | Независимое основание |
|---|---|
| Exact attributed media/sidecars, durable absence, keep-files и preservation | Fresh useful positives, whole modules и real completed-task control; реальные bytes в synthetic recoverable tree и reopened JSON |
| Preview/token/no-token и legacy callers | Source/AST bound matching/stale cases; оба реальных старых вызова ID4/ID3, delete_files=True/без token достигают настоящего CONFIRMATION_REQUIRED и сохраняют cache/disk/reopen/media |
| Roots/outside/links/shared/activity | Fresh cases, два actual native symlink fixtures и inside-root native junction replacement; blocked fetch/cancel finally release/join и последующий useful delete |
| Validation/staleness/identity/move-time | Strict ID/bool, десять material dimensions, same-size/mtime distinct inode и checkpoint замены второго файла; source/assertion/physical readbacks |
| Partial second-move failure и unknown post-effect | Known moved1/failed1 либо explicit unknown/not_attempted, retained history, recoverable bytes и protected replacement/repreview |
| Atomic history-save failure после moves | Real os.replace refusal, truthful PERSISTENCE_FAILED, unchanged authoritative cache/disk/reopen на отказе, retained closed temp и missing-only recovery |
| Missing/zero/dedupe | Совместные modern/legacy/spelling paths без double count/чужой attribution; zero moves не success-флаг удаления файлов |
| Retry/lost response | NOT_FOUND после success и stale old token после partial/new target; нет автоматического повторения опасного действия |
| Infrastructure/default/headless/native | Actual Python adapter result/error, default policy wiring и lazy core; synthetic moves/native capability раздельны; actual native Trash restore NOT_RUN |
| Diagnostics | Непустые настоящие application/adapter main/error/configured stream через formatter/handlers/flush; ID/code/count сохранены, private sentinels отсутствуют; safe CLI refusal |

Два compatibility observers прозрачно вызывают исходный bound API, не возвращают
scripted success/error и не mint-ят token. Реальный in-process CLI возвращает1,
stdout пуст, stderr — safe error/hint JSON. API code подтверждён на самом исключении;
wire code или standalone native CLI qualification этим не выдумываются. Production
CLI/MCP/GUI token wiring не менялось; его успешная интеграция — S5.

**NOT_RUN / пределы:** native Trash move/restore (portable restoration не проверена;
пользовательская Корзина не перечислялась/не трогалась), live YouTube/network E2E,
codec/FFmpeg quality, Linux runtime/remote CI, packaged EXE/manual visual GUI,
whole legacy/native Qt stderr privacy. PLAN S4 допускает честный native NOT_RUN;
capability=True и synthetic recoverable rename не превращаются в состоявшийся OS
Trash effect. Все own workers/leases/handlers/barriers/наблюдённые descendants
освобождены, watchdog emergency cleanup не понадобился.

Независимая technical acceptance, affected documentation checks, selective commit,
remote ref readback и exact-head CI — отдельные факты. Отсутствие branch-trigger
проверок не CI PASS. После публикации/освобождения следующий срез назначается
по существующему командному порядку; S5 в этой приёмке не начинался.

## S5 — авторский связный кандидат адаптеров (2026-10-24)

Это новый author evidence, не изменение исторической приёмки S4 и не независимый
ACCEPTED. База: `1cfda355cff364786638c3618332131d49b8130c`, ветка
`refactor/command-first`; S6 не начинался. Evidence сохранён отдельно от Git
в авторском пакете S5; его исходные artifacts/failed runs неизменны.

Canonical MCP factory теперь в infrastructure/server; bootstrap сохраняет
reexports, десять manifest tools и их прежние defaults. Factory/listener/window
заимствуют один ApplicationAPI, не создают вторую очередь. CLI выбирает readonly
queries, передаёт plan token, отказывает standalone cancel до runtime creation.
Owned add печатает один flushed acceptance, ждёт настоящий terminal/persistence
и закрывает свой runtime; borrowed add не ждёт и не закрывает owner.

GUI managers используют detached API queries/settings и общие add/cancel/delete.
Repository-delete fallback убран. До существующего modal готовятся оба режима;
Yes передаёт token выбранного checkbox, No ничего не меняет, stale не удаляет.
Desktop создаёт subscriptions и восстанавливает list_tasks до HTTP admission.
Настоящий uvicorn.Server имеет stop/join; window/listener не закрывают borrowed
runtime. Desktop finally останавливает admission, закрывает transport/bridges и
дожидается runtime. Cleanup error не становится успешным exit/closed: при отказе
resource-close accepted core сохраняет lease; после устранения controlled external
fault повторный close освобождает его, сохраняя исторический error code.

| Обязательная строка S5 | Исполненное основание |
|---|---|
| Native CLI | Настоящий module/parser/bootstrap/JSON store: list/get/description/transcript/paths, writer-held readonly snapshot, absent/corrupt store, missing/usage/JSON channels, wrappers/help, token keep-files и reopen |
| Owned add/lifetime | Четыре настоящих дочерних entry: acceptance прочитан до release, worker удержан, done/cancel/fail/persistence exits 0/1/1/1, ровно один stdout JSON, durable readback и следующий writer; native Windows no-delete-sharing handle вызывает реальный atomic-replace refusal, не fake save |
| Native MCP stdio | SDK discovery/get/list/read_description/missing, две реальные no-token/preview/apply границы, matching-token keep-files/reopen; два наблюдённых child exit0, включая EOF с настоящей отменой/terminal persistence; отдельный in-process SDK add/cancel использует тот же runtime |
| Managed HTTP | Реальные loopback calls/эффекты, OS-allocated port, disconnect без отмены job, cooperative intent до quiescence, stop/join/idempotence/port reuse, borrowed owner остаётся полезен; foreign bind сохранён |
| Actual offscreen GUI | Existing cards получают restored/API/MCP/GUI-button jobs, cancel button не делает terminal до release; history filter сохранён; шесть настоящих modal/button/signal случаев No/Yes/stale × оба режима, real fixture Trash moves и preservation; settings Cancel/Save/theme проходят через detached API |
| Startup/cleanup | Partial port factory, actual bind refusal, actual partial window construction, public subscription/unsubscription readback, controlled resource-close failure/recovery, повторный close и следующий writer; real partial log-open failure закрывает только own handlers |

Окончательный full offline: **270 passed, 7 e2e deselected, 0 skips**, raw/native0
(`runs/pytest-offline-corrected-observer`). JUnit содержит все прежние239 case IDs
и31 новых connected cases; это один suite, не сумма пересекающихся прогонов.
Changed-Python Ruff E/F/I — PASS; четыре module smokes — raw/native0.
Full mypy — **raw1, 34 findings/15 files, 68 checked**, не type PASS. Сопоставление
file/enclosing-symbol/message/code/multiplicity с сохранённым S4 baseline даёт
new0/removed0; первоначальные43/18 с новыми owned findings сохранены и исправлены.

Настоящие GUI/MCP/CLI emitters прошли formatter/handlers/flush: main1772 bytes,
error340, stderr1677, отдельный CLI error72; stdout0 для diagnostic operations.
Проверены полезные ID/code/count и отсутствие synthetic URL/proxy/title/path/raw
error sentinels; пользовательские title/description отдельно остаются полезными
protocol results. Это не whole-legacy/native Qt privacy certification.

Сохранены первый полезный readonly RED и все setup/assertion/teardown failures:
SDK-generated schema dataclasses вместо предполагаемого dict/model, slots-only API
observer, настоящий Qt standard button, неверное ожидание clean resource-close и
текстовое ожидание stale message. Начальный full269/1 сохранил deferred Qt terminal
signal до teardown; corrected observer запускает настоящий новый Qt event loop и
проверяет исполнение callback, не меняет production emitter/результат. Timeout не
увеличен, skip/xfail/selection bypass не добавлены. Final native supervision
фиксирует завершённые собственные handles, без watchdog emergency cleanup.

**NOT_RUN:** independent S5 acceptance/publication/remote CI, native Trash
move/restore, live network/YouTube/codec quality, Linux runtime, packaged EXE/manual
visual GUI, whole legacy privacy, S6. Подменены external network backend и OS Trash
(real fixture renames); отрицательные startup/open/replace failures и публичные
transparent observers отдельно связаны с исходниками. Ни user Trash, ни реальные
профили/медиа не использовались. Автор не stage/commit/push и не принимает свой срез.

## S5-R1 — авторский repair-01 после независимого NEEDS_CHANGES

SAME Reviewer обнаружил конкретное нарушение ownership в CLI `_diagnostics` и
`app._logging`: finally закрывал/терял caller-owned handler, подключённый во время
invocation. Его два реальных controls raw/native1 и whole-S5 NEEDS_CHANGES остаются
неизменной историей. Предыдущие270 PASS не были доказательством сохранности такого
ресурса и не означали ACCEPTED.

Минимальная правка только двух logging contexts: список `owned` наполняется при
acquire, formatter/JSON-level changes и flush/close/remove применяются к нему.
Старые borrowed handlers возвращаются публичным addHandler без замены текущего
root list, поэтому late caller handlers не теряются. Сами caller objects/streams
не переоткрываются; mode='w' не может усечь их прежние bytes. Root/logger levels,
owned partial-open cleanup и сообщение cleanup error сохранены.

До реализации добавлены пять случаев в двух существующих adapter modules: реальный
borrowed CLI/parser/API/coordinator/queued subscriber при normal/cleanup-error и
настоящий desktop logging context при normal/body-error/cleanup-error. Все пять
на исходных rejected production bytes дали meaningful RED именно на late handler
identity/registration; jobs при этом реально завершались done/persisted, bytes и
следующий запрос/writer проверены, finally исполнен. После правки те же assertions
GREEN. Проверяются прежний stream object, root registration, before/during/after
физические записи, owned file closure/rename и полезная следующая операция.

Оба независимых immutable control helper скопированы без изменения bytes и запущены
только с новым `REVIEW_RUN_ROOT` в `coder-evidence/s5/repair-01/runs/`: оба raw/native0.
Это авторский recheck исходных controls, не новая независимая приёмка. Desktop
control подтверждает logging context, а не визуальную GUI-квалификацию.

Свежие repair gates: affected modules **36 passed**, full offline **275 passed,
7 e2e deselected, 0 skips**, cumulative24-Python E/F/I и четыре отдельные module
smokes raw/native0. Full mypy raw/native1: прежние **34 findings/15 files/68 checked**,
точные identities совпадают с независимым S5 baseline, new0/removed0; не type PASS.
Сохранены все270 прежних selected IDs/декораторов/assertions, добавлены5. Пересекающиеся
5/36/275 и прежние54/270 не складываются. S1–S4 campaign не повторялась.

Repair delta ограничен этими двумя contexts, добавленными regression functions и
данным factual append. Остальные20 predecessor candidate paths и55 protected bytes
не изменены; прежний VERIFICATION prefix сохранён. Для всей шестистрочной матрицы
используются свежие275 и явно связанное неизменное evidence прежней проверки,
а не только последний R1 assertion. Полный cumulative25 successor сохранён
в авторском repair-01/final пакете отдельно от Git.
Все ограничения native Trash/live/platform/package/privacy/CI остаются прежними.
Статус автора READY_FOR_REVIEW, whole-S5 verdict SAME Reviewer ещё ожидается;
commit/push и S6 не выполнялись.

## S5 — независимая приёмка repair-01 и текущего целого среза (2026-10-24)

**WHOLE-S5 ACCEPTED; S5-R1 CLOSED.** Предыдущий NEEDS_CHANGES относится к
predecessor manifest `8b273484ed175a44d8b2a447333ab76624911959e1a20150c8964008461addf4`;
он и оба настоящих RED controls raw1 не переписаны и не объявлены успешными.
Текущий coherent successor — manifest
`3c2aabf4e37bcf0604e548094d26a3f8033055a67b9a8ebbe42708c78c2f8ade`,
author archive `881624fe9131b806d5bb2f91a2943c83788288e010dfdd9b9cafb1af3dda1b6d`,
на accepted/published S4 базе `1cfda355cff364786638c3618332131d49b8130c`.
Это не S6 final qualification.

До helpers/product producers независимо скопированы/связаны все25 cumulative
paths (24 Python/3 new), полный archive и author evidence. Пять repair paths
ограничены двумя logging function bodies, append-only regression functions и
factual verification. Остальные20 candidate и55 protected paths unchanged;
93 finite input identities и все прежние270 selected cases/assertions/decorators
сохранены. Текущий паспорт документа обновлён отдельно; исторические body/RED
сохранены, новые machine-local evidence paths не публикуются.

### Закрытие S5-R1

Оба byte-identical исходных независимых controls исполнены заново только в новых
owned roots, с прежним business route/assertions: **raw/native0/0**. CLI проходит
настоящие parser/API/coordinator и genuine queued EventBus subscriber; caller
подключает свой заранее открытый handler во время полезной работы. Тот же late
object/stream остаётся открыт/зарегистрирован, physical after-write присутствует;
early handler также сохранён. Acceptance0, done/persisted/media/close/next writer
действительно проверены. Только external network backend синтетический.

Второй control исполняет настоящий app._logging и nonempty app/error sinks;
это logging-context, не новая visual GUI qualification. Пять новых cases
дополнительно проверяют SAME streams/objects и before/during/after bytes,
normal/body exception/owned cleanup fault, actual owned close/remove и полезную
следующую операцию. Caller FileHandler(mode='w') не пересоздаётся/не переоткрывается.
Existing partial file-open failure и root/logger restoration сохранены. Ошибка
owned cleanup остаётся безопасным nonzero/CommandError, не подавленным success.

### Независимые fresh executions

Pre-import/collection изоляция и audited plugin policy соответствуют testing
instruction: winning owned YTDL_DATA_DIR/home/temp/cache/log/output, absolute
forward-slash basetemp, offline/no-sync/no-download/UTF8/no-bytecode/offscreen/
no-tracking; OS essentials не печатались. Existing .venv, независимый bounded
Windows Job watcher, actual own descendant handle exits и finally cleanup.

| Команда / граница | Raw exit | Наблюдение |
|---|---:|---|
| Оба original ownership controls | 0 each | Те же early/late objects и actual after bytes; useful CLI result/next writer |
| Две named new regression functions | 0 |5 passed, включая normal/body/cleanup cases |
| Оба affected adapter integration modules | 0 |36 passed/0 skips, existing privacy/partial-startup/close branches сохранены |
| `uv run --locked --no-sync pytest tests/ --ignore=tests/downloads -m "not e2e" -q -rs` | 0 |275 passed,7 e2e deselected,0 skips; все прежние270 IDs +5 новых |
| `uv run --locked --no-sync ruff check --select E,F,I <exact24 cumulative Python paths>` | 0 |Полный непустой changed-path E/F/I gate |
| `uv run --locked --no-sync mypy src/ --ignore-missing-imports` | **1** |34 inherited findings/15 files/68 checked, exact file/line/message/code/multiplicity new0/removed0; не type PASS |
| Четыре отдельные module smokes CLI/MCP/stdio/GUI | 0 each |Help5/discovery10/actual parity/offscreen construct/events/close, не замена useful checks |
| Metadata/source/assertion/fixture/receipt reconciliation | 0 |Один successor и все шесть original rows, не дополнительное runtime coverage |

5/36/275 и прежние2/54/270 пересекаются, не складываются. Прежние независимые
useful CLI/MCP/HTTP/Qt физические readbacks применимо reused после byte/fixture/
assertion binding, не выданы за новые controls. Fresh36/275 квалифицируют изменённые
contexts/new assertions. Принятые S1–S4 не исследовались и не принимались заново.

### Вся исходная шестистрочная матрица

| Original row | Текущее основание / disposition |
|---|---|
| 1 Native CLI | Реальный module/parser/bootstrap/store: useful query/description/transcript/paths, exact channels/exits/usage/wrappers, readonly без writer/recovery/write, absent/corrupt preservation, standalone cancel OWNER_REQUIRED до пустого owner — ACCEPTED |
| 2 Owned/borrowed add | Flushed acceptance до release, process held до terminal/save, done/fail/cancel/persistence native0/1/1/1, физические результаты/reopen/next writer; Windows no-delete-share handle реально отказывает replace и закрывается. Borrowed acceptance не wait/close runtime; R1 caller handlers сохранены — ACCEPTED |
| 3 MCP stdio/shared owner | Actual SDK protocol child/ten tools/useful calls/missing, matching-token keep-files/reopen/native0; owned EOF cancel/save/native0. In-process add/cancel одного runtime, structured partial с реальными moved bytes/retained history — ACCEPTED |
| 4 Managed HTTP | Actual OS listener/SDK effect/read, disconnect не Job cancel, intent nonterminal до release, stop/join/repeated close/port reuse/next job, foreign bind/borrowed runtime preservation — ACCEPTED |
| 5 Existing GUI | Подписки/restoration до раннего HTTP, real Qt actions/signals/cards/dedup/cancel/filter, шесть actual modal No/Yes/stale × modes/token/physical recoverable moves, detached settings Cancel/Save/theme; no redesign — ACCEPTED в offline границе |
| 6 Startup/close | Actual resource-factory/bind/window/log-open partial failures, truthful incomplete cleanup/resource-close recovery, owned worker/listener/lease/handler release и next operation; оба R1 callers/пять regression cases теперь проходят — ACCEPTED |

Новые contexts не создают параллельный logging framework: только локальный acquired
список handlers; formatter/levels/flush/close/remove применяются к owned objects,
previous handlers возвращаются без стирания late caller registrations. Произвольные
иные concurrent logger configurations этой bounded приёмкой не аттестованы.

Fresh changed-chain diagnostics прошли actual emitter/formatter/handler/flush/readback:
непустые main/error/stderr и safe CLI error, полезные id/code/count, diagnostic
stdout0. Synthetic URL/proxy/title/path/raw-error markers отсутствуют. Explicit
useful title/description/path results не считаются diagnostic leak. No blanket
legacy/native Qt privacy claim.

**Пределы:** native Trash move/restore, live YouTube/network/codec quality, Linux
runtime/remote CI, packaging/EXE/manual visual и whole legacy privacy — NOT_RUN.
System Trash заменён только fixture-owned recoverable moves; capability не
превращается в native qualification. Пользовательские profiles/media/logs/bin и
credentials не читались. Пакеты/software не устанавливались/не скачивались;
чужие процессы/порты не закрывались. Собственные controlled backends в finally
отпущены, worker/client/listener/handler/lease outcomes и native exits проверены;
watchdog emergency cleanup не понадобился.

Документационное завершение отражает именно эту приёмку: actual CLI режимы/выходы,
canonical MCP factory, token/GUI/settings/lifetime/log ownership, known limits.
24 принятых Python bytes не меняются при docs finish; source/tests не исправляются
Reviewer-ом. PLAN и нормативные semantics CONTRACT не ослаблены, CI workflow
alignment оставлен S6. Technical acceptance, selective commit, literal remote ref
readback и exact-head CI остаются разными фактами; отсутствие jobs не CI PASS.
S6 начинается только следующим отдельным назначением после завершения S5.

## S6 — авторская конечная offline qualification и CI/doc alignment

База S6 — опубликованный S5 commit `0187eb90b15802460dae44098ee914a7129765a8`.
S1–S5 и закрытые R1/R2 не переоткрывались; production Python, tests и smokes в S6
не менялись. Статус этого раздела — **author READY_FOR_REVIEW, не S6 ACCEPTED**.
Исходные Oracle rationale, historical failures/RED, независимые verdict и пределы
выше сохранены. Следующий независимый verdict и доставка принадлежат тому же Reviewer.

### CI procedure и реальные локальные границы

Workflow сохраняет исходные push-to-main/PR triggers, Linux/Windows matrix,
Python3.12 selection и все прежние provisioning/install commands. После них
отдельный Python step создаёт новый root в RUNNER_TEMP, назначает winning
profile/APPDATA/home/temp/XDG/cache/log/smoke roots, offline/no-sync/no-download/
UTF8/no-bytecode/offscreen/no-track flags и audited Qt plugin policy **до**
application imports/collection/children. PYTEST_ADDOPTS содержит tests/downloads
exclusion, quoted forward-slash absolute basetemp и JUnit; output default следует
synthetic home, YTDL_OUTPUT_DIR не объявлен продуктовым override. Smokes — четыре
отдельные locked/no-sync module invocations.

На доступном Windows host исполнены actual workflow preparation bytes, не их
вторая реализация: inherited selectors указывали в competing owned roots,
RUNNER_TEMP содержал пробелы. Настоящие API/coordinator/JSON + boundary backend
создали useful done/persisted media в synthetic default output; native readonly
CLI прочитал тот же store при живом writer, затем следующий writer открыл его.
Competing store bytes не изменились. Затем actual offline/smoke argv выполнены
с environment, полученным из GITHUB_ENV этой же процедуры, в новых own run roots.
Это Windows/Python3.14.2 native argv/env qualification, **не** исполнение hosted
GitHub runner, pwsh7 wrapper, configured Python3.12 или Linux matrix/install steps.
Workflow не dispatch/rerun-ился; установки/скачивание зависимостей не запускались.

### Конечные gates и disposition исходных требований

- Fresh final offline: **275 passed, 7 e2e deselected, 0 skips**, raw/native0.
  Counter selected cases совпадает с independently accepted S5; tests/assertions/
  fixtures и production bytes неизменны. Live test bodies не исполнялись.
- Cumulative authored lint: **65 Python paths**, от исходного PLAN code_ref до
  текущего worktree, E/F/I raw/native0. Отдельно проверены74 read-only imported PFK
  files против первого committed import; его checker не authored lint scope.
  Не использован пустой last-delta список CI/Markdown.
- Full source/test/script lint baseline по104 explicit Python paths: raw/native1,
  **57 findings**, отдельный факт, не narrow gate и не broad cleanup. Source не
  исправлялся. Full mypy: raw/native1, **34 inherited findings/15 files/68 checked**,
  точные identities/cause совпадают с S5, new0/removed0; это не type PASS.
- Четыре отдельные module smokes CLI/MCP/stdio/GUI: raw/native0. Они не заменяют
  useful connected cases. Foundation explicit corpus18 и doc/manifest literals4
  passed; README Python example реально прочитал useful synthetic record без
  изменения store. CLI prose examples проверены parser-only, installers/live URLs/
  сторонние client configs не исполнялись. Final doc bytes проверяются отдельно.

| Original done/connected obligation | S6 основание |
|---|---|
| Direct Python без UI/transport, lease/storage/recovery/settings | Fresh existing connected cases в275; current source/assertion/readback bound к S5, независимый accepted статус reused, не новая архитектурная приёмка |
| Cancellation/races/outcomes/snapshots/pools/SDK attribution | Fresh deterministic cases в275 на unchanged owners, прежние meaningful RED и независимое закрытие S3-R1/R2 сохранены |
| File-only preview/token/guards/partial/persistence/replay | Fresh existing physical fixture moves/readback в275; original S4 matrix retained с byte/assertion binding; native Trash restore отдельно NOT_RUN |
| Native CLI/stdio/managed HTTP/Qt/lifetime/handler ownership | Fresh275 содержит accepted S5 six-row cases и обе R1 regression functions; useful physical results и own release, не только help/discovery |
| CI alignment и final gates | Actual preparation/owned-selector/readback probe + реальные команды выше; same workflow bytes, matrix/triggers/provisioning не изменены |
| Знания, finite scope, final handoff | PLAN отделяет initial snapshot и historical notes от accepted S1–S5/current S6; нормативные semantics CONTRACT прежние. Полный S6 diff/preimages/receipts/freeze передаётся отдельно; independent verdict ещё ожидается |

275, прежние36/5/275 и адресные проверки не суммируются. Неизменное независимое
S1–S5 evidence переиспользовано только с проверкой относящихся source/assertion/
fixture inputs и receipt; старые producer scripts/destinations не переисполнялись.

Сохранены также S6 metadata/procedure failures: первоначальный слишком широкий
input list захватил tracked packaging source build/build.py, после чего admission
остановился; исправленный runner проверяет prefix allowlist **до** snapshot.
Этот ошибочный input больше не читается/не используется. Два lint attempts получили
E902 из-за CRLF в shell argv inventories; native splitlines/literal argv correction
дала требуемый65-file PASS без изменения product/tests или ослабления assertions.
Это setup/acquisition faults, не product RED и не вымышленный baseline lint PASS.

**NOT_RUN / пределы неизменны:** independent S6 verdict/publication, hosted remote CI,
Linux/Python3.12 runtime, native Trash move/restore, live YouTube/network/codec,
packaging/EXE/manual visual GUI, whole legacy/native Qt privacy. Synthetic media и
recoverable fixture moves не дают этих гарантий. Собственные resources закрыты/
joined и последующие safe operations проверены; native supervisor/release receipts
отдельны от author PASS. Coder не stage/commit/push; final docs/delivery — только
после независимого ACCEPTED.

## S6 — независимая конечная приёмка offline command-first (2026-10-24)

**S6 и итоговый переход независимо ACCEPTED в согласованной offline-границе.**
Source/tests/scripts в S6 не менялись; accepted S1–S5 не переоткрывались. Текущий
technical verdict относится к coherent8-path candidate на S5 базе
`0187eb90b15802460dae44098ee914a7129765a8`: manifest
`15e6992af1da8c50da1ff01822be22114cd792493e0c10ea58c31d7491e0c387`,
author archive `f9162546568c4d7e773fe383cc4f6fa6614117c8c8952edf9f02d9a0a3786186`.
Это не полная cross-platform/live/native/package сертификация.

До helpers/product producers независимо скопированы восемь candidate files и
125 explicit admitted inputs. **Весь** список валидирован до source copy;
117 protected/104 Python bytes сопоставлены с accepted S5,65 actual cumulative
Python paths выведены от original code_ref. PFK74 отдельно raw-bound к unchanged
первому импорту (Git LF reconciliation не заменяет текущие raw identities).
Author acquisition fault с packaging source сохранён; его copied body не читался/
не использовался Reviewer и не попадает в payload. Current admission исключила
build/dist/vendor/tests/downloads/private roots до чтения. Personal leak не выдуман.

### Actual CI procedure, не только YAML

Независимо исполнены точные YAML run scalar bytes шага preparation. Сохранены
matrix ubuntu/windows, triggers main+PR, fail-fast=false и все первые шесть
provisioning recipes; installation/uv sync/remote workflow не запускались.
Перед preparation унаследованные selectors намеренно указывали только в competing
OWNED дерево, RUNNER_TEMP содержал пробелы. GITHUB_ENV от actual preparation дал
winning native absolute profile/home/config/data/temp/cache/log/smoke roots,
plugin/offline policy и shlex-quoted forward-slash basetemp/JUnit.

Полезный composed путь: настоящий API/coordinator/repository с заменой только
external network backend создал done/persisted media в **реальном default**
synthetic home/Downloads/YTDownloader. Native readonly CLI прочитал тот же store
при удерживаемой writer lease; physical bytes/JSON и next writer проверены.
Competing JSON не менялся. Затем на том же workflow SHA и source bytes, в новых
roots, исполнены actual full-test и четыре module-smoke argv. Parent/probe/дети
получили изоляцию до импорта/collection; tests/downloads исключён до traversal.

**Подтверждено:** local Windows/Python3.14.2, actual preparation, native argv/env,
space paths, child inheritance, полезные effects/readback/cleanup. **NOT_RUN:**
hosted GHA/provisioning, Linux, configured Python3.12 и pwsh7 shell wrapper.
Native argv equivalence не названо запуском GitHub runner или PowerShell wrapper.

### Свежие независимые gates и debt

| Проверка | Raw/native | Результат |
|---|---:|---|
| Actual workflow prep + useful composed probe | 0 |Default output/physical bytes/JSON/held-writer readonly CLI/next writer, competing store unchanged |
| Actual workflow offline-test command | 0 |275 passed,7 e2e deselected,0 skips; exact independently accepted S5 Counter |
| Authored cumulative literal65 E/F/I | 0 |Не last-delta8 и не пустой docs-only Python scope; единственный imported PFK checker исключён отдельно |
| Full mypy src | **1** |34 inherited findings/15 files/68 checked; exact file/line/message/code/multiplicity new0/removed0; не type PASS |
| Configured full lint104 | **1** |57 inherited findings; exact file/line/column/code/message/multiplicity совпадают с bound unchanged-source baseline; не PASS и не broad cleanup |
| Четыре actual workflow module-smoke commands | 0 each |CLI help5/MCP ten-tool discovery/real stdio parity/offscreen GUI construct-events-close |
| Foundation explicit corpus + docs literal consumers | 0 |18 files/findings=[] и4 passed; external-link limits сохранены |
| README Python example | 0 |Действительно прочитана одна useful synthetic row; readonly store byte-identical |
|12 CLI prose examples | 0 |Только existing parser/arguments, не handlers/live download/server execution |
| Independent source/assertion/fixture/native reconciliation | 0 |Все четыре original obligations и final offline done; не ещё один coverage count |

Fresh275 и предыдущие5/36/275/другие reruns не суммируются. Каждый selected case
связан с current raw test file/decorated source/assertions; нет нового/потерянного
case. Физически перечитаны current CLI4 native0/1/1/1, modal6 recoverable bytes/
unlisted preservation, R1five same-object/streams/after-write/owned-release и
nonempty safe sinks. Unchanged independent S1–S5 owners/schedules/guards применимо
retained, не выданы за новые acceptance cycles или новую архитектуру.

### Четыре исходных обязательства S6 — единый verdict

| Original obligation | Disposition |
|---|---|
| 1 Done/connected proof | ACCEPTED: qualified unchanged independent S1–S5 chain + current actual CI composed operation/full275/source/assertion/physical readback; direct core, cancellation/quiescence/settings/pools/artifacts, leases/deletion/partial/persistence и real adapters/lifetime сохранены |
| 2 CI procedure | ACCEPTED LOCAL WINDOWS: actual prep и subsequent commands, winning roots/space quoting/child inheritance/useful result/release; matrix/triggers/provisioning unchanged. Hosted/Linux/Python3.12/pwsh7 остаются NOT_RUN |
| 3 Документы/инструкции | ACCEPTED: historical Oracle snapshot/S3 notes отделены от current status, rationale/RED сохранены, normative CONTRACT неизменен кроме factual status. Useful README example, parser-only12, literal consumers/Foundation и truthful limits |
| 4 Final gates/freeze/release | ACCEPTED: raw gates/65-file scope и exact debt attribution, independent admission-before-copy, one coherent snapshot, native own handles/join/next operation; no source/test/CI self-fix |

### Подтверждённые входы и пределы

- Direct Python: README example импортирует create_runtime, явно читает собственный
  YTDL_DATA_DIR через read_only=True и list_downloads; actual useful row/store
  preservation проверены. Отсутствие Qt/transport в core и direct lifecycle остаются
  source-bound к принятым connected tests, не выводятся из одного import.
- CLI: `uv run --locked --no-sync python -m src.interfaces.cli --json --data-dir <owned-data-root> history list`;
  native tests отдельно подтверждают queries/acceptance/terminal/errors/readonly/
  tokens/reopen. `--data-dir` не attach, standalone cancel требует live owner.
- Stdio MCP: `uv run --locked --no-sync python -m src.interfaces.cli server stdio`;
  real SDK child/tools/EOF и отдельный parity smoke подтверждены, stdout — protocol.
- Existing GUI source entry: `uv run --locked --no-sync python app.py`. Проверены
  actual offscreen MainWindow/run_desktop/shared HTTP/Qt actions/modal/settings и
  cleanup; это **не** новый native launcher/EXE/manual visual proof. Нельзя выдавать
  parser-only или source-tree/offscreen проверку за установленную сборку.

После technical ACCEPTED этот же Reviewer завершает только materially affected
factual docs/instructions и final-byte checks; runtime/tests/scripts и accepted
workflow bytes остаются frozen. Исторические bodies/RED и отдельные artifacts
не переписываются, текущий паспорт обновляется отдельно. Doc-only status sync
не запускает заново неизменённые product suites. Selective commit, literal remote
ref/SHA readback и observed exact-head CI записываются отдельно; zero jobs не PASS.

**Открытые пределы, не скрытые обязательные дефекты:** native Trash move/restore,
live YouTube/network/codec, Linux/configured Python3.12/pwsh7/hosted CI, EXE/manual
visual, whole legacy/native Qt privacy и произвольные иные logging configurations
не квалифицированы. Native capability/synthetic Trash/media не снимают этих границ.
Ни installs/downloads/sync, ни user-bin/profile/media/log reads, ни foreign kills/
ports, ни Goal/Pi/Hermes/global settings changes не выполнялись. Все own barriers/
workers/clients/listeners/leases/handlers освобождены finally/join/native exit;
watchdog emergency cleanup не потребовался. Согласованный offline-переход конечен
и завершён; новые возможности/платформенные доказательства требуют отдельного задания.
