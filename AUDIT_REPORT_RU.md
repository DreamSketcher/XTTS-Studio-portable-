# Полный аудит XTTS Studio

**Дата:** 15 июля 2026  
**Репозиторий:** `DreamSketcher/XTTS-Studio`  
**Коммит:** `5f64084db685f43c2811bc9e21d2dbec9e085a3b` (`Update`, 2026-07-15 19:58:47 +0300)  
**Объём:** 199 отслеживаемых файлов, около 58 172 строк Python  
**Среда аудита:** Linux/Python 3.13; целевая платформа проекта — Windows 10/11, Python 3.11.

## 1. Резюме

Проект функционально богат, хорошо документирован и имеет заметно более зрелые тесты, чем типичный desktop AI GUI. Есть staging/backup/rollback обновлений, SHA-256, таймауты, отмена задач, CPU fallback, CI на Linux и Windows, Ruff/Black и большое число модульных тестов.

Однако **перед безопасным публичным распространением portable-сборки необходимы исправления**. Наиболее серьёзны:

1. пути из удалённого update-манифеста не ограничены корнем приложения;
2. update-манифест и его хэши получаются из одного неподписанного канала;
3. community RVC-модели принимаются без обязательного хэша и потенциально загружаются как PyTorch checkpoints;
4. API-ключи хранятся открытым текстом;
5. зависимости содержат большое число известных уязвимостей;
6. CI допускает частично установленное окружение и поэтому не гарантирует воспроизводимость результата.

**Итоговая оценка:** **6/10 — пригодно для разработки и контролируемого локального использования, но не hardened-дистрибутив.**

## 2. Что проверено

- структура, архитектура и точки входа;
- updater, загрузчики моделей, работа с файлами и сетью;
- хранение секретов и пользовательских данных;
- зависимости и supply chain;
- CI, тесты, lint/format;
- документация и лицензирование;
- статическая компиляция всех Python-файлов;
- Ruff, Black, Bandit, pip-audit;
- попытка запуска pytest в доступной среде.

Не выполнялись: полноценный запуск GUI/аудиогенерации на Windows, CUDA/RVC/XTTS inference, анализ поведения готового EXE в Windows sandbox и динамический malware-анализ всех внешних моделей/колёс.

## 3. Критические и высокие риски

### P0 — Path traversal в автообновлении

**Где:** `engine/updater.py:247`, `:248`, `:316`, `:345`, `:359–368`, `:601–608`.

`files` и `removed_files` принимаются из удалённого `version.json`, после чего путь строится через `os.path.join(BASE_DIR, rel.replace(...))`. Проверки, что итоговый путь остаётся внутри `BASE_DIR`, нет. Значения вроде `../outside/file` или абсолютный путь способны привести к записи, удалению, резервному копированию или восстановлению файлов вне каталога приложения.

Это особенно опасно, потому что updater обновляет исполняемый Python-код и EXE.

**Исправление:** единая функция `safe_app_path(rel)`:

