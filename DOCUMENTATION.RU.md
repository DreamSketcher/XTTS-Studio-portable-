# 📖 XTTS Studio — Документация

**[English](./DOCUMENTATION.EN.md)** · **[Русский](./DOCUMENTATION.RU.md)**

Технический справочник: архитектура, функции, данные, дерево проекта.

> Краткий обзор:  **[README.RU.md](./README.RU.md)** · **[README.EN.md](./README.EN.md)**  
> Справочник API: **[unified_function_reference.RU.md](./unified_function_reference.RU.md)** · **[EN](./unified_function_reference.EN.md)**

---

## Содержание

1. [О продукте](#о-продукте)
2. [Быстрый старт](#быстрый-старт)
3. [Пайплайн](#пайплайн)
4. [Возможности (подробно)](#возможности-подробно)
5. [RVC — улучшение голоса](#rvc--улучшение-голоса)
6. [Ядро TTS (`engine/tts/`)](#ядро-tts-enginettss)
7. [AI-модуль](#ai-модуль)
8. [Словарь произношений](#словарь-произношений)
9. [Диагностика и self-heal](#диагностика-и-self-heal)
10. [Система обновлений](#система-обновлений)
11. [Требования](#требования)
12. [Файлы данных и конфиги](#файлы-данных-и-конфиги)
13. [Структура проекта](#структура-проекта)
14. [Модули engine/ по зонам](#модули-engine-по-зонам)
15. [Разработка](#разработка)
16. [Сторонние компоненты / лицензии](#сторонние-компоненты--лицензии)

---

## О продукте

**XTTS Studio** — портативное полностью офлайн-приложение text-to-speech и клонирования голоса на **XTTS v2**.

- Точка входа: `XTTS Studio.exe` → BAT → `python\runtime\python.exe` → `gui.py`
- Зависимости: `python\xtts_env`
- Архитектура: тонкий entry · ядро `engine/` (без GUI) · UI `engine/gui/`

Опциональный **AI-модуль**: облачные OpenAI-compatible провайдеры и/или **локальные LLM** (без ключей, офлайн).

---

## Быстрый старт

1. Скачайте и распакуйте архив  
2. **Не** используйте путь с кириллицей  
3. Запустите `XTTS Studio.exe`  
4. Выберите референс (~10–20 с)  
5. Введите текст  
6. **🚀 ГЕНЕРИРОВАТЬ**  
7. Результат → `outputs/` (или **🎵 Аудио**)

```text
✔  C:\XTTS\
✘  C:\Новая папка\XTTS\
```

---

## Пайплайн

```text
Референс → автообработка → библиотека голосов (+ кэш эмбеддингов)
   ↓
Текст → (опц. GPT improve на сыром тексте) → normalize → word replacer
   ↓
(опц.) AI Conductor rewrite / per-chunk map
   ↓
Chunker (SBD / инициалы / merge-split) → (опц.) prosody / smart pauses*
   ↓
На каждый чанк:
   · XTTS inference (QC-ретраи при включённом QC)
   · (опц.) RVCPostProcessor на WAV чанка
   · ключ кэша чанка учитывает настройки RVC
   ↓
Merge + паузы → loudness normalize → de-esser → WAV / MP3
```

\* Smart pauses / prosody **пропускаются**, если активен AI Conductor (паузы из `conductor_map`).

**Важно:** RVC работает **на каждый чанк** после XTTS (не только на финальный файл). Де-эссер — один раз на **склеенном** экспорте.

---

## Возможности (подробно)

### Синтез и клонирование

- Полностью офлайн TTS  
- Portable-папка  
- Клонирование с короткого референса  
- Библиотека голосов + кэш эмбеддингов  
- Без жёсткого лимита длины текста  
- RU/EN контент  
- **CUDA по запросу**: CPU по умолчанию; **⚙ Настройки → Ускорение**  

### Интерфейс

- **⚙ Настройки**: обновления · ускорение CPU/GPU · диагностика  
- Темы dark/light + конструктор; immersive titlebar  
- Раскладка, dock-панели, auto-save  
- UI **RU / EN**  
- Размер шрифта ввода, neon glow  
- Авто-обновления: SHA256, backup, rollback  

### Текст

| Модуль | API | Заметки |
|--------|-----|---------|
| `normalizer.py` | `TextNormalizer.normalize`, `safe_character_filter` | Числа→слова, ординалы, время, аббревиатуры, **ёфикация** |
| `word_replacer.py` | `WordReplacer.apply`, `add_rule`, `remove_rule` | **builtin → auto → ai_corrected → custom**; JSON-only; бэкапы ≤30 |
| `chunker.py` | `TextChunker.chunk_text` | max 175 / target 150 / min 50; SBD для инициалов |
| `prosody_layer.py` | `ProsodyLayer.process` | Семантические паузы; **off при Conductor** |
| `smart_pauses.py` | `SmartPauseEngine.get_pause_ms` | Паузы merge; **off при Conductor** |

### Качество

- 4 пресета; UI вкладок **RVC · Обрезка · Вывод · XTTS** (sticky)  
- `quality_settings_last_tab` в `settings.json`  
- Встроенный браузер RVC-моделей: **Подборка · Новые · Топ**, live-поиск, preview до/после скачивания и очистка кэша  
- Параметрический RVC preview: текущие **Index · Pitch shift · f0** применяются к короткому фрагменту выбранного voice reference  
- QC, де-эссер (на merge), trim, кэш чанков (ключ включает RVC)  

**Сохранение (проверено):** `settings_ui.save_settings()` пишет всё дерево `quality_params` (включая `rvc_*`) через **read-modify-write**. Живые сессии уже хранят `rvc_enable`, `rvc_model`, `rvc_index_rate`, `rvc_pitch_shift`, `rvc_f0_method`.

### Прочее

Очередь задач, batch TXT, история, подсветка чанка, статистика, WAV/MP3.

---

## RVC — улучшение голоса

Опциональный этап **Retrieval-based Voice Conversion** после XTTS. Функциональность разделена на **setup** (установка в portable-окружение), **catalog/parser/cache** (поиск и жизненный цикл моделей), **pipeline** (инференс), а также **GUI-браузер моделей + общий аудиоплеер**.

### Пользовательский сценарий

1. Откройте настройки пресета и выберите вкладку **RVC**.
2. Включите **RVC пост-обработку**.
3. Откройте браузер моделей и выберите **★ Подборка**, **🆕 Новые**, **🔥 Топ** либо введите поисковый запрос.
4. Выделите строку и нажмите **▶**, чтобы прослушать короткий пример без скачивания checkpoint; **■** останавливает пример.
5. Нажмите **⬇** для прямой загрузки модели либо **🔗**, если источник требует браузера или ручного скачивания.
6. После скачивания модель появляется в локальном списке и сохраняет **▶ / ■**, если доступны метаданные источника и preview.
7. Кнопка **🧹** удаляет временные preview и остатки прерванных загрузок. Примеры установленных моделей сохраняются до удаления соответствующей модели.
8. Выберите локальную модель и настройте **Index**, **Pitch** и **f0 method** для текущего пресета.
9. Нажмите отдельную кнопку **▶ параметрического preview** непосредственно слева от списка модели. XTTS Studio применит текущие настройки к первым шести секундам выбранного voice reference в фоновом RVC-проходе, сохранит результат в кэш и проиграет его; **■** останавливает воспроизведение.

### Где вызывается RVC

В `engine/tts/__init__.py` → `run_tts()`:

1. `rvc_enable`, `rvc_model`, `rvc_index_rate`, `rvc_pitch_shift`, `rvc_f0_method` извлекаются из пресета, чтобы не попасть в XTTS `inference()`.
2. Эти значения включаются в **ключ кэша чанка** (`_rvc_*`), поэтому кэш не смешивает одинаковый текст с разными настройками RVC.
3. После записи WAV-чанка XTTS и успешного QC, если заданы `rvc_enable` и `rvc_model`:
   - `get_rvc_processor()` возвращает lazy singleton `RVCPostProcessor`;
   - `run_inference_via_lib(chunk_path, chunk_path, model_name=..., ...)` конвертирует чанк на месте.
4. При `RVCPipelineError` или неожиданной ошибке сообщение записывается в лог, а исходный XTTS-чанк сохраняется — генерация задания не прерывается.

Facade `engine/tts_runner.py` реэкспортирует `run_tts`, `get_tts`, `detect_device`, `word_replacer` из `engine.tts`.

GUI-вход: `engine/gui/generation.py` → `generate()` создаёт `Task` с полным `quality_params`, включая `rvc_*`, и передаёт его в `task_manager`.

### Классы пайплайна (`engine/rvc_pipeline.py`)

| Имя | Роль |
|-----|------|
| `RVCPipelineError` | Ошибка отсутствующей/невалидной модели, несовместимого API или инференса |
| `RVCPostProcessor` | Загружает `.pth` и опциональный `.index`, запускает `rvc-python` |
| `XTTSWithRVCPipeline` | XTTS → временный WAV → RVC → финальный путь; пропускает RVC, если модель не выбрана |

Производственный путь `RVCPostProcessor.run_inference_via_lib(...)`:

1. Ленивый импорт `rvc_python.infer.RVCInference`.
2. `load_model(model_path, version="v2", index_path=...)`.
3. `set_params(f0up_key=pitch_shift, f0method=..., index_rate=..., filter_radius=3, resample_sr=0, rms_mix_rate=0.25, protect=0.33)`.
4. `infer_file(input_path, output_path)` — **ровно два аргумента**; pitch сюда не передаётся.

Строки устройства нормализуются в `cpu:0` / `cuda:0`. Опциональный CLI-путь: `run_inference_via_cli` (`tools/RVC_CLI` или глобальный `rvc`).

**Отчёт о работе и проверка модели**

- Одна короткая стартовая строка показывает модель, CPU/CUDA, index ratio, pitch и f0 method.
- Одна строка завершения показывает имя выходного файла.
- Служебные `print()` и INFO-сообщения `rvc-python` / `fairseq` подавляются только на время RVC-инференса; значимые ошибки преобразуются в `RVCPipelineError`.
- До инференса `_validate_rvc_checkpoint` отклоняет пустой checkpoint и HTML/XML-страницу, ошибочно сохранённую с расширением `.pth`.
- При ошибке CLI stdout/stderr сокращается до последних полезных строк без известного служебного шума.

### Каталог, парсинг сайта, preview и кэш (`engine/rvc_catalog.py`)

У каталога три пользовательских источника. Все они нормализуются к единому формату entry, поэтому скачивание, preview, открытие страницы и локальные метаданные используют общий код.

| Каталог | Источник | Сетевое поведение |
|---------|----------|-------------------|
| **★ Подборка** | `json/rvc_catalog_seed.json` или `models/rvc/catalog_cache.json` | Работает офлайн; GitHub-каталог запрашивается только при отсутствии локальных данных или принудительном refresh |
| **🆕 Новые** | Первая страница публичной ленты voice-models.com (`fetch_data.php`, пустой search) | Загружается по запросу; in-memory кэш на 15 минут |
| **🔥 Топ** | Публичная таблица `https://voice-models.com/top` | Парсится по запросу; in-memory кэш на 15 минут |

#### Парсинг voice-models.com

Сайт используется как публичный индекс, но не является обязательной runtime-зависимостью:

1. `_parse_vm_table(html)` извлекает из строк таблицы id страницы, название, автора, размер и ссылку скачивания.
2. `_row_to_entry(row)` приводит запись к общей схеме каталога.
3. `browse_voice_models("new" | "top")` сохраняет порядок сайта и кэширует нормализованные записи.
4. `search_voice_models(query)` использует `fetch_data.php`; autocomplete служит fallback, если основной endpoint вернул слишком мало строк.
5. `search_catalog(...)` объединяет совпадения локального seed/кэша с live-результатами и удаляет дубли по id.
6. Ошибки сети обрабатываются мягко: локальные модели и офлайн-подборка остаются доступны.

Парсер распознаёт прямые Hugging Face `/resolve/`, `.pth` / `.zip` и Google Drive file links. Folder/page-only ссылки отображаются как **🔗 Открыть страницу**, а не как прямое скачивание.

#### Поиск аудиопримера

Preview не требует скачивания RVC checkpoint:

1. `can_preview(entry)` проверяет локально сохранённый sample, прямой preview URL или страницу модели voice-models.com.
2. `get_preview_url(entry)` запрашивает страницу лениво — только после нажатия **▶**.
3. `_PreviewAudioParser` выбирает настоящий источник `<audio id="vm-fit-audio" ...>`; URL аудио внутри script используется как fallback.
4. `get_preview_audio_path(entry)` загружает только короткий MP3/WAV/OGG/M4A с ограничением **32 MiB**.
5. Sample проигрывается внутри XTTS Studio через pygame. Если pygame недоступен, `open_preview(entry)` открывает поток в системном браузере.

Успешный preview URL кэшируется на 24 часа. Неудачный поиск — на 5 минут, чтобы временно недоступную страницу можно было повторно проверить позднее.

#### Параметрический preview по запросу

Отдельная кнопка рядом с выбором модели отличается от кнопок preview внутри списка. Она запускает настоящий локальный RVC-проход выбранной скачанной моделью:

1. Источник — текущий voice reference, а не уже сконвертированный пример с сайта.
2. Во временный WAV копируются максимум первые шесть секунд.
3. Текущие `rvc_index_rate`, `rvc_pitch_shift` и `rvc_f0_method` применяются в background worker через `get_rvc_processor()`.
4. Fingerprint кэша включает путь/размер/mtime референса, путь/размер/mtime модели, размер/mtime optional `.index` и все три параметра.
5. Полностью одинаковый запрос сразу использует WAV из `.parameter_preview_cache`; для одной модели сохраняется до шести последних вариантов.
6. **▶** создаёт или проигрывает preview, **■** останавливает через общий pygame-плеер. Если параметры изменились во время обработки, устаревший результат сохраняется в кэш, но автоматически не проигрывается.

`Index` влияет на звук только при наличии подходящего `.index`. Pitch shift и f0 method применяются и без index-файла.

#### Метаданные локальной модели

Модель, скачанная через каталог, получает sidecar:

```text
models/rvc/.metadata/<local_model_name>.json
```

Sidecar хранит id каталога, отображаемое имя, автора, source/page URL, локальное имя файла, preview URL и путь к закэшированному примеру. Поэтому скачанная модель сохраняет действие **▶ / ■** после исчезновения из списка удалённых результатов.

`get_local_model_entry(name)` также мигрирует ранее скачанные модели, если имя файла совпало с записью из:

- офлайн seed или дискового catalog cache;
- уже загруженного каталога **Новые** / **Топ**;
- live-поиска, выполненного в текущей сессии.

Вручную скопированный `.pth` не содержит встроенного demo-аудио. Если сопоставить его с каталогом или страницей не удалось, модель остаётся полностью рабочей для конвертации, но кнопка preview не показывается.

#### Жизненный цикл preview и partial-кэша

| Путь / маска | Назначение | Поведение при очистке |
|---------------|------------|-----------------------|
| `models/rvc/.preview_cache/` | Короткие примеры с сайта для ▶ внутри списка | Orphan/pre-download samples удаляются; примеры из metadata установленных моделей защищены |
| `models/rvc/.parameter_preview_cache/<model>/` | Локальные WAV с текущими Index/Pitch/f0 | Хранятся, пока модель установлена; незавершённые `.part` и orphan-каталоги очищаются; вся папка удаляется с моделью |
| `models/rvc/.metadata/*.json` | Источник и preview локальной модели | Не удаляются очисткой кэша; удаляются с соответствующей моделью |
| `models/rvc/*.part`, `*.part.*`, `*.partial`, `*.tmp`, `*.download`, `*.crdownload` | Прерванные загрузки и временные файлы | Удаляются кнопкой **🧹 Очистить кэш RVC** |
| `models/rvc/catalog_cache.json` | Дисковый кэш каталога | Не удаляется очисткой preview/partial-кэша |
| `models/rvc/*.pth`, `*.index` | Установленные веса и optional index | Никогда не удаляются очисткой кэша |

`clear_rvc_cache()` возвращает количество файлов и освобождённый объём. Функция удаляет orphan-preview, остатки прерванных загрузок, незавершённые parameter-preview `.part`, orphan-каталоги параметрического preview и забытые metadata `.tmp`. Website sample установленной модели и её готовые параметрические previews сохраняются до `delete_local_model(name)`; общий sample, на который ссылается другая установленная модель, не удаляется.

#### Публичный API

| Функция | Описание |
|---------|----------|
| `get_catalog(force_refresh=False)` | Сначала disk cache/seed; GitHub raw — только при отсутствии локального каталога или forced refresh; одна попытка и cooldown 6 часов |
| `browse_voice_models(mode, max_results=50, force_refresh=False)` | Парсинг публичных каталогов **Новые** / **Топ**, in-memory кэш 15 минут |
| `search_catalog(query, max_results=30, live=True)` | Локальный seed/cache, затем optional live search; дедупликация по id |
| `search_voice_models(query, ...)` | Поиск таблицы voice-models.com + autocomplete fallback; сетевые ошибки fail-soft |
| `can_preview(entry)` / `get_preview_url(entry)` | Определение и ленивое получение аудиопримера со страницы модели |
| `get_preview_audio_path(entry, force_refresh=False)` | Скачивание/повторное использование примера с сайта в `.preview_cache` |
| `get_parameter_preview_cache_path(model_name, fingerprint)` | Создание/получение пути к локальному параметрическому preview модели |
| `prune_parameter_preview_cache(model_name, keep=6)` | Ограничение числа закэшированных вариантов Index/Pitch/f0 одной модели |
| `open_preview(entry)` | Browser fallback для примера с сайта |
| `download_model(entry, progress_callback, cancelled_flag)` | HF `/resolve/`, прямые zip/pth, best-effort Google Drive file; из zip извлекаются самый большой `.pth` и подходящий `.index`; сохраняются metadata |
| `get_local_model_entry(name)` | Восстановление source/preview metadata локальной модели, включая legacy matching |
| `clear_rvc_cache()` | Очистка orphan-preview и interrupted downloads с защитой установленных моделей и их samples |
| `is_downloaded` / `local_model_path` / `delete_local_model` | Локальный lifecycle; `.pth` — каноническое имя, delete также обрабатывает `.index`, metadata и защищённый sample |
| `open_model_page(entry)` | Открытие непрямой model/folder page в браузере |

Обязательные поля entry: `id`, `name`, `url`. Опциональные: `filename`, `author`, `license`, `description`, `source`, `page_url`, `size`, `sha256`, `downloadable`, `catalog`, `preview_url`, `preview_cache_path`, `local_name`.

### Установка (`engine/env_core/rvc_setup.py`)

| Функция | Описание |
|---------|----------|
| `rvc_status()` | Subprocess-проверка импорта `RVCInference` |
| `install_rvc(progress_cb=None)` | Установка в portable `python/xtts_env/Lib/site-packages` |
| `uninstall_rvc(progress_cb=None)` | Удаление `rvc_python` и хвостов fairseq без удаления общих пакетов вроде `portalocker` |
| `detect_torch_build(site_packages)` | Определение того же варианта torch, что используется базовой установкой (`cu118` / `cpu`) |

Особенности установки под Windows:

- готовые fairseq wheels по версии CPython без сборки MSVC;
- `rvc-python --no-deps`, затем реальные зависимости из METADATA;
- constraints, не позволяющие повторно скачивать установленный torch+cu118/cpu;
- повтор без `--upgrade` при WinError 5;
- auto-heal отсутствующих модулей после установки;
- force-reinstall PyYAML.

### GUI-браузер моделей (`engine/gui/rvc_model_dropdown.py`)

`RVCModelDropdown` встроен в RVC-вкладку каждого пресета.

**Постоянные элементы**

- Trigger показывает текущую локальную модель и **▾**.
- Поиск использует debounce: сначала локальные результаты, затем live voice-models.com.
- Панель каталогов: **★ Подборка · 🆕 Новые · 🔥 Топ**. Выбор каталога очищает поисковый запрос.
- **🧹 Очистить кэш** после подтверждения удаляет orphan-preview и interrupted downloads, сохраняя установленные модели и их samples.
- Список построен на canvas со scrollbar и wheel-прокруткой.

**Действия строки**

| Тип строки | Действия после выделения |
|------------|--------------------------|
| Локальная модель с известными preview metadata | **▶ / ■** проиграть/остановить пример · **🗑** удалить модель |
| Локальная модель без preview metadata | **🗑** удалить модель |
| Удалённая модель с прямым файлом | **▶ / ■** preview · **⬇** скачать; во время скачивания **✕** отменяет |
| Удалённая page/folder без прямого файла | **▶ / ■** при наличии sample · **🔗** открыть страницу |

Активные кнопки создаются только для выделенной строки. Под действия заранее резервируется правая колонка, поэтому длинное имя обрезается и не выталкивает кнопки. После перерисовки сохраняется позиция списка, а активная строка остаётся видимой.

Preview использует общий `engine/gui/player.py`: sample из кэша загружается в `pygame.mixer.music`, **▶** меняется на **■**, естественное завершение возвращает **▶**. Запуск обычного reference-плеера останавливает RVC-preview и наоборот. Используется текущая громкость плеера.

Удалённая загрузка передаёт byte progress в status bar. После успешного скачивания новая локальная модель выбирается автоматически, а её page/preview metadata сохраняются для последующего прослушивания.

### Пресеты (`engine/gui/presets.py`)

Sticky tabs: **RVC · Обрезка · Вывод · XTTS**.

- RVC: включение, браузер модели, отдельная кнопка **▶ / ■ параметрического preview**, index, pitch, f0 method.
- Параметрический preview использует активный voice reference, выполняется асинхронно и повторно использует per-model кэш для одинаковых настроек.
- Вывод: формат, **де-эссер**, QC.
- Последняя вкладка хранится в `settings.json` как `quality_settings_last_tab`.
- Закрытие кнопкой или ✕ вызывает `save_settings`, поэтому RVC-поля сохраняются в `quality_params[preset]`.

Ключи пресета:

```text
rvc_enable, rvc_model, rvc_index_rate, rvc_pitch_shift, rvc_f0_method
```

Ключ окна: `quality_settings_last_tab` ∈ `rvc | trim | out | xtts`.

---

## Ядро TTS (`engine/tts/`)

| Символ | Файл | Роль |
|--------|------|------|
| `run_tts(...)` | `tts/__init__.py` | Полный job |
| `get_tts()` / `get_rvc_processor()` | `tts/__init__.py` | Lazy singleton'ы |
| `tts_runner.py` | корень | Re-export |
| QC helpers | `tts/qc.py` | repeats, duration, trim, loudness |
| `export_audio` | `tts/export.py` | Merge + de-esser + WAV/MP3 |
| `DeEsser` / `create_de_esser` | `engine/de_esser.py` | 4–9 kHz split-band |

QC: до **3** попыток при `qc_enabled`. Де-эссер: `export_audio` при `de_esser_intensity > 0`.

---

## AI-модуль

### Conductor — `ai_conductor.py`

`conduct(...)` → list / `{rewritten_text, chunks}` / None / fallback.  
Диапазоны: temperature 0.50–0.90, top_p 0.70–0.95, speed 0.75–1.25, pause 0–1200.  
`rewritten_text` только при `rewrite_enabled=True`. Транспорт: `_call_with_chain`.

### GPT client — `gpt_client.py`

`gpt_settings.json`. Цепочка: **active → builtins с ключом → custom**.  
`_call_with_chain`, `chat`, `improve_for_tts`, key library, `get_chain_diagnostics`.  
Исключения: `AIUnavailable`, rate limit / network.

### Локальные LLM — `local_llm_client.py`

GGUF in-process (`llama-cpp-python`). Каталог HF, download+resume, `call_local_llm` (CPU max_tokens ≤256). GPU→CPU fallback + broken backend.

### `gui.py`

Single-instance, `_ensure_dependencies_before_startup`, recovery UI, `main` + `updater.check_startup_health`.  
`llama_cpp` / `rvc_python` **не** critical.

---

## Словарь произношений

`WordReplacer`. Истина: `word_rules.json`.  
Приоритет: **builtin → auto → ai_corrected → custom**.  
Бэкапы ≤30. UI **📖 Словарь**. Conductor может писать `ai_corrected`.

---

## Диагностика и self-heal

Пакет **`engine/env_core/`** (re-export в `__init__.py` / facade `env_setup`).

| Модуль | Главное |
|--------|---------|
| `cpu_gpu.py` | `detect_cpu`, `detect_gpu` |
| `diagnostics.py` | `run_full_diagnostics` (изолированный процесс), `get_broken_critical`, `scan_for_garbage` + quarantine, `run_error_recovery`; CRITICAL vs OPTIONAL=`{llama_cpp,rvc_python}` |
| `torch_setup.py` | `install_torch` / `torch_status` / variant cu118\|cpu |
| `llama_setup.py` | cuda/vulkan/cpu, broken backends, smoke test |
| `rvc_setup.py` | install/probe RVC |

Startup: `gui.py` → full diagnostics → recovery только для critical.

---

## Система обновлений

**`engine/updater.py`** (не класс `Updater`).

| Функция | Описание |
|---------|----------|
| `check_update()` | Сравнение версий + files + sha256 + manual reinstall |
| `apply_update(...)` | staging → verify → backup → live → removed_files → marker |
| `check_startup_health()` | `ok` / `first_attempt` / `rolled_back` |
| `confirm_update_success()` | После успешного открытия GUI |
| `rollback_update()` / `restart()` | Откат / рестарт |

Отмена работает до подмены файлов. При `local < min_app_version` — полная переустановка.

---

## Требования

| | CPU | CUDA |
|---|---|---|
| ОС | Windows 10/11 x64 | то же |
| RAM | 8+ ГБ | 8+ ГБ |
| GPU | — | NVIDIA 4+ ГБ VRAM, CC 6.0+ |

---

## Файлы данных и конфиги

| Файл | Назначение |
|------|------------|
| `settings.json` | сессия, `quality_params` (вкл. **rvc_***), `quality_settings_last_tab`, тема, язык |
| `gpt_settings.json` | AI-провайдеры, ключи, модели |
| `word_rules.json` | словарь |
| `word_rules_backups/` | бэкапы словаря |
| `chat_history.json` / `history.json` | чат / генерации (history max 100) |
| `version.json` / `checksums.txt` | обновления |
| `json/rvc_catalog_seed.json` | офлайн-каталог **★ Подборка** |
| `models/rvc/*.pth`, `*.index` | установленные веса RVC и optional feature index |
| `models/rvc/catalog_cache.json` | дисковый кэш каталога |
| `models/rvc/.preview_cache/` | короткие примеры с сайта для ▶ внутри списка |
| `models/rvc/.parameter_preview_cache/<model>/` | локально рассчитанные preview текущих Index/Pitch/f0 на voice reference |
| `models/rvc/.metadata/*.json` | source/page/preview metadata скачанных локальных моделей |
| `.llama_broken_backends.json` / `.known_safe_files.json` | backend / diagnostics |

---

## Полная структура проекта (как в EN)

**Точка входа:** `XTTS Studio.exe` → BAT → `python\runtime\python.exe` → `gui.py` → `python\xtts_env`

```text
XTTS Studio (portable)
│
├── gui.py                        ← entry point: launches the interface only
├── i18n.py                       ← UI localization (RU / EN)
├── settings.json                 ← session settings (auto)
├── gpt_settings.json             ← AI provider, keys, models (auto)
├── word_rules.json               ← pronunciation dictionary
├── chat_history.json             ← AI chat session history
├── history.json                  ← generation history
├── version.json                  ← version and update-system data
├── env_cache.cfg                 ← environment-scan cache
├── generate_version_manifest.py  ← generates version manifest for updates
├── theme_settings.json           ← user theme/color scheme
├── checksums.txt                 ← SHA256 for update verification
├── .llama_broken_backends.json   ← broken llama.cpp backends (auto)
│
├── engine/                       ═══ TECHNICAL CORE (no tkinter) ═══
│   │
│   │   ── generation pipeline ──
│   ├── tts_runner.py
│   ├── chunker.py
│   ├── normalizer.py
│   ├── word_replacer.py
│   ├── text_utils.py
│   ├── smart_pauses.py
│   ├── prosody_layer.py
│   ├── de_esser.py
│   ├── rvc_pipeline.py           ← RVC post-process (rvc-python)
│   ├── rvc_catalog.py            ← RVC parsing / browse / preview / download / cache
│   │
│   │   ── AI module ──
│   ├── ai_conductor.py
│   ├── chat_window.py
│   ├── gpt_client.py
│   ├── local_llm_client.py
│   ├── env_setup.py
│   │
│   │   ── voice and audio ──
│   ├── reference_processor.py
│   ├── voice_manager.py
│   ├── audio_backend.py
│   │
│   │   ── infrastructure ──
│   ├── task_manager.py
│   ├── task_models.py
│   ├── batch_window.py
│   ├── updater.py
│   ├── paths.py
│   ├── settings_store.py
│   ├── history_store.py
│   ├── output_naming.py
│   ├── text_tools.py
│   └── logging_utils.py
│
│   ├── tts/
│   │   ├── __init__.py           ← generation core
│   │   ├── cache.py
│   │   ├── device.py
│   │   ├── export.py
│   │   ├── qc.py
│   │   └── utils.py
│   │
│   └── gui/                      ═══ INTERFACE (tkinter / customtkinter) ═══
│       ├── main_window.py
│       ├── layout.py
│       ├── theme.py
│       ├── theme_manager.py
│       ├── colors.py
│       ├── widgets.py
│       ├── tooltip.py
│       ├── gradient.py
│       ├── neon_widgets.py
│       ├── helpers.py
│       ├── header_panel.py
│       ├── voice_panel.py
│       ├── player.py             ← общий pygame-плеер reference + RVC preview
│       ├── queue_panel.py
│       ├── batch_panel.py
│       ├── chat_panel.py
│       ├── word_replacer_panel.py
│       ├── console.py
│       ├── textbox.py
│       ├── toolbar.py
│       ├── statusbar.py
│       ├── generation.py
│       ├── presets.py            ← quality presets + settings window (tabs)
│       ├── rvc_model_dropdown.py ← RVC browse / search / preview / cache UI
│       ├── settings_ui.py
│       ├── styles_menu.py
│       ├── updates.py
│       ├── chat_window.py
│       ├── ai_conductor.py
│       ├── ai_status_window.py
│       ├── history_window.py
│       ├── output_window.py
│       ├── batch_window.py
│       ├── word_replacer_window.py
│       ├── dialogs.py
│       └── chat_window/          ═══ modular AI chat ═══
│           ├── ...
│           └── engine/
│
├── json/
│   └── rvc_catalog_seed.json     ← offline RVC seed catalog
│
├── models/
│   ├── xtts_v2/                  ← XTTS model (offline)
│   └── rvc/
│       ├── *.pth / *.index       ← установленные RVC-модели
│       ├── catalog_cache.json    ← дисковый кэш каталога
│       ├── .preview_cache/       ← короткие примеры с сайта для ▶
│       ├── .parameter_preview_cache/ ← локальные WAV текущих Index/Pitch/f0
│       └── .metadata/            ← source/preview sidecar локальных моделей
├── library/<voice_name>/         ← voice profiles + embedding cache
├── outputs/_cache/               ← finished files + chunk cache
├── logs/
├── reference/
├── word_rules_backups/
├── test/                         ← pytest
├── tools/
├── ffmpeg/bin/
└── python/
    ├── xtts_env/
    └── runtime/                  ← Python 3.11 portable
```

> `engine/gui/chat_window.py` assembles the chat UI; `engine/gui/chat_window/` holds submodules and nested `engine/` for generation/sessions.

---


---

## Модули engine/ по зонам

### Пайплайн генерации

- `tts_runner` (facade) · `tts/*` · `chunker` · `normalizer` · `word_replacer` · `smart_pauses` / `prosody_layer` (off при Conductor) · `de_esser`.
- **`rvc_pipeline.py`** — `RVCPostProcessor` / `XTTSWithRVCPipeline` через `rvc-python`.
- **`rvc_catalog.py`** — парсинг Подборка/New/Top, live-поиск, website preview, parameter-preview cache, metadata, скачивание моделей и защищённая очистка кэша.
- **`gui/rvc_model_dropdown.py`** — вкладки каталогов, поиск, действия выбранной строки, preview/download/delete и кнопка 🧹.
- **`gui/presets.py`** — отдельная ▶ / ■ кнопка реального preview текущих Index/Pitch/f0 на voice reference.
- **`gui/player.py`** — общий pygame transport для voice reference и RVC preview.
- **`env_core/rvc_setup.py`** — установка, удаление и проверка portable RVC-окружения.

### AI
`ai_conductor` · `gpt_client` · `local_llm_client` · chat UI

### Голос
`reference_processor` (trim + SNR) · `voice_manager` · `de_esser`

### Инфраструктура

`task_manager` · `history_store` · `updater` · `settings_ui` · `env_core/*`.  
`i18n.py` содержит RU/EN-ключи каталогов, preview/playback и очистки RVC-кэша.

---

## Разработка

AI-assisted tooling; pytest в `test/`; утилиты в `tools/`.  
Архитектура и UI-полировка — с Arena.ai Agent Mode. Claude

Tests: **pytest** in `test/` (`RUN_TESTS.bat`)
platform win32 -- Python 3.11.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\XTTS Studio
configfile: pyproject.toml
plugins: timeout-2.4.0
timeout: 60.0s
timeout method: thread
timeout func_only: False
collected 621 items / 2 skipped

---

## Сторонние компоненты / лицензии

- **XTTS v2** (Coqui) — [CPML](https://coqui.ai/cpml)  
- Лицензия проекта: [LICENSE.md](./LICENSE.md)  
- Community RVC-модели — по своим лицензиям  

---

## Поддержка

**BTC:** `bc1qz78u3lvagt3v886359glv57ct6rnlh506wjmdy`

---

**XTTS Studio** · by EXIZ10TION · [README RU](./README.RU.md) · [README EN](./README.EN.md) · [EN docs](./DOCUMENTATION.EN.md) · [License](./LICENSE.md)