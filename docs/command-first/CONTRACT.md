---
id: ytdl-command-first-contract
title: "YTDownload — предлагаемый контракт Application API"
kind: contract
status: proposed
created: "2026-10-23"
updated: "2026-10-23"
areas: [application, contracts, lifecycle, persistence, safety]
summary: "Один прикладной владелец загрузок, честные принятие/завершение/отмена, безопасные файловые эффекты и совместимые адаптеры."
code_ref: "0abda8e2959b53561e8327f40c53118c944c94f8"
code_verified_at: "2026-10-23"
verification_scope: "S1–S3 независимо приняты, включая cancellation/outcomes/projection/task attribution и R1/R2 repair. Ниже также цели S4–S6, не полностью реализованный контракт; fresh/retained evidence — VERIFICATION.md."
related: [ytdl-command-first-plan, ytdl-project-philosophy]
---

# 1. Статус и единственный канон

Это **предлагаемый поведенческий контракт**, подготовленный Oracle по исходникам. Пользователь уже разрешил реализацию после плана в отдельной ветке; новой человеческой архитектурной approval-точки нет. Независимая приёмка реализации остаётся за назначенным Reviewer. План, scope и проверки — в [PLAN.md](PLAN.md); этот файл не второй roadmap.

**Code-first канон:** публичные сигнатуры `src/application/api.py::ApplicationAPI`, типы запросов/ответов в `src/application/dto.py` и существующие command DTO/errors в `src/application/command_api.py`, их `serialize_for_transport`. Документ определяет смысл и необходимые изменения этих owners. Не создавать параллельные OpenAPI/JSON-schema/command registry. `src/infrastructure/mcp/manifest.py` остаётся только каноном десяти имён MCP, не владельцем прикладных правил.

Provider — Application API с одним coordinator, репозиториями и явными инфраструктурными портами. Consumers — Python, CLI, MCP и существующие GUI managers. `main.initialize_app()` остаётся совместимым composition wrapper, а не API и не глобальным singleton. Прикладные/domain модули не импортируют Qt, argparse, FastMCP, uvicorn или конкретный yt-dlp backend. Стандартные `Path`, threading и локальные файловые чтения сами по себе не требуют отдельного framework.

# 2. Размещение, полномочия и время жизни

Выбран **B: управляемые задачи в одном процессе, с сохраняемой историей, но без восстанавливаемого исполнения**. Короткие queries/settings/delete — обычные операции A внутри того же приложения. Нет C-документа, D-workflow, брокера, нового демона или скрытого Attached-клиента.

| Режим | Авторитетный владелец | После ответа / закрытия |
|---|---|---|
| Прямой Python | Созданный caller-ом `ApplicationRuntime` | `queue_add_download` возвращает принятие; caller держит runtime до результата или явного shutdown |
| GUI `app.py` + встроенный HTTP MCP | **Тот же** runtime, API, coordinator, EventBus и repositories | Окончание MCP-запроса не отменяет Job. Выход приложения закрывает transport и кооперативно завершает принадлежащую runtime работу |
| Standalone HTTP / stdio MCP | Runtime этого серверного процесса | Job живёт между tool calls. Disconnect HTTP-клиента не отменяет Job. Завершение stdio-сервера/его процесса запускает shutdown; вечная работа после EOF не обещана |
| Standalone CLI `queue add` | Собственный headless runtime на время команды | Печатает acceptance, затем **явно ждёт** итог и освобождает runtime; не оставляет detached worker |
| CLI history queries/preview | Read-only снимок сохранённого JSON | Не создаёт executor, не восстанавливает и не переписывает историю. Снимок может отставать от ещё не сохранённого live результата |
| Встроенный вызов `cli.main(..., services=...)` | Переданный caller-ом runtime | Адаптер не закрывает чужой runtime; add возвращает acceptance без обязательного ожидания. Это локальное embedding, не межпроцессный Attached |

Каждый writable runtime получает **exclusive OS lease на канонический data root** до загрузки mutable caches. Второй writer получает `OWNER_BUSY`, а не запускает вторую очередь/затирает JSON. Реализация lease — небольшой stdlib-адаптер `msvcrt`/`fcntl`, с освобождением handle при close/аварийном выходе; lock-файл не удаляется ради «разблокировки». Read-only snapshot reader не требует writer lease и читает атомарно заменяемый файл.