- отклонять абсолютные пути, `..`, пустые/служебные сегменты и Windows drive/UNC paths;
- вычислять `candidate = (BASE_DIR / rel).resolve()`;
- проверять `candidate.is_relative_to(Path(BASE_DIR).resolve())`;
- применять проверку ко всем `files`, `removed_files`, staging, backup и rollback до любых операций;
- добавить негативные тесты для `../`, `C:\`, UNC, mixed separators и symlink/reparse-point сценариев.

### P0 — Недостаточная аутентификация канала обновлений

**Где:** `engine/updater.py:20–32`, `:92–129`, `:149–194`, `:408–522`.

SHA-256 защищает от случайной порчи, но манифест и ожидаемые хэши загружаются из того же GitHub-репозитория. Компрометация аккаунта/репозитория, токена релиза или ветки позволяет одновременно заменить код и хэши. Привязка к commit SHA предотвращает CDN race, но не подтверждает доверенного автора релиза.

**Исправление:** подписывать release manifest офлайн-ключом (Ed25519/minisign/Sigstore), встроить только публичный ключ в приложение и проверять подпись до чтения списка файлов. Обновляться с immutable release artifact/tag, а не с `main`. Добавить key rotation и минимально допустимую версию updater.

### P0/P1 — Недоверенные RVC `.pth` без обязательной целостности

**Где:** `engine/rvc_catalog.py:1158–1174`, `:1347–1434`; источник — публичный community-каталог.

Для community-моделей SHA-256 опционален. `.pth` исторически является pickle-совместимым форматом PyTorch; загрузка недоверенного checkpoint способна привести к выполнению кода, если downstream RVC loader использует небезопасный `torch.load`. Даже если загрузчик находится во внешней RVC-зависимости, приложение само доставляет файл в доверенный каталог моделей.

**Исправление:**

- не позиционировать community `.pth` как безопасные;
- использовать safetensors, где возможно;
- для PyTorch применять `weights_only=True` и строгую проверку ожидаемой структуры;
- разрешать автоматическую установку только из curated allowlist с обязательным SHA-256/подписью;
- показывать явное предупреждение перед первой загрузкой неподписанной модели;
- запускать конвертацию/проверку в изолированном subprocess с минимальными правами.

### P1 — Секреты хранятся открытым текстом

**Где:** `engine/gpt_client.py:302–313`, `:351–431`; файл `gpt_settings.json`.

Активные API-ключи и библиотека именованных ключей записываются в обычный JSON. Любой процесс пользователя, backup/sync tool или случайно отправленный диагностический архив может их прочитать.

**Исправление:** Windows Credential Manager/DPAPI через `keyring`; в JSON хранить только provider/key ID. При миграции удалить plaintext после успешного переноса. Явно исключить секреты из диагностики и добавить permission check.

## 4. Средние риски

### P1 — 58 известных уязвимостей в 6 зависимостях

`pip-audit -r requirements.txt --no-deps` сообщил **58 advisory** для `diskcache 5.6.3`, `msgpack 1.1.2`, `nltk 3.9.4`, `pillow 12.2.0`, `torch 2.2.2`, `transformers 4.38.2`.

Особенно проблемны старые `torch` и `transformers`. Часть advisories зависит от конкретно используемых функций, но текущий lock не может считаться безопасным.

**Исправление:** сформировать совместимую обновлённую матрицу XTTS/TTS/torch/transformers; отделить core и optional зависимости; добавить `pip-audit`/OSV Scanner в CI; документировать временно принятые исключения с причиной и сроком.

### P1 — Небезопасная десериализация embedding cache

**Где:** `engine/tts/utils.py:300`.

`torch.load(cache_path, map_location=device)` вызывается без `weights_only=True`. Если злоумышленник способен подменить cache `.pth`, возможна pickle-десериализация.

**Исправление:** `torch.load(..., weights_only=True)` при поддерживаемой версии или хранить массивы в safetensors/NumPy; проверять типы, shape, dtype и конечные значения.

### P1 — Произвольные URL AI-провайдеров и загрузки моделей

**Где:** `engine/gpt_client.py:270–290`, `:623`; `engine/local_llm_client.py:238–319`.

Пользовательские provider/model URLs не ограничены HTTPS. Допускаются `http://`, `file://` и потенциально обращения к loopback/LAN. Для desktop-приложения это не классическая удалённая SSRF, но вредоносная конфигурация/импорт настроек может читать локальные ресурсы или отправлять API-ключ на недоверенный endpoint.

**Исправление:** HTTPS по умолчанию; явное подтверждение для HTTP/localhost; запрет `file:`, `ftp:` и неизвестных схем; показывать hostname перед сохранением ключа; не следовать redirect с HTTPS на HTTP.

### P1 — CI скрывает ошибки установки

**Где:** `.github/workflows/ci.yml:55–63`.

`pip install -r requirements.txt || true` превращает ошибку зависимостей в успешный шаг, после чего ставится небольшой набор пакетов. Тесты могут проходить в окружении, не соответствующем релизу.

**Исправление:** убрать `|| true`; создать `requirements-core.txt`, `requirements-test.txt`, optional extras/constraints; отдельно тестировать минимальное и полное окружение. Добавить проверку сборки portable artifact.

### P2 — Нет хэшей для Python-зависимостей

Версии закреплены, но колёса не закреплены хэшами. Некоторые optional wheels берутся со стороннего GitHub Pages/release URL.

**Исправление:** lock-файлы по платформам с `--require-hashes`; SBOM (CycloneDX/SPDX); provenance релизов; allowlist индексов; проверка SHA-256 внешних wheels до установки.

### P2 — Большое число проглоченных исключений

