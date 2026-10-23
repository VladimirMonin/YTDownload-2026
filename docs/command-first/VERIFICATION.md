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