Нет обещания управления GUI из отдельного CLI-процесса. Standalone `queue cancel` без внедрённого live owner возвращает **`OWNER_REQUIRED`**, не создавая пустой coordinator. Для уже работающего GUI доступен его существующий HTTP MCP endpoint. Standalone server на занятом data root отказывает; отдельный `--data-dir` означает **другую** сессию, не синхронизацию. Несколько явно выделенных data roots должны иметь раздельные output roots; многопроцессное согласование общего output между такими профилями здесь не вводится.

Локальная модель доверия остаётся single-user: Python/GUI/CLI действуют с правами запустившего их пользователя; MCP host отвечает за согласие пользователя перед `confirm=True`. Boolean/plan token **не удостоверяет человека**, MCP не sandbox. Не добавляются actor_id, аккаунты, remote-auth или автоматическая внешняя отправка. HTTP по умолчанию только `127.0.0.1`; явный иной host не получает новых гарантий безопасности. Утверждать, что неаутентифицированный HTTP безопасен для недоверенной сети, нельзя.

# 3. Runtime и сохраняемые данные

## 3.1 Сборка

Owner сборки, реализованный в S2, — `src/bootstrap.py::create_runtime`. Он принимает явный `data_root`, overrides настроек для synthetic исполнения и factories backend/file-remover, возвращает `src/application/runtime.py::ApplicationRuntime`. Environment читается **при сборке**, не при import. Достаточны keyword-only зависимости; универсальный DI framework не нужен.

- `data_root`: корень **YTDownloader**, содержащий `config/`, `data/`, `logs/`, а не сама подпапка `data`.
- Приоритет: явный аргумент / CLI `--data-dir` → `YTDL_DATA_DIR` → существующий `%APPDATA%/YTDownloader` (при отсутствии APPDATA — `Path.home()/YTDownloader`).
- Сохраняются `config/settings.json`, `data/history.json`, JSON `{next_id, entries}`, числовые IDs и существующие значения enum.
- Output default остаётся `Path.home()/Downloads/YTDownloader`. Tests обязаны назначать synthetic home до import либо передавать `AppSettings(output_dir=...)`.
- Entry adapters настраивают logging с явным runtime log path; `YTDL_LOG_DIR` поддерживается для subprocess isolation. API construction не открывает окно, порт или глобальный handler.
- Read-only factory не создаёт executor/lease, не выполняет recovery и не пишет отсутствующие settings/history. Отсутствующий history — пустой snapshot; повреждённый — ошибка, не «пустая история».
- `initialize_app()` возвращает прежние ключи dict и дополнительно `runtime`; `application_api` и `command_api` указывают на **один** facade. Legacy repo/coordinator keys — переходная совместимость, не разрешение адаптерам обходить API.

## 3.2 Запись

JSON repositories остаются JSON, без миграции в SQL. Запись: candidate state → собственный temp рядом с целевым файлом → flush/закрытие (fsync, где применим) → atomic replace → публикация нового cache. Исключение до replace сохраняет прежний JSON и cache; ошибка возвращается вверх. Повреждённые существующие данные не заменяются defaults. Читаются/возвращаются **отделённые копии**, не writable ссылки на cache.

Это защита от частично записанного JSON и потерянных обновлений внутри выбранного owner-а, **не** общая транзакция JSON+media+Recycle Bin и не гарантия против отказа диска/питания. `next_id` допускает пропуски после отказов, но не повторное использование уже выданного ID.

S2 добавил backward-readable `output_root`/`error_code`, S3 — `artifact_paths` и подтверждённую принадлежность результатов текущей задачи. Допустимые совместимые расширения `HistoryEntry`: `output_root` (snapshot root принятой работы), `artifact_paths` (точно известные результаты, в том числе нескольких элементов плейлиста), `error_code`. Старые файлы без них читаются с безопасными defaults; старая `output_dir` остаётся display/result folder, но **не полномочием удалить дерево**. Существующие поля/значения не переименовывать. Для playlist одиночные legacy media/sidecar fields по-прежнему представляют последний успешно обработанный элемент; полный известный набор — `artifact_paths`.

При открытии **exclusive writable owner**, после получения lease и успешного чтения, прежние `queued/downloading/merging` без живого исполнителя переводятся в `failed` с `error_code=INTERRUPTED`, безопасным объяснением и временем восстановления. Уже terminal записи не меняются. Никаких автоматических повторных загрузок, очистки `.part` или признания найденного файла успешным результатом. Неудача сохранения recovery блокирует mutable startup; read-only запрос может показать последний сохранённый snapshot с оговоркой об отсутствии live owner.