Bandit зафиксировал сотни `try/except/pass`; всего найдено 816 low findings. Для GUI best-effort это иногда оправдано, но в updater, диагностике, очистке и работе с данными исключения могут скрывать потерю состояния.

**Исправление:** ловить конкретные исключения; писать structured log; отличать ожидаемый best-effort от нарушения инварианта; запретить новые broad exceptions линтером хотя бы в security-sensitive модулях.

## 5. Качество и архитектура

### Сильные стороны

- хорошее разбиение core на `engine/tts`, `env_core`, GUI-модули;
- модульные тесты updater, cancellation, rollback, RVC catalog и text pipeline;
- атомарные `.part`/`os.replace` во многих загрузчиках;
- timeout/retry/backoff и cancellation;
- updater проверяет обязательный SHA-256 каждого файла;
- Ruff и Black проходят без ошибок;
- `python -m compileall` проходит;
- CI запускается на Linux и Windows;
- документация RU/EN подробная и реалистичная.

### Проблемы сопровождаемости

1. **Дублирование/переходная архитектура chat UI.** Одновременно существуют `engine/chat_window.py`, `engine/gui/chat_window.py`, package `engine/gui/chat_window/` и сходные `chat_messages.py`. Это повышает риск исправить неиспользуемую копию.
2. **Крупные модули:** `rvc_catalog.py` ~1 517 строк, `gpt_client.py` ~950, diagnostics и GUI-модули также велики.
3. **Глобальное mutable state** и прямые файловые операции затрудняют параллелизм и тестирование.
4. **Настройки записываются неатомарно** в некоторых местах (`gpt_settings.json`): crash во время записи может повредить файл.
5. **MD5 используется для cache keys** (`engine/tts/cache.py`, `engine/tts/__init__.py`). Это не криптографическая проверка и потому не является высокой уязвимостью само по себе, но лучше использовать BLAKE2/SHA-256 или явно `usedforsecurity=False`, чтобы не вводить аудиторов в заблуждение.

**Рекомендация:** определить единственную canonical chat implementation, удалить/заархивировать legacy shims, добавить dependency-injected storage/network clients и атомарный settings store с locking.

## 6. Тесты и результаты инструментов

| Проверка | Результат |
|---|---|
| Clone/commit | успешно |
| `compileall` | успешно |
| Ruff 0.6.9 | успешно |
| Black 24.10.0 `--check` | успешно, 161 файл без изменений |
| Bandit | 830 findings: 3 high, 11 medium, 816 low; MD5 highs являются cache-key findings, наиболее важны `torch.load` и URL/file handling |
| pip-audit | 58 advisories / 6 packages |
| pytest в sandbox | полный прогон не завершён: среда имеет Python 3.13 и не содержит целевой torch/TTS/FFmpeg stack |

Первоначальная коллекция pytest также выявила, что тестовое окружение не bootstrap-ится отдельным лёгким manifest. После установки лёгких зависимостей оставалась обязательная зависимость от `torch` уже при импорте `engine.tts`, что подтверждает сильную import-time связанность.

Нельзя трактовать неполный локальный pytest как падение продукта: CI проекта рассчитан на Python 3.11 и отдельную установку CPU torch. Но это указывает на необходимость воспроизводимого dev/test setup.

## 7. Документация, приватность и лицензия

- README честно разделяет offline core и сетевые функции.
- Следует добавить отдельный Privacy/Security раздел: какие данные уходят AI-провайдерам, где лежат ключи, история, voice references и модели.
- Нужна `SECURITY.md` с private disclosure process и поддерживаемыми версиями.
- `LICENSE.md` — нестандартная source-available лицензия с субъективным критерием «существенной доработки» и правом автора решать спор. Это может осложнить корпоративное использование и не является OSI-лицензией. Стоит явно назвать её **source-available**, а не open source, и получить юридическую проверку.
- Необходимо сформировать third-party notices и SBOM, включая Coqui XTTS CPML, RVC/fairseq, FFmpeg и модели; коммерческие права на голос/модели должны быть явно отделены от лицензии приложения.

## 8. План исправлений

### Первые 48 часов

1. Закрыть path traversal во всех updater paths и написать regression tests.
2. Отключить автозагрузку неподписанных community `.pth` либо добавить жёсткое предупреждение.
3. Перевести embedding cache на безопасный формат/`weights_only=True`.
4. Не логировать и не включать `gpt_settings.json`, history и voice references в отчёты.

### 1–2 недели

