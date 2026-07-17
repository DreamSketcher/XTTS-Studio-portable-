"""
engine/rvc_catalog/metadata.py — метаданные локальных моделей + trust (TASK-008).

.metadata/<model>.json (источник и preview для показа ▶ у локальной модели),
восстановление записи из seed/кэша для ранее скачанных моделей, и привязка
доверия RVC-чекпоинта к SHA-256 (делегируется engine.rvc_pipeline).
Перенесено дословно из монолитного engine/rvc_catalog.py.
"""

import json
import os

from engine import rvc_catalog as _pkg
from engine.rvc_catalog import _constants as _C
import contextlib


def _metadata_path_for_local_name(name: str) -> str:
    safe_name = os.path.basename(str(name or "").strip())
    return os.path.join(_C.RVC_METADATA_DIR, f"{safe_name}.json")


def _save_local_model_metadata(entry: dict, model_path: str = "") -> bool:
    """Сохраняет источник и preview для показа ▶ у локальной модели."""
    try:
        resolved_path = model_path or _pkg.local_model_path(entry)
        local_name = os.path.splitext(os.path.basename(resolved_path))[0]
        if not local_name:
            return False
        os.makedirs(_C.RVC_METADATA_DIR, exist_ok=True)
        allowed = (
            "id",
            "name",
            "url",
            "filename",
            "author",
            "license",
            "description",
            "source",
            "page_url",
            "preview_url",
            "preview_cache_path",
            "size",
            "downloadable",
        )
        metadata = {key: entry.get(key) for key in allowed if entry.get(key) is not None}
        metadata["local_name"] = local_name
        metadata["filename"] = os.path.basename(resolved_path)
        target = _metadata_path_for_local_name(local_name)
        temp_target = target + ".tmp"
        with open(temp_target, "w", encoding="utf-8") as output:
            json.dump(metadata, output, ensure_ascii=False, indent=2)
        os.replace(temp_target, target)
        return True
    except Exception:
        return False


def _entry_matches_local_name(entry: dict, local_name: str) -> bool:
    try:
        candidate = os.path.splitext(os.path.basename(_pkg.local_model_path(entry)))[0]
        return os.path.normcase(candidate) == os.path.normcase(local_name)
    except Exception:
        return False


def get_local_model_entry(name: str):
    """Возвращает метаданные локальной модели, включая источник preview."""
    local_name = os.path.basename(str(name or "").strip())
    if not local_name:
        return None

    metadata = _C._load_json(_metadata_path_for_local_name(local_name))
    if isinstance(metadata, dict):
        entry = dict(metadata)
        entry.setdefault("id", f"local_{local_name}")
        entry.setdefault("name", local_name)
        entry.setdefault("filename", f"{local_name}.pth")
        entry["local_name"] = local_name
        return entry

    # Миграция старых скачиваний: восстановление записи из seed/кэша и из
    # уже загруженных в этой сессии каталогов New/Top.
    candidates = []
    with contextlib.suppress(Exception):
        candidates.extend(_pkg._load_local_catalog())
    try:
        for _expires, entries in _C._browse_catalog_cache.values():
            candidates.extend(entries or [])
    except Exception:
        pass
    with contextlib.suppress(Exception):
        candidates.extend(_C._known_entry_cache.values())

    seen = set()
    for candidate in candidates:
        entry_id = candidate.get("id") if isinstance(candidate, dict) else None
        if not entry_id or entry_id in seen:
            continue
        seen.add(entry_id)
        if not _entry_matches_local_name(candidate, local_name):
            continue
        entry = dict(candidate)
        entry["local_name"] = local_name
        _save_local_model_metadata(
            entry,
            os.path.join(_pkg.RVC_MODELS_DIR, f"{local_name}.pth"),
        )
        return entry
    return None


def is_local_model_trusted(name: str) -> bool:
    from engine.rvc_pipeline import is_rvc_checkpoint_trusted

    model_path = os.path.join(_pkg.RVC_MODELS_DIR, f"{os.path.basename(str(name or ''))}.pth")
    return is_rvc_checkpoint_trusted(model_path)


def trust_local_model(name: str, source: str = "user-confirmed") -> str:
    from engine.rvc_pipeline import mark_rvc_checkpoint_trusted

    safe_name = os.path.basename(str(name or "").strip())
    if not safe_name or safe_name != str(name or "").strip():
        raise ValueError("некорректное имя RVC-модели")
    return mark_rvc_checkpoint_trusted(
        os.path.join(_pkg.RVC_MODELS_DIR, f"{safe_name}.pth"), source=source
    )