Реализованная S3 naming delta: реальный yt-dlp backend использует
`settings.output_dir.resolve()/download-<admitted task_id>/` как корень своей
попытки. Внутри него сохранены title/playlist templates и quality format selection.
Числовой ID резервируется единственным leased owner до backend admission и не
переиспользуется; отдельный path registry не вводится. AppSettings.output_dir и
HistoryEntry.output_root остаются выбранным parent root. Разные задачи не делят
одноимённые media/sidecars; поля результата/истории содержат actual absolute paths,
а не вычисление по title. Старые записи/файлы не перемещаются и не очищаются. Это
текущая гарантия S3 после R2, не отложенное обещание S4 и не sandbox/согласование
общего output разных profiles (ограничение §2 сохраняется).

# 4. Операции и queries

Существующие методы сохраняются. S2 типизировал commands/settings/history facade, S3 реализовал task/wait/live DTO и согласованные selection snapshots. Safe delete/полные adapters ещё S4/S5. В таблице — полная целевая граница, не обещание готовности всех будущих операций и не второй машинный реестр.

| Operation | Вход/defaults | Результат / эффект |
|---|---|---|
| `queue_add_download(...)` | Существующие keyword args; defaults `quality='720p'`, `download_type='video'`, subtitle_lang=None, три save-флага=False | `AddDownloadResult(task_id, status='queued')`: принятая и записанная в историю работа; **не** готовые файлы |
| `prepare_cancel_download(id)` | Положительный int, live owner | `CancelPreview`; без сигнала/смены статуса |
| `cancel_download(id)` | Тот же id; транспортное подтверждение отдельно | `CancelResult(status='cancel_requested')` либо известный refusal; см. §5 |
| `prepare_delete_download(id, delete_files=True)` | Явная цель и режим | `DeletePreview` со старым набором полей + точным списком, `plan_token`, missing/count сведениями; никаких изменений |
| `delete_download(id, delete_files=True, *, expected_plan=None)` | Повтор тех же параметров и token от preview; None оставлен в сигнатуре для контролируемой ошибки совместимости | `DeleteResult` только при полном известном завершении; без token — `CONFIRMATION_REQUIRED`, без эффекта |
| `list_downloads(status=None, limit=50)` | Limit clamp 1..200; неизвестный status сохраняет прежний пустой результат | `list[DownloadSummaryDTO]`, новые IDs первыми |
| `get_download(id)` / `get_file_paths(id)` | Положительный id | `DownloadDetailsDTO` или `QueryErrorDTO`; результат не запускает загрузку/поиск в сети |
| `search_downloads(query, limit=20, *, with_description=False)` | По title/playlist_title/URL без регистра; пустая/пробельная строка — весь набор | Limit 1..100, with_description 1..30; прежние DTO |
| `read_description(id)` | Только файл, привязанный к записи | `DescriptionResultDTO`; отсутствующий sidecar — text=None + hint, а не ошибка загрузки |
| `get_transcript(id, *, lang=None, raw=False, timestamps=False)` | Прежний выбор языка и VTT/SRT semantics; raw имеет приоритет над timestamps | `TranscriptResultDTO`; отсутствие subtitles — nullable text + hint; несовпавший язык — query error |
| `get_task(id)` / `list_tasks()` | Только текущий runtime | `TaskSnapshotDTO | QueryErrorDTO` / `list[TaskSnapshotDTO]`: detached status, title/url, progress, cancel_requested, known artifacts, error_code, result_persisted; не executor/Future |
| `wait_for_download(id, timeout=None)` | Python/standalone CLI; timeout >=0 или None | `TaskSnapshotDTO`; неизвестный id — CommandError/NOT_FOUND, нет live owner — OWNER_REQUIRED. Timeout возвращает текущий nonterminal snapshot и прекращает **ожидание**, не Job. Future наружу не возвращается |
| `list_history_entries(query=None)` | Локальный GUI consumer без прежнего ограничения 200 | Detached HistoryEntry list для существующих widgets; общая query semantics, не чтение UI-менеджером repo напрямую |
| `get_settings()` / `update_settings(settings)` | Detached AppSettings; не публикуется новым MCP tool/CLI деревом | Сохранённые настройки/ошибка; только после успешного save меняются defaults runtime |

### Валидация и особые значения