1. Подписанный immutable update manifest.
2. DPAPI/Credential Manager для API-ключей.
3. Обновить уязвимые зависимости и внедрить pip-audit/OSV gate.
4. Исправить CI: убрать `|| true`, разделить manifests, добавить Windows artifact smoke test.
5. Валидация схем URL и redirect policy.

### 1–2 месяца

1. Удалить дубли chat UI и разделить крупные модули.
2. Добавить атомарный settings store + file locking.
3. SBOM, third-party notices, release provenance и подпись EXE/архива Authenticode.
4. Windows sandbox smoke/integration tests для updater, FFmpeg, XTTS, RVC, CPU/CUDA fallback.
5. `SECURITY.md`, threat model и release security checklist.

## 9. Статус исправлений после аудита

В рабочую копию внесён первый security patch:

- добавлена fail-closed нормализация путей update-манифеста;
- запрещены `..`, абсолютные, drive/UNC, ADS/colon, пустые и неоднозначные пути;
- одинаково обрабатываются `/` и `\\` на всех ОС;
- итоговые пути staging/live/backup/rollback проверяются через `Path.resolve()` на принадлежность разрешённому корню, включая существующие symlink;
- `files` и `removed_files` проверяются до сетевых и файловых операций;
- запрещены дубликаты и одновременное обновление/удаление одного пути;
- rollback повторно валидирует локальный marker;
- embedding cache загружается через `torch.load(..., weights_only=True)` со строгой проверкой схемы;
- добавлены regression tests traversal, Windows drive/UNC, alternate separators, symlink escape и overlap.

Дополнительный P1 patch:

- API endpoints принимают только HTTPS; незашифрованный HTTP разрешён исключительно для явного loopback (`localhost`, `127.0.0.1`, `::1`);
- запрещены URL credentials, fragments, `file:`, `ftp:` и прочие схемы;
- проверка применяется при добавлении/редактировании custom provider, загрузке списка моделей и перед фактическим API-вызовом;
- `gpt_settings.json` теперь записывается атомарно через временный файл, `fsync` и `os.replace`;
- RVC `model_name` больше не может содержать traversal, абсолютные/drive/ADS пути или готовое расширение;
- реальные пути `.pth`/`.index` проверяются на принадлежность `models_dir`;
- ZIP RVC ограничен числом элементов, размером распаковки и коэффициентом сжатия;
- `.pth`/`.index` извлекаются через временные файлы с атомарной финализацией.

Результат расширенной targeted regression suite: **144 passed**. Ruff, Black и `git diff --check` проходят.

Третий этап hardening:

- добавлены `SECURITY.md` и `PRIVACY.md`;
- добавлен детерминированный CycloneDX 1.5 SBOM (`sbom.cdx.json`) и генератор `tools/generate_sbom.py`;
- CI проверяет наличие security/privacy документов и точное воспроизведение SBOM;
- из CI удалён `pip install ... || true`: установка полного release requirements теперь fail-closed;
- Windows/Linux matrix продолжает запускать полный pytest, включая updater traversal и GUI smoke tests;
- обновлены `msgpack` 1.1.2 → 1.2.1 и Pillow 12.2.0 → 12.3.0, число advisories `pip-audit` сократилось с 58 до 52 (оставшиеся относятся к 4 пакетам).

Результат текущей security regression suite: **153 passed**. Ruff, Black и `git diff --check` проходят.

Четвёртый этап hardening:

- update manifest теперь подписан Ed25519 offline-ключом (`version.json.sig`);
- updater загружает манифест и подпись с одного commit-pinned URL и проверяет точные байты встроенным public key до JSON parsing и применения;
- unsigned, изменённый или повреждённый manifest отклоняется fail-closed;
- повторное чтение манифеста после применения привязано к тому же commit SHA;
- CI проверяет действительность committed manifest signature;
- создан offline private key вне репозитория (`/home/user/XTTS-Studio-signing-private.pem`, mode 0600); он не включается в portable bundle и должен быть передан владельцу через защищённый канал;
- API credentials переведены на Windows DPAPI (`CryptProtectData`/`CryptUnprotectData`) с application entropy;
- активные ключи и key library сохраняются только в защищённом envelope;
- legacy plaintext credentials автоматически мигрируют при первом чтении;
- на не-Windows системах production fallback в plaintext отсутствует; отдельный test-only backend включается только явной переменной окружения.

