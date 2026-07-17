"""
engine/rvc_catalog/__init__.py — публичный фасад каталога RVC-моделей (TASK-008).

Раньше это был монолитный engine/rvc_catalog.py (~1550 строк). Реализация разбита
на подмодули по ответственности (см. критерии TASK-008):
  • _constants.py — пути, константы, общие хелперы и глобальные кэши;
  • sources.py    — seed/кэш/GitHub + парсинг voice-models.com + поиск;
  • downloader.py — скачивание .pth/.zip (HF /resolve/, Google Drive, zip-извлечение);
  • preview.py    — демо-аудио и параметрический preview;
  • metadata.py   — .metadata/<model>.json и модель доверия RVC-чекпоинта;
  • cache.py      — lifecycle кэшей, clear_rvc_cache, delete_local_model.

ВНИМАНИЕ: импортный путь `from engine import rvc_catalog` и все имена, которые
использовали внешние модули и тесты (включая приватные, monkeypatch-аемые
константы/кэши), сохранены 1:1. Подмодули обращаются к подменяемым именам через
объект этого пакета, чтобы тестовый monkeypatch.setattr(rvc_catalog, ...) оставался рабочим.

Подробности — в docstring каждого подмодуля.
"""

# Порядок важен: сначала константы/состояние, затем подмодули, которые их используют.
from engine.rvc_catalog import _constants as _constants  # noqa: F401

# ── Константы и пути (источник: _constants) ──────────────────────────────────
from engine.rvc_catalog._constants import (  # noqa: F401
    BASE_DIR,
    SEED_CATALOG_PATH,
    RVC_MODELS_DIR,
    RVC_PREVIEW_CACHE_DIR,
    RVC_PARAMETER_PREVIEW_CACHE_DIR,
    RVC_METADATA_DIR,
    CATALOG_CACHE_PATH,
    PREVIEW_MAX_BYTES,
    RVC_ARCHIVE_MAX_MEMBERS,
    RVC_ARCHIVE_MAX_EXTRACTED_BYTES,
    RVC_ARCHIVE_MAX_COMPRESSION_RATIO,
    CATALOG_RAW_URL,
    VOICE_MODELS_HOME_URL,
    VOICE_MODELS_TOP_URL,
    VOICE_MODELS_FETCH_URL,
    VOICE_MODELS_SEARCH_URL,
    VOICE_MODELS_UA,
    MAX_RETRIES,
    SEARCH_MAX_RESULTS,
    SEARCH_PAGES,
    VM_SEARCH_TIMEOUT,
    VM_SEARCH_ATTEMPTS,
)

# ── Глобальные кэши (скалярные + dict). Тесты патчат скалярные на этом пакете. ──
from engine.rvc_catalog._constants import (  # noqa: F401
    _vm_search_fail_log_until,
    _github_catalog_fail_until,
    _github_catalog_fail_logged,
    _local_catalog_cache,
    _preview_url_cache,
    _browse_catalog_cache,
    _known_entry_cache,
)

# ── Общие хелперы ──────────────────────────────────────────────────────────────
from engine.rvc_catalog._constants import (  # noqa: F401
    _load_json,
    _sha256_of_file,
    _cleanup_tmp,
    _path_is_inside,
    _download_is_html_error,
)

# ── sources.py ─────────────────────────────────────────────────────────────────
from engine.rvc_catalog.sources import (  # noqa: F401
    _validate_catalog,
    _load_local_catalog,
    _fetch_remote_catalog_once,
    _save_cache,
    get_catalog,
    _clean_download_url,
    _safe_filename_stem,
    _guess_filename,
    _is_direct_downloadable,
    _vm_request,
    _parse_vm_table,
    _row_to_entry,
    _remember_catalog_entries,
    browse_voice_models,
    search_voice_models,
    search_catalog,
)

# ── downloader.py ──────────────────────────────────────────────────────────────
from engine.rvc_catalog.downloader import (  # noqa: F401
    local_model_path,
    is_downloaded,
    _gdrive_file_id,
    _resolve_download_url,
    _download_gdrive,
    _download_bytes_to_file,
    _extract_rvc_from_zip,
    download_model,
)

# ── preview.py ─────────────────────────────────────────────────────────────────
from engine.rvc_catalog.preview import (  # noqa: F401
    _PreviewAudioParser,
    _entry_page_url,
    can_preview,
    _normalize_preview_url,
    get_preview_url,
    get_preview_audio_path,
    open_preview,
    _parameter_preview_model_dir,
    get_parameter_preview_cache_path,
    prune_parameter_preview_cache,
    _delete_parameter_preview_cache,
)

# ── metadata.py ────────────────────────────────────────────────────────────────
from engine.rvc_catalog.metadata import (  # noqa: F401
    _metadata_path_for_local_name,
    _save_local_model_metadata,
    _entry_matches_local_name,
    get_local_model_entry,
    is_local_model_trusted,
    trust_local_model,
)

# ── cache.py ───────────────────────────────────────────────────────────────────
from engine.rvc_catalog.cache import (  # noqa: F401
    _installed_preview_paths,
    clear_rvc_cache,
    delete_local_model,
    open_model_page,
)