- ID — положительное целое, bool не ID. Ошибочный ввод не создаёт запись/Job и не меняет файлы.
- URL strip, http/https с непустым host. Сохраняется существующая возможность CLI/MCP передать такой URL yt-dlp; новый YouTube-only whitelist не вводится. GUI может сохранить существующий более узкий input hint/filter без переноса в него окончательной прикладной валидации.
- Quality/type: lower/strip; существующие `best,1080p,720p,480p,360p,audio` и `video,audio`; quality=audio нормализуется в best+audio. Это **одно** чистое правило, вызываемое всеми consumers.
- Для явного `None` в локальном Python/GUI вызове option берётся из settings snapshot; отсутствующие CLI/MCP параметры продолжают иметь объявленные выше старые defaults. `False` никогда не заменяется default=True. `subtitle_lang=None`/пустой код при включённых subtitles использует settings.subtitle_lang (обычно ru), а не означает «отключить subtitles».
- Settings: валидные enum/theme, непустой output Path, положительное целое max_concurrent; mcp_port 1..65535, без динамического перезапуска listener. Секретный proxy не нормализуется в log и не включается в диагностический результат.
- Изменение settings не меняет уже принятые задачи: **весь** AppSettings snapshot, включая output/proxy, фиксируется при admission. Max-concurrent нового пула применяется после полного drain старой очереди; одновременно действующих поколений executor не создаётся. Это ограниченное отложенное применение, не поддержка pause/resume.
- Text read limits сохраняются: description при search 8 KiB, read_description 64 KiB, transcript 1 000 000 символов. `truncated` относится к returned text; не обещать bounded memory там, где пока читается файл целиком. I/O failure становится безопасной query error. `get_file_paths` должен возвращать и реально сохранённый description_path (не терять его через summary mapper).
- None означает отсутствующее/неизвестное, [] — известный пустой список, 0 — действительный ноль. Неизвестные новые progress/count поля — None. Legacy callback progress/speed/eta сохраняет числовую совместимость bridge; неизвестный 0 не выдаётся за измерение в новой диагностике.

# 5. Принятие, выполнение, отмена, shutdown

## 5.1 Кто принимает решения

`DownloadCoordinator` остаётся единственным owner-ом task state; фабрика создаёт отдельный `IDownloadService` на задачу. Factory инжектируется composition root, не импортируется из application. Репозиторий отвечает за хранение, backend — за выполнение/артефакты, EventBus — за доставку уведомлений, GUI — за представление. Подписчик не вправе переписать статус.

До acceptance фиксируются normalized request/settings snapshot, устойчивый id, история queued и локальный task record с cancellation token. После этого работа может стартовать. Submit failure не оставляет «успешно принятую невыполняемую очередь»: возвращается `EXECUTION_UNAVAILABLE` с известным id/состоянием записи; доступная запись становится failed. Сохранение acceptance не прошло — backend **не запускается**. Не обещается exactly-once; повтор add без сверки создаёт новую работу.

`download.queued` доставляется раньше `download.started` для того же id, включая мгновенный backend. Реестр задач/futures устанавливается до допуска worker; завершение быстрее возврата submit не оставляет stale future. События публикуются вне state lock; ошибочный subscriber не отменяет уже принятое действие. EventBus делает thread-safe snapshot подписчиков и не исполняет callbacks под своим lock. Callbacks должны быть короткими, не ждать задачу синхронно.

## 5.2 Итоги backend

У `IDownloadService` появляется типизированный outcome (owner — domain protocol/model): **completed / cancelled / failed**, известные artifact paths, безопасный error_code. Пустой словарь **не** success и **не** скрытая отмена. Допустим compatibility mapping accessor для существующих внутренних consumers `.get('video')`; не возвращать transport DTO с Qt/FastMCP типами.