Regression для signature, tampering, invalid signatures, credential encryption и plaintext migration проходит.

Пятый этап hardening — RVC trust gate:

- любой `.pth` checkpoint теперь запрещено загружать до явного подтверждения пользователя;
- GUI показывает отдельное предупреждение о pickle/PyTorch риске для скачиваемых и вручную добавленных моделей;
- подтверждение сохраняется в sidecar trust record и криптографически привязано к SHA-256 точных байтов checkpoint;
- замена или изменение `.pth` автоматически аннулирует доверие;
- library и CLI RVC paths используют один fail-closed trust check;
- удаление модели удаляет и trust record;
- скачанная модель не активируется, если явное подтверждение отсутствовало или trust record не удалось записать.

Расширенная regression suite: **150 passed**; отдельно проверяются отказ unsigned checkpoint и аннулирование доверия после изменения файла.

Шестой этап — dependency security baseline:

- `torch` 2.2.2 → 2.11.0, `torchaudio` 2.2.2 → 2.11.0, `torchvision` 0.17.2 → 0.26.0;
- CUDA baseline `cu118` → `cu128`, минимальная CUDA 12.8; несовместимые системы fail over на CPU;
- `transformers` 4.38.2 → 5.13.1 и `tokenizers` 0.15.2 → 0.22.2;
- устаревший `TTS==0.22.0` заменён поддерживаемым namespace-compatible `coqui-tts==0.27.5`;
- `nltk` 3.9.4 → 3.10.0;
- неиспользуемый `diskcache` удалён, исключив pickle cache attack surface;
- `pip-audit` baseline сократился с 52 advisories до одного upstream advisory без fixed version;
- CVE-2025-3000 оформлен как узкое временное исключение в `SECURITY_BASELINE.md`: описаны exposure, compensating controls, residual risk, срок пересмотра 2026-08-15 и условие удаления;
- CI fail-closed запускает `pip-audit`; любые новые advisory ID ломают сборку;
- добавлены тесты согласованности requirements, installer constants, CUDA baseline и отсутствия diskcache.

Результат gate: **No known vulnerabilities found, 1 ignored**. Исключение считается обоснованным и ограниченным по сроку.

Седьмой этап — UI performance, фаза 1:

- `AnimationManager` переведён в event-driven режим: в простое отсутствует `after()` timer;
- первый active animation запускает ровно один tick loop;
- отмена последней анимации и `stop_all()` немедленно отменяют pending timer;
- scheduler учитывает реальную стоимость Tcl/Tk redraw и вычитает её из задержки следующего кадра вместо fixed-delay drift;
- добавлена лёгкая telemetry: target FPS, active count, last tick time, frames и dropped frames;
- добавлены headless unit tests на true-idle, single timer, cancellation и telemetry.

Результат UI regression фазы 1: **98 passed, 11 display-dependent skipped**.

UI performance, фаза 2a — progress throttling:

- добавлен thread-safe monotonic `ProgressThrottle`;
- частота RVC download progress ограничена 10 обновлениями/с вместо callback на каждый 64-КБ блок;
- 0% и 100% доставляются без задержки;
- одинаковые значения coalesce, percentage clamp ограничен диапазоном 0–100;
- lambda захватывает immutable percentage, исключая отображение более нового mutable значения;
- throttler сбрасывается перед каждой новой загрузкой;
- добавлены unit tests rate limit, boundary delivery, duplicate coalescing и reset.

Совместная UI/RVC regression фазы 2a: **125 passed, 11 skipped**.

UI performance/stability, фаза 2b — main-thread bridge:

- добавлен `UIThreadBridge` с thread-safe queue и UI-owned poller;
- worker threads больше не вызывают Tk `after()` для RVC catalog, live search, preview download, model download progress и completion;
- producer lifecycle гарантирует автоматический true-idle после доставки последнего события;
- несколько одновременных workers используют один poller;
- callbacks обрабатываются ограниченными batch, чтобы не монополизировать event loop;
- destroy trigger отменяет poller и очищает очередь;
- исключение одного UI callback не блокирует последующие события.

Regression фазы 2b: **143 passed, 11 skipped**.

UI performance, фаза 3 — layout coalescing:

- RVC dropdown больше не выполняет три layout pass на каждый render (немедленно + 10 мс + 50 мс);
- rapid search/selection renders объединяются в один `after_idle` callback, предыдущий pending callback отменяется;
- удалены синхронные `inner.update_idletasks()` из scroll refresh и active-row visibility;
- при закрытии popup pending layout callback отменяется;
- Windows titlebar setup больше не вызывает `update()` и не запускает nested event loop; используется только geometry flush через `update_idletasks()`;
- аналогичная nested-loop проблема устранена в chat dialog titlebar setup.

Regression фазы 3: **162 passed, 11 skipped**.

UI performance, фаза 4a — incremental RVC rows:

- создан registry уже построенных row widgets по стабильному key;
- выбор модели больше не вызывает `_render_rows()` и не уничтожает весь список;
- обновляются только две строки: предыдущая active и новая active;
- action slot остаётся стабильным, пересоздаются только его компактные action/preview buttons;
- повторный клик по уже активной строке не выполняет layout/render работу;
- прокрутка к новой active row планируется через `after_idle`;
- full rebuild сохранён только для реального изменения dataset: search/catalog/download/delete.

Regression фазы 4a: **131 passed, 11 skipped**, включая old/new-only patch и same-row no-op.

UI performance, фаза 4b — progressive catalog rendering:

- первый viewport (до 12 remote rows + local rows) строится синхронно для мгновенного открытия;
- оставшиеся remote results добавляются batch по 8 строк с паузой 8 мс, уступая event loop input и animation frames;
- новый поиск/render отменяет pending batch; stale render token не создаёт ни одного виджета;
- закрытие popup отменяет pending batch callback;
- wheel bindings применяются только к новым строкам, без повторного обхода всего дерева;
- добавлены метрики initial render time, total render time, row count, batch count и render count;
- snapshot метрик готов для debug overlay и дальнейшего выбора размера widget pool.

Regression фазы 4b: **134 passed, 11 skipped**.

UI performance, общий прогон по приложению:

- создана карта `UI_PERFORMANCE_PLAN.md`: 137 `after`, 34 `update_idletasks`, 25 worker thread sites и 16 `<Configure>` hot paths классифицированы по приоритету;
- прямые GUI `update()` полностью устранены (0 nested event loops);
- chat input resize + token count + placeholder sync объединены в один отменяемый 60-мс debounce вместо полного чтения текста на каждую клавишу;
- status и stage deduplicate одинаковые значения, global progress ограничен 12 Hz с гарантированными 0/100;
- из generation textbox handshake удалены два ненужных synchronous geometry flush;
- delayed chat scroll больше не вызывает `update_idletasks()` перед scrollregion update;
- console stdout/stderr переведена с `after(0)` на каждую строку на thread-safe queue pump;
- console группирует до 64 сообщений за batch и объединяет соседние строки одного severity в один Text.insert; `see()` вызывается один раз за batch;
- idle console pump работает с низкой частотой, под нагрузкой переключается на 16 мс; worker `write()` не касается Tk.

Regression объединённого прогона 1: **89 passed, 12 skipped**.

UI performance, объединённый прогон 2:

- добавлен reusable `ConfigureCoalescer`: resize storms сводятся к последнему размеру через один `after_idle`, микрошум меньше заданного pixel threshold игнорируется;
- coalescer подключён к canonical AI chat canvas: scrollregion, canvas-window width и wraplength больше не пересчитываются на каждый промежуточный `<Configure>` event;
- coalescer подключён к AI settings scroll canvas, удалён дополнительный `update_idletasks()`;
- waveform canvas окна Outputs redraw выполняется coalesced и игнорирует изменения меньше 3 px;
- waveform worker Outputs переведён с `win.after(0)` из worker thread на `UIThreadBridge`;
- history waveform futures также доставляют результаты через `UIThreadBridge`; close уничтожает bridge до executor shutdown;
- bridge lifecycle исключает callbacks после закрытия окон и объединяет несколько одновременных waveform producers.

Regression объединённого прогона 2: **94 passed, 11 skipped**.

UI performance, объединённый прогон 3:

- canonical AI chat window создаёт один `UIThreadBridge` на весь lifecycle окна и уничтожает его до teardown дочерних окон;
- main AI response worker больше не вызывает `_safe_after`/Tk из background thread; response, error и final cleanup доставляются упорядоченно через bridge queue;
- editor «улучшить текст» и отдельный editor preview worker переведены на тот же bridge;
- producer counting удерживает poller только пока операции активны и корректно обслуживает одновременные AI requests;
- cancellation token и исходный порядок response/error/final cleanup сохранены без изменения AI/provider логики;
- Outputs и History waveform bridges подтверждены как active-only: poller существует только при незавершённых waveform producers; playback timers уже запускаются только при `playing/get_busy` и останавливаются при pause/end/close.

