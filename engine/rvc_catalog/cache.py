"""
engine/rvc_catalog/cache.py — lifecycle кэшей RVC-моделей (TASK-008).

clear_rvc_cache() (orphan-preview, partial-файлы, остатки прерванных загрузок;
защищены preview установленных .pth), delete_local_model(), open_model_page().
Перенесено дословно из монолитного engine/rvc_catalog.py.
"""

import os
import re
import shutil

from engine import rvc_catalog as _pkg
from engine.rvc_catalog import _constants as _C
import contextlib


def _installed_preview_paths(exclude_local_name: str = "") -> set:
    """Preview-файлы, принадлежащие установленным .pth и защищённые от очистки."""
    protected = set()
    try:
        metadata_files = os.listdir(_C.RVC_METADATA_DIR)
    except Exception:
        metadata_files = []
    excluded = os.path.normcase(str(exclude_local_name or ""))
    for filename in metadata_files:
        if not filename.lower().endswith(".json"):
            continue
        metadata = _C._load_json(os.path.join(_C.RVC_METADATA_DIR, filename))
        if not isinstance(metadata, dict):
            continue
        local_name = str(metadata.get("local_name") or os.path.splitext(filename)[0])
        if excluded and os.path.normcase(local_name) == excluded:
            continue
        model_path = os.path.join(_pkg.RVC_MODELS_DIR, f"{local_name}.pth")
        if not os.path.isfile(model_path):
            continue
        preview_path = str(metadata.get("preview_cache_path") or "")
        if preview_path and os.path.isfile(preview_path):
            protected.add(os.path.normcase(os.path.abspath(preview_path)))
    return protected


def clear_rvc_cache() -> dict:
    """Удаляет orphan preview и недокачанные модели, не трогая установленные."""
    protected = _installed_preview_paths()
    removed_files = 0
    removed_bytes = 0
    removed_previews = 0
    removed_partials = 0

    def remove_file(path, kind):
        nonlocal removed_files, removed_bytes, removed_previews, removed_partials
        try:
            size = os.path.getsize(path) if os.path.isfile(path) else 0
            os.remove(path)
            removed_files += 1
            removed_bytes += max(0, size)
            if kind == "preview":
                removed_previews += 1
            elif kind == "partial":
                removed_partials += 1
        except Exception:
            pass

    try:
        preview_files = os.listdir(_C.RVC_PREVIEW_CACHE_DIR)
    except Exception:
        preview_files = []
    for filename in preview_files:
        path = os.path.join(_C.RVC_PREVIEW_CACHE_DIR, filename)
        if not os.path.isfile(path):
            continue
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in protected:
            continue
        remove_file(path, "preview")

    try:
        model_files = os.listdir(_pkg.RVC_MODELS_DIR)
    except Exception:
        model_files = []
    for filename in model_files:
        path = os.path.join(_pkg.RVC_MODELS_DIR, filename)
        if not os.path.isfile(path):
            continue
        lower = filename.lower()
        is_partial = bool(
            re.search(r"\.part(?:\.|$)", lower)
            or lower.endswith((".partial", ".tmp", ".download", ".crdownload"))
        )
        if is_partial:
            remove_file(path, "partial")

    # Параметрические previews принадлежат установленной модели. Для живых
    # моделей удаляем только незавершённые .part; orphan-каталоги очищаем целиком.
    installed_parameter_dirs = set()
    try:
        for filename in os.listdir(_pkg.RVC_MODELS_DIR):
            if filename.lower().endswith(".pth"):
                local_name = os.path.splitext(filename)[0]
                installed_parameter_dirs.add(
                    os.path.normcase(os.path.abspath(_pkg._parameter_preview_model_dir(local_name)))
                )
    except Exception:
        pass
    try:
        parameter_dirs = os.listdir(_C.RVC_PARAMETER_PREVIEW_CACHE_DIR)
    except Exception:
        parameter_dirs = []
    for dirname in parameter_dirs:
        directory = os.path.join(_C.RVC_PARAMETER_PREVIEW_CACHE_DIR, dirname)
        if not os.path.isdir(directory):
            continue
        normalized_dir = os.path.normcase(os.path.abspath(directory))
        if normalized_dir not in installed_parameter_dirs:
            for root_dir, _subdirs, filenames in os.walk(directory):
                for filename in filenames:
                    remove_file(os.path.join(root_dir, filename), "preview")
            shutil.rmtree(directory, ignore_errors=True)
            continue
        for filename in os.listdir(directory):
            lower = filename.lower()
            if re.search(r"\.part(?:\.|$)", lower) or lower.endswith(".tmp"):
                remove_file(os.path.join(directory, filename), "partial")

    # Атомарная запись metadata может оставить .tmp после аварийного закрытия.
    try:
        metadata_files = os.listdir(_C.RVC_METADATA_DIR)
    except Exception:
        metadata_files = []
    for filename in metadata_files:
        if filename.lower().endswith(".tmp"):
            remove_file(os.path.join(_C.RVC_METADATA_DIR, filename), "partial")

    return {
        "removed_files": removed_files,
        "removed_bytes": removed_bytes,
        "removed_previews": removed_previews,
        "removed_partials": removed_partials,
        "protected_previews": len(protected),
    }


def delete_local_model(name: str) -> bool:
    """
    Удаляет локально скачанную модель по имени (без расширения — так же,
    как её отдаёт get_rvc_models() в presets.py: f[:-4]). Заодно удаляет .index
    с тем же именем. Возвращает False, только если НИ ОДИН файл не удалён.
    """
    pth = os.path.join(_pkg.RVC_MODELS_DIR, f"{name}.pth")
    idx = os.path.join(_pkg.RVC_MODELS_DIR, f"{name}.index")
    metadata_path = _pkg._metadata_path_for_local_name(name)
    metadata = _C._load_json(metadata_path)
    preview_path = ""
    if isinstance(metadata, dict):
        preview_path = str(metadata.get("preview_cache_path") or "")

    removed_any = False
    trust_path = pth + ".trust.json"
    for p in (pth, idx, trust_path):
        try:
            if os.path.isfile(p):
                os.remove(p)
                removed_any = True
        except Exception:
            pass

    # Metadata и закреплённый sample удаляем только когда самой .pth уже нет.
    if not os.path.isfile(pth):
        _pkg._delete_parameter_preview_cache(name)
        try:
            if os.path.isfile(metadata_path):
                os.remove(metadata_path)
        except Exception:
            pass
        if (
            preview_path
            and _C._path_is_inside(preview_path, _C.RVC_PREVIEW_CACHE_DIR)
            and os.path.isfile(preview_path)
        ):
            protected_elsewhere = _installed_preview_paths(exclude_local_name=name)
            normalized_preview = os.path.normcase(os.path.abspath(preview_path))
            if normalized_preview not in protected_elsewhere:
                with contextlib.suppress(Exception):
                    os.remove(preview_path)
    return removed_any


def open_model_page(entry: dict) -> bool:
    """Открыть page_url модели в системном браузере (для folder / non-downloadable)."""
    url = entry.get("page_url") or entry.get("url") or ""
    if not url:
        return False
    try:
        import webbrowser

        webbrowser.open(url)
        return True
    except Exception:
        return False