- Done требует: backend завершился успешно, имеется подтверждённый основной media artifact требуемого типа, итог/пути успешно сохранены в истории. Это не сертификат качества ролика: codec/звук/длительность проверяются отдельной media проверкой. `merging` выставляется только по фактическому postprocessing signal; если backend не сообщает этап, сохраняется downloading, а не ложная «сборка» перед всей загрузкой.
- Failed/cancelled могут иметь известные готовые и частичные файлы. Они сохраняются; автоматического удаления каталога/отката нет.
- Ошибка одного элемента playlist не превращает оставшиеся результаты в отсутствие эффекта. При известном частичном отказе итог `failed` + `PARTIAL_DOWNLOAD`, доступные файлы остаются в record. Недоступный необязательный sidecar сам по себе не делает основной media-result failed, но нельзя утверждать, что он сохранён.
- Backend учитывает фактический результат yt-dlp и postprocessing. Артефакты получаются из **этой** попытки/явно подтверждённого результата yt-dlp. `_find_newest_folder(output_root)` не источник принадлежности. Не сканировать чужое дерево ради заполнения пустого результата. Existing final files не перезаписывать молча; совпадение заголовка не доказывает, что файл принадлежит текущему видео.
- Сбой terminal persistence не скрывается. Live snapshot сообщает `result_persisted=False`, `error_code=PERSISTENCE_FAILED` и известные артефакты; `download.done` не публикуется. Физически закончившийся backend и сохранённый результат различаются. Runtime close может освободить ресурсы, но обязан вернуть/пробросить итоговую ошибку, не «всё сохранено».

В принятом S3 list/search несут одну detached пару entry/task через projection → query/status selection → limit → mapping: mapper не читает live state заново. Snapshot может устареть после capture, но его выбранные status/title/flags/artifacts не подменяются другой версией после фильтрации. Legacy/query-only shapes и None/0 различия сохраняются.

Live `get_download/list_downloads` используют authoritative task snapshot поверх last-saved record и добавляют nullable `cancel_requested`, `result_persisted`, `error_code`. Read-only process видит только last-saved JSON, без выдуманного live прогресса. После завершения процесса память/unsaved outcome не восстанавливаются; recovery §3 не обещает восстановить потерянные пути.

## 5.3 Отмена

Сохраняются enum `queued/downloading/merging/done/failed/cancelled`. Новое намерение `cancel_requested` — отдельное поле live snapshot, а не ложный terminal статус и не обязательный новый GUI state.

1. Queued: cancellation token фиксируется под owner lock. Если Future удалось снять до старта, task и history становятся cancelled; worker не вызывает backend. Если Future уже стартует, он обязан проверить тот же token до следующего внешнего шага.
2. Running: ответ `cancel_requested` означает только зарегистрированное намерение. История/событие cancelled не появляются, пока исполнитель ещё внутри fetch/download/postprocessing.
3. Token существует **до** создания/регистрации service; окно между submit и `_active_services` не теряет отмену. `YtDlpService.download` больше не очищает ранее поданный cancel event. Проверки — перед fetch, после fetch, перед download и в поддержанных hooks/между элементами.
4. Blocking metadata/FFmpeg/сторонний вызов может не прерваться немедленно. Нет гарантированного срока остановки и kill произвольного потока. После возврата backend owner принимает конечное решение и сохраняет его.
5. Completion/cancel сериализованы: terminal success раньше cancel → `ALREADY_TERMINAL`; cancel записан раньше окончательного успешного перехода → cancelled после прекращения исполнения, с сохранением известных файлов. Самостоятельная ошибка backend остаётся failed, не скрывается флагом отмены.
6. Повтор cancel при уже установленном намерении возвращает то же cancel_requested без второго эффекта; для уже cancelled — идемпотентный `CancelResult(status='cancelled')`; done/failed — conflict. Неизвестный id — NOT_FOUND; история без live задачи — OWNER_REQUIRED, не фиктивная отмена.

Отмена не Undo и не запрет уже допущенных media-записей. Ни `cancel_requested`, ни timeout ожидания не обещают, что после ответа не появится файл. Terminal cancelled означает quiescent работу **в пределах управляемого backend**, а не обратимость внешних эффектов.

## 5.4 Освобождение

Принятые S2/S3 реализуют `ApplicationRuntime.close(*, cancel=True, wait=True) -> ShutdownResultDTO`: owned/borrowed admission/join/lease, cooperative queued/active cancellation и terminal consistency. `wait=False` удерживает ownership до реального join. Transport/GUI finally ещё S5; это не hard stop deadline внешнего blocking call. Close идемпотентен. DTO содержит `closed: bool`, `pending_task_ids`, `persistence_error_ids`, `error_codes` (отделённые коллекции). Сначала закрывает admission; при cancel=True отменяет queued и сигнализирует active; wait=True дожидается собственных workers и записывает известные итоги, затем освобождает lease/owned handles. cancel=False — drain уже принятого, без новых admissions. wait=False возвращает состояние «ещё закрывается», а не completed cleanup; lease остаётся удержан до последнего writer-а. Финальный `close(wait=True)` обязателен у владельца процесса. `closed=True` означает освобождённые ресурсы, но не отменяет непустые persistence_error_ids/error_codes: entrypoint обязан сообщить ошибку/nonzero exit. При неполном cleanup closed=False, не ложный успех. Никакой `__del__`/interpreter exit не заменяет этот путь.