Regression объединённого прогона 3: **106 passed, 11 skipped**.

UI performance, объединённый прогон 4 — environment workers:

- `EnvSettingsWindow` получил один lifecycle-bound `UIThreadBridge` и общий `_start_worker` с producer accounting;
- targeted package repair, dependency status scan, garbage scan/delete, recovery и Torch install workers больше не вызывают `self.after(0)` из background threads;
- заменено 30 worker-side `after(0)` delivery sites на queue-based `_post_ui`;
- destroy окна сначала уничтожает bridge, блокируя late callbacks после teardown;
- pip/Torch/RVC progress text ограничен 8 Hz отдельным throttler, при этом глобальный progress остаётся 12 Hz;
- последовательность disable/progress/result/dialog/release-lock сохранена, environment/install бизнес-логика не изменялась;
- nested delete producer корректно создаётся из UI callback после scan result.

Regression объединённого прогона 4: **65 passed** по env/diagnostics/torch/RVC/bridge suites.

UI performance, объединённый прогон 5:

- local GGUF catalog download worker переведён на lifecycle chat `UIThreadBridge`; success/pause/error/progress больше не вызывают Tk из worker;
- local model progress label ограничен 8 Hz, download/cancel/resume логика не изменена;
- batch status tracker убрал пять лишних `after(0)` внутри уже UI-thread polling callback и обновляет StringVar только при фактическом изменении значения;
- добавлен global motion profile: `ultra`, `balanced`, `performance`, `reduced`, `off` с env/settings source;
- neon pulses и header rainbow/author/underline учитывают профиль; decorative effects полностью отключаются в performance/reduced/off, интервалы масштабируются в balanced;
- gradient resize переведён на `ConfigureCoalescer`, стартовый `update_idletasks` удалён;
- вертикальный gradient теперь строится как полоса 1×H и расширяется в C-коде Pillow вместо H линий шириной W; performance/off используют solid background.

Regression объединённого прогона 5: **141 passed, 11 skipped**.

UI performance, критический long-chat fix:

- UI пузырь хранит полный message content для session/API/copy/editor, но первоначально вставляет максимум 8000 символов;
- длинные сообщения раскрываются страницами по 8000 символов кнопкой «Показать ещё», поэтому один Text widget не получает мегабайты данных за один event;
- bubble width measurement ограничен 40 строками и 800 символами на строку вместо полного прохода по тексту;
- удалён патологический Tcl `count -displaylines` + synchronous layout; высота вычисляется bounded O(displayed text) estimate с cap 80;
- session history строится cancellable batch по 6 сообщений/8 мс, новый session switch отменяет старый render;
- при session render больше не создаётся scroll callback для каждого bubble; wrap/scroll/token выполняются один раз после финального batch;
- chat-history token count кэшируется по session/message tail signature и не пересчитывает всю длинную историю каждые 60 мс при вводе.

Long-chat regression первой фазы: **41 passed**.

UI performance, long-chat virtualization + motion UI:

- session window ограничен последними 40 сообщениями, поэтому initial widget count не зависит от полной длины истории;
- старые сообщения доступны страницами по 40 через «Показать предыдущие», полный session data не удаляется;
- после подгрузки older page viewport остаётся сверху, обычное открытие сессии скроллит к последним сообщениям;
- внутри visible window сохраняется progressive batch 6 сообщений/8 мс и render-token cancellation;
- добавлен глобальный selector motion profile в Theme Customizer: ultra/balanced/performance/reduced/off;
- выбор сохраняется в `settings.json`, применяется live к motion policy и подхватывается neon/header refresh без изменения core logic.

Targeted regression предыдущего этапа: **111 passed, 11 skipped**.

UI performance, settings API + History paging:

- API-key validation worker считывает Tk variable до старта thread и доставляет result/error через lifecycle chat bridge;
- request token не позволяет медленному старому validation result обновить уже перестроенную provider card;
- History больше не создаёт до 100 Canvas-heavy cards и waveform jobs при открытии;
- initial History page ограничен 20 карточками, создание идёт batch по 5/8 мс;
- следующие страницы по 20 добавляются только по кнопке, полный history store не меняется;
- waveform resize каждой видимой карточки coalesced с threshold 3 px;
- close отменяет pending history batch, все resize callbacks, waveform bridge и executor work.