GUI detach происходит в closeEvent; shutdown request неблокирующий. После возврата Qt loop `app.py` в finally останавливает/join-ит **свой** embedded HTTP handle, затем завершает runtime. Standalone server использует тот же finally. Уже занятые чужие порты/процессы не закрываются; прежняя ограниченная попытка следующих портов может сохраняться с явным фактическим endpoint. Ошибка bind не маскируется успехом.

Пока backend игнорирует кооперативную остановку, процесс может ждать после закрытия окна; это честное ограничение. Не выдавать daemon thread, `shutdown(wait=False)` или истечение тестового timeout за завершённый shutdown. Tests обязаны управляемо отпускать synthetic backend в finally и проверять join.

# 6. Удаление: только согласованные известные файлы

Прикладной owner — `DownloadCommandAPI` (при необходимости helper `src/application/deletion.py`); конкретный OS trash — `IFileRemover` в domain protocol, инфраструктурная реализация. Нельзя оставлять fallback UI → repository.delete, обходящий эти проверки.

## 6.1 Preview и подтверждение

Preview фиксирует id, режим, detached version/fingerprint HistoryEntry, точные кандидаты и их lstat identity/size/mtime_ns, canonical root, сведения missing. `plan_token` — детерминированный digest этого плана, не секрет и **не право доступа**. Он работает между CLI-процессами без серверного plan registry. Изменение существенных inputs делает token stale; срок по часам/хранилище подтверждений не вводится.

Apply повторно строит план и сравнивает token **перед первым эффектом**, а mutable checks — также непосредственно перед каждым filesystem effect. Другой id/delete_files/root/набор файлов/изменённый файл → `STALE_PLAN`, без нового автоматического согласия. Уже отсутствующая запись → NOT_FOUND, не повтор удаления по сохранённому пути.

- CLI/MCP preview defaults сохраняются. Для apply нужны прежний confirm и **новый** `--plan-token` / `plan_token`. `--confirm` без token теперь безопасно отказывает. Это намеренное ужесточение, а не незаметная совместимость.
- Direct Python: `preview = api.prepare_delete_download(...)`, затем `api.delete_download(..., expected_plan=preview.plan_token)` — caller отвечает за разрешение пользователя.
- GUI не получает новый экран. Минимальная проводка готовит планы режимов **до существующего диалога**, а Yes/checkbox передают выбранный token. Если состояние изменилось во время диалога, показывается существующий путь ошибки и требуется новое подтверждение. Сам диалог, тема, layout, вкладки не перерабатываются.

## 6.2 Область эффекта

`delete_files=False` удаляет только логическую запись истории после проверок и успешной записи JSON, не трогает media. Active/nonterminal owned task нельзя удалить даже history-only: сначала отмена и фактический terminal, иначе worker потеряет запись для финализации.

`delete_files=True`:

- Только **явно перечисленные** artifact_paths либо legacy video/audio/subtitle/description/thumbnail/info_json paths. `output_dir` и его parent не превращаются в recursive delete; `rmtree` запрещён.
- Legacy entry только с папкой, без доказуемого списка, получает `UNSAFE_FILE_SCOPE`; доступны keep-files и ручное управление файлами вне этой операции. Не «достраивать» список обходом папки. У playlist со старыми одиночными путями будут обработаны только известные файлы, прочие остаются; preview это объясняет.
- Candidates — обычные файлы в разрешённом output root; reject volume root, home/data/project root как destructive target, каталоги, symlink/junction/reparse ancestry, выход за root, shared paths, на которые ссылаются другие записи. `Path` prefix как строка недостаточен. Root берётся из trusted runtime/зафиксированных при принятии настроек; произвольный путь во входе MCP не разрешён.
- Консервативный guard: файловое удаление не применяется, пока в этой области есть незавершённые downloads; оно не конкурирует с дописыванием результата. Read-only preview проверяет last-saved nonterminal records; apply — live owner и запись под общей mutation boundary.
- Удаление физического файла означает **перемещение в системную Корзину**, не permanent unlink. Минимальный cross-platform adapter может лениво использовать уже установленный `PySide6.QtCore.QFile.moveToTrash` без QApplication. Qt остаётся только в этом инфраструктурном адаптере, не импортируется core. Поддержка/ошибка проверяются; нет fallback на permanent delete и нет установки Send2Trash/другого пакета. Если Qt/Trash недоступен — `TRASH_UNAVAILABLE`, файлы и history сохранены.
- Папки/чужие/неучтённые файлы не трогать, даже если после операции остаётся пустая папка. Изменения файлов, замеченные между preview/apply, не уничтожаются. Враждебная одновременная подмена файлов вне процесса не объявляется решённой одним lstat: здесь локальная single-user, не OS sandbox/атомарная filesystem-транзакция.

## 6.3 Partial failure и повтор

Сначала подтверждённые файлы переносятся в Корзину по одному с учётом факта результата; **после** всех успешных перемещений/подтверждённых missing удаляется запись истории. Если очередной trash operation или history save не удался, запись сохраняется, насколько это подтверждено репозиторием; уже перемещённые файлы не возвращаются/не удаляются автоматически.

`DeleteResult` со старыми `id, deleted=True, files_removed` возвращается только для известного полного успеха. `files_removed=True` означает, что хотя бы один согласованный файл реально перемещён из исходного места в Trash, а не «вся папка уничтожена». При нуле existing candidates — False.

Partial/unknown outcome — `CommandError` с `code=PARTIAL_DELETE` или `PERSISTENCE_FAILED`, структурированным result: id, known history_deleted, per-file moved/missing/failed/unknown, counts, recovery=`repreview`. CLI exit1, MCP error payload, GUI ошибка без безусловного удаления карточки. Пути в явном результате операции допустимы, в диагностическом log — нет. Нельзя сообщать `deleted=True`, если JSON save не подтверждён.

После потерянного ответа или partial failure: перечитать запись/файлы → новый preview/token → новое подтверждение. Повтор старого token не должен затронуть новый/заменённый файл. Нет автоматического retry опасного действия и обещания exactly-once, durable trash receipts или Undo через API. OS Recycle Bin остаётся способом ручного восстановления; в offline tests OS-trash boundary заменяется принадлежащим fixture trash-каталогом с проверкой **сохранённых bytes**, не mock-флагом `called`.

# 7. Ошибки, транспорт и диагностика

`CommandError` сохраняет `message`/`hint`, получает стабильный `code` и при partial effect структурированный `result`. QueryErrorDTO сохраняет `error`/`hint`, добавляет `code`. Не делать клиентов зависимыми от raw exception текста. Предлагаемый конечный vocabulary:

| Код | Что известно / recovery |
|---|---|
| INVALID_ARGUMENT | Admission не состоялся; исправить ввод |
| NOT_FOUND | Цель не найдена у названного owner/snapshot |
| OWNER_REQUIRED / OWNER_BUSY | Нужен правильный live owner / root уже занят; без fallback на другую очередь |
| RUNTIME_CLOSING | Новые изменения не принимаются |
| ALREADY_TERMINAL / ACTIVE_DOWNLOAD | Состояние не допускает действие; перечитать |
| CONFIRMATION_REQUIRED / STALE_PLAN / UNSAFE_FILE_SCOPE | Файловый эффект не разрешён текущим планом; новый preview/keep-files |
| STORAGE_CORRUPT / PERSISTENCE_FAILED | Не притворяться пустым store/успешной записью; при известном эффекте сообщить его |
| EXECUTION_UNAVAILABLE / DOWNLOAD_FAILED / PARTIAL_DOWNLOAD / INTERRUPTED | Известная стадия отказа, сохранённые артефакты не скрывать |
| TRASH_UNAVAILABLE / PARTIAL_DELETE / ARTIFACT_READ_FAILED | Известная или частичная файловая операция; recovery по §6 |
| INTERNAL_ERROR | Безопасная техническая ошибка; не raw str(exc)/traceback в ответе |

Нет единого `retryable=True` для всех временных ошибок. Add может дублировать работу; delete требует repreview; cancel повторим в указанной области. Потерянный transport response не доказывает отсутствие эффекта.

### CLI

Сохраняются `python -m src.interfaces.cli`, console script `ytdl`, группы queue/history/server, существующие positional args/флаги/форматы, wrapper `mcp_stdio_server.py`, legacy module HTTP entrypoint. Добавляются только `--data-dir` и deletion plan-token. `--preview` не применяет effect даже вместе с confirm.