Targeted regression предыдущего этапа: **53 passed**.

UI performance, adaptive frame-quality monitor:

- `AnimationManager` хранит rolling 240 frame samples и вычисляет average/p95, dropped frames и sample count;
- balanced profile автоматически переходит во временный `adaptive` режим только после двух устойчиво медленных окон (p95 > 135% frame budget);
- восстановление требует шесть устойчиво хороших окон — hysteresis исключает переключение туда-сюда;
- ultra никогда не понижается автоматически; performance/reduced/off остаются явным выбором пользователя;
- adaptive не отключает эффекты резко, а увеличивает интервалы примерно в 2.5 раза, сохраняя визуальную непрерывность;
- header rainbow/author/underline и neon pulse читают effective policy на каждом tick и реагируют без рестарта;
- telemetry snapshot расширен avg/p95/sample/adaptive state и готов для debug overlay.

Adaptive regression: **106 passed, 11 skipped**.

Финальный infrastructure/UI пакет:

- добавлен optional performance overlay (`XTTS_UI_PERF=1`) с motion profile, last/avg/p95 frame time, active animations, dropped frames и sample count; refresh 500 мс, полностью отсутствует по умолчанию;
- overlay уничтожается до AnimationManager при закрытии;
- добавлен deterministic release builder: проверяет Ed25519 manifest, path confinement, наличие и SHA-256 каждого payload file, сортирует ZIP entries, фиксирует timestamps/permissions/compression;
- два локальных build дали byte-identical archive SHA-256 `4642694cbbc0642724df2c51b5e7c7e6d73673fba719c6be13285aa11204cf71`;
- добавлен Windows `Secure Release Gate`: release блокируется, если `Get-AuthenticodeSignature` не возвращает `Valid`; затем проверяются manifest signature и двойная reproducible build;
- workflow публикует только прошедшие gate ZIP, SHA-256, SBOM и signed manifest.

Regression: **79 passed, 11 skipped** + deterministic archive test.

AI chat UX patch по пользовательскому скриншоту:

- default chat geometry изменён с 1180×820 на 780×850, minsize 680×620;
- sidebar и chat area переведены в horizontal `PanedWindow`; sash можно перетаскивать, sidebar min 145 px, default 190 px;
- session history font уменьшен с 13 до 11 scaled pt;
- AI settings window уменьшено с 960×700 до 500×460 (min 430×380), content остаётся scrollable;
- wheel events над Text/bubble/meta/avatar направляются в chat Canvas вместо блокировки Text widget;
- scroll step ускорен 3→9 units, animation 200→95 ms и easing заменён на `ease_out_cubic`.

UX regression: **80 passed, 11 skipped**.

Main TTS sidebar animation patch:

- sidebar width animation больше не вызывает synchronous `update_idletasks` и не commit-ит 60 full-layout widths;
- ширина quantized примерно в 18 geometry commits, duration 190 ms, `ease_out_cubic`; tracked visual width исключает forced geometry measurement;
- show/hide и live side switch обновляют один tracked width, одинаково для left/right;
- console collapse/expand теперь анимирует четыре card heights синхронно одним progress timeline;
- card resize ограничен 16 geometry commits/210 ms; повторный toggle отменяет прошлую animation и стартует с текущих heights;
- финальные listbox heights/font/pack state применяются один раз после transition; лишний master `update_idletasks` удалён.

Sidebar regression: **70 passed, 11 skipped**. Reproducible build criterion закрыт на уровне tooling/workflow. Authenticode gate закрыт, но текущий EXE нельзя считать подписанным до предоставления code-signing certificate и успешного Windows workflow.

## 10. Критерии готовности безопасного релиза

- traversal-тесты updater проходят на Windows и Linux;
- манифест обновления подписан и проверяется до применения;
- ни один неподписанный pickle/PyTorch checkpoint не загружается без явного доверия пользователя;
- API-ключи отсутствуют в plaintext;
- нет необоснованных critical/high advisories в runtime dependencies;
- полное окружение устанавливается без игнорирования ошибок;
- portable artifact собран воспроизводимо, подписан и проходит Windows smoke test;
- опубликованы SBOM, SECURITY.md и privacy disclosure.