- stdout — запрошенный результат, JSON остаётся одним JSON-документом, не log/progress stream. Для standalone add это прежний acceptance `{task_id,status:'queued'}` с flush; терминальный результат можно прочитать по id.
- Exit0 standalone add означает последующее известное done+persisted; ошибка/отмена/потеря persistence — exit1 и безопасный error result в stderr с id. Не менять acceptance.status на `done` задним числом и не печатать второй JSON в stdout.
- Exit0 для query/preview — выполнен именно query/preview. Exit1 — runtime/domain/partial failure. Exit2 — argparse usage. Interrupt — прекращение ожидания с cancel+cleanup собственных задач, не «готово»; сохранить существующий runtime-error exit1.
- Внедрённые services caller owns: add exit0 только acceptance; caller сам ждёт/закрывает. Tests обязаны различать эту границу и настоящий subprocess CLI.
- Server stdio не печатает banner/business prints в stdout. HTTP startup message — диагностика stderr, не result JSON. Не накапливать безграничный StringIO ради `--json`.

### MCP

Все десять имён и существующие аргументы/defaults сохраняются. `search_with_description` остаётся адаптацией общего search, не второй query implementation. Регистрируются методы одного API. `create_mcp_server` живёт в инфраструктурном MCP module, CLI bootstrap только вызывает/реэкспортирует; MCP не зависит от CLI parser/bootstrap как semantic owner.

Дополнительный аргумент delete plan_token и безопасные codes — описанное расширение. `confirm=False` только preview; `confirm=True` без корректного token не удаляет. Transport cancellation не равна `cancel_download`. Протокольные Tasks/новый tool для Job Manager не вводятся. Real stdio call с synthetic store обязателен отдельно от discovery.

### Логи

Канон — [logging.instructions.md](../../.github/instructions/logging.instructions.md). Значимые события acceptance/start/cancel_requested/terminal/persist_failed/shutdown связываются task id; допустимы enum/code, stage, count и elapsed_ms, но не URL, proxy, title, path, content, raw exception/cause/traceback. Backend/third-party diagnostics проходят безопасный logger adapter, не прямой stderr с пользовательским URL. Ошибка subscriber не печатает его payload/exception text.

Проверяется настоящий непустой stdout/stderr/file handler output после flush с synthetic sentinels. Полный privacy-audit всех сторонних библиотек/всех исторических GUI сообщений не обещан; все **изменённые и соединённые** runtime/adapter error paths обязаны соблюдать политику. Retention/rotation не меняются самовольно.

# 8. Совместимость и доказательство

Сохраняются входы, десять MCP tools, old result keys, JSON locations/форматы, theme/layout и назначения GUI controls. S3-R2 намеренно добавляет task-ID prefix новым backend paths (§3.2); paths старых записей остаются читаемыми, полагаться на прежнее расположение новых файлов по title нельзя. Обоснованные изменения поведения: writer lease вместо потерянных updates; явное ожидание standalone CLI; отказ standalone cancel без owner; cancellation request вместо преждевременного terminal; fail-closed storage; no empty success; file-only Trash+plan token вместо recursive permanent deletion. Это обязательная миграционная дельта, не маскируемая словом «рефакторинг».

До runtime acceptance должны быть выполнены connected proofs из [PLAN.md](PLAN.md): direct API без UI/SDK, реальные repositories/readback, детерминированные races отмены/быстрого завершения, реальный CLI subprocess, реальные MCP stdio tool calls на synthetic store, offscreen GUI bridge над тем же owner, cleanup/следующая операция, file preservation и реальные log sinks. Подменяются внешние сеть/yt-dlp и в основных tests системная Корзина, **не** Application API/coordinator/repository.

Этот контракт не утверждает runtime PASS всей миграции. Исторические Oracle/S1/S2 результаты сохранены в [VERIFICATION](VERIFICATION.md). S3 независимо принят после двух source findings: текущие original/adapted controls, five repaired cases и51 affected cases passed; прежние82/177/full-mypy34/four smokes применимо retained, не новые прогоны/суммы. Scoped type2 PASS не отменяет inherited global raw1/34 findings. S4 safe delete, S5 complete adapters и S6 final matrix ещё не реализованы/не приняты. Live YouTube, codec quality, Linux runtime/CI, packaged EXE, native Trash, whole legacy privacy и ручной визуальный GUI — NOT_RUN; Markdown их не заменяет.
