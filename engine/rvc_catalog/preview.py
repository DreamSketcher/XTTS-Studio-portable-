"""
engine/rvc_catalog/preview.py — короткие демо-примеры и параметрический preview (TASK-008).

Демо-аудио из Sample deck voice-models.com (ленивый парсинг <audio>), кэш демо
в .preview_cache, и параметрический preview (RVC-проход на референсе) в
.parameter_preview_cache/<model>/. Перенесено дословно из монолитного модуля.
"""

import hashlib
import os
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from engine import rvc_catalog as _pkg
from engine.rvc_catalog import _constants as _C
import contextlib


class _PreviewAudioParser(HTMLParser):
    """Достаёт основной generated sample из страницы voice-models.com."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if str(tag).lower() != "audio":
            return
        data = {str(k).lower(): v for k, v in attrs if k}
        src = (data.get("src") or "").strip()
        if not src:
            return
        if src.startswith(("https://", "http://")):
            priority = 0 if data.get("id") == "vm-fit-audio" else 1
            self.urls.append((priority, src))


def _entry_page_url(entry: dict) -> str:

    page_url = str(entry.get("page_url") or "").strip()
    if re.match(r"^https?://(?:www\.)?voice-models\.com/model/", page_url, re.I):
        return page_url

    source_url = str(entry.get("url") or "").strip()
    if re.match(r"^https?://(?:www\.)?voice-models\.com/model/", source_url, re.I):
        return source_url

    description = str(entry.get("description") or "")
    match = re.search(
        r"https?://(?:www\.)?voice-models\.com/model/[A-Za-z0-9_-]+",
        description,
        re.I,
    )
    if match:
        return match.group(0)

    entry_id = str(entry.get("id") or "")
    if entry_id.startswith("vm_") and len(entry_id) > 3:
        return f"https://voice-models.com/model/{entry_id[3:]}"
    return ""


def can_preview(entry: dict) -> bool:
    """True, если запись содержит sample, его кэш или страницу-источник."""
    cached_path = str(entry.get("preview_cache_path") or "")
    return bool(
        (cached_path and os.path.isfile(cached_path))
        or entry.get("preview_url")
        or _entry_page_url(entry)
    )


def _normalize_preview_url(url: str) -> str:
    import html as htmlmod

    value = htmlmod.unescape(str(url or "").strip()).replace(r"\/", "/")
    if not value.startswith(("https://", "http://")):
        return ""
    parsed = urllib.parse.urlparse(value)
    if not parsed.netloc:
        return ""
    if not re.search(r"\.(?:mp3|wav|ogg|m4a)(?:$|[?#])", value, re.I):
        return ""
    return value


def get_preview_url(entry: dict, force_refresh: bool = False) -> str:
    """Возвращает URL короткого примера голоса без скачивания RVC-модели."""
    direct = _normalize_preview_url(entry.get("preview_url") or "")
    if direct:
        return direct

    page_url = _entry_page_url(entry)
    if not page_url:
        return ""

    cache_key = str(entry.get("id") or page_url)
    now = time.monotonic()
    if not force_refresh:
        cached = _C._preview_url_cache.get(cache_key)
        if cached and now < cached[0]:
            return cached[1]

    preview_url = ""
    try:
        req = urllib.request.Request(
            page_url,
            headers={
                "User-Agent": _C.VOICE_MODELS_UA,
                "Accept": "text/html,application/xhtml+xml",
                "Referer": "https://voice-models.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=_C.VM_SEARCH_TIMEOUT) as response:
            raw = response.read(2 * 1024 * 1024).decode("utf-8", "replace")

        parser = _PreviewAudioParser()
        parser.feed(raw)
        for _priority, candidate in sorted(parser.urls, key=lambda item: item[0]):
            preview_url = _normalize_preview_url(candidate)
            if preview_url:
                break

        if not preview_url:
            candidates = re.findall(
                r"https?(?::|\u003A)(?:\/|\u002F){2}[^\"'<> ]+?"
                r"\.(?:mp3|wav|ogg|m4a)(?:[^\"'<> ]*)",
                raw,
                re.I,
            )
            for candidate in candidates:
                candidate = (
                    candidate.replace("\u003A", ":").replace("\u002F", "/").replace(r"\/", "/")
                )
                preview_url = _normalize_preview_url(candidate)
                if preview_url:
                    break
    except Exception:
        preview_url = ""

    ttl = _C._PREVIEW_SUCCESS_TTL if preview_url else _C._PREVIEW_FAILURE_TTL
    _C._preview_url_cache[cache_key] = (now + ttl, preview_url)
    if preview_url:
        entry["preview_url"] = preview_url
        try:
            if _pkg.is_downloaded(entry):
                _pkg._save_local_model_metadata(entry)
        except Exception:
            pass
    return preview_url


def get_preview_audio_path(entry: dict, force_refresh: bool = False) -> str:
    """Скачивает только короткий sample в кэш и возвращает локальный аудиофайл."""
    remembered_path = str(entry.get("preview_cache_path") or "")
    if remembered_path and os.path.isfile(remembered_path) and not force_refresh:
        return remembered_path

    url = get_preview_url(entry, force_refresh=force_refresh)
    if not url:
        return ""

    parsed = urllib.parse.urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()
    if ext not in (".mp3", ".wav", ".ogg", ".m4a"):
        ext = ".mp3"
    digest = hashlib.sha256(url.encode("utf-8", "replace")).hexdigest()[:20]
    readable = re.sub(
        r"[^\w\-]+", "_", str(entry.get("name") or entry.get("id") or "preview")[:42]
    ).strip("_")
    readable = readable or "preview"
    cache_path = os.path.join(_C.RVC_PREVIEW_CACHE_DIR, f"{readable}_{digest}{ext}")

    try:
        if os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0:
            if not _C._download_is_html_error(cache_path):
                entry["preview_cache_path"] = cache_path
                try:
                    if _pkg.is_downloaded(entry):
                        _pkg._save_local_model_metadata(entry)
                except Exception:
                    pass
                return cache_path
            os.remove(cache_path)
    except Exception:
        pass

    part_path = cache_path + ".part"
    try:
        os.makedirs(_C.RVC_PREVIEW_CACHE_DIR, exist_ok=True)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": _C.VOICE_MODELS_UA,
                "Accept": "audio/mpeg,audio/*;q=0.9,*/*;q=0.1",
                "Referer": _entry_page_url(entry) or "https://voice-models.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            total_header = response.headers.get("Content-Length")
            too_big = (
                total_header
                and str(total_header).isdigit()
                and int(total_header) > _C.PREVIEW_MAX_BYTES
            )
            if too_big:
                raise ValueError("аудиопример слишком большой")
            received = 0
            with open(part_path, "wb") as output:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > _C.PREVIEW_MAX_BYTES:
                        raise ValueError("аудиопример превысил допустимый размер")
                    output.write(chunk)

        if not os.path.isfile(part_path) or os.path.getsize(part_path) <= 0:
            raise ValueError("получен пустой аудиопример")
        if _C._download_is_html_error(part_path):
            raise ValueError("вместо аудио сервер вернул HTML-страницу")
        os.replace(part_path, cache_path)
        entry["preview_cache_path"] = cache_path
        try:
            if _pkg.is_downloaded(entry):
                _pkg._save_local_model_metadata(entry)
        except Exception:
            pass
        return cache_path
    except Exception:
        _C._cleanup_tmp(part_path)
        return ""


def open_preview(entry: dict) -> bool:
    """Fallback: открывает потоковый sample в браузере."""
    url = get_preview_url(entry)
    if not url:
        return False
    try:
        import webbrowser

        return bool(webbrowser.open(url))
    except Exception:
        return False


# ----------------------------------------------------------------
#  Параметрический preview (RVC-проход на референсе пользователя)
# ----------------------------------------------------------------


def _parameter_preview_model_dir(model_name: str) -> str:
    safe_model = re.sub(
        r"[^\w\-]+",
        "_",
        os.path.basename(str(model_name or "model")),
        flags=re.U,
    ).strip("_")
    safe_model = (safe_model or "model")[:64]
    model_digest = hashlib.sha256(
        str(model_name or "model").encode("utf-8", "replace")
    ).hexdigest()[:10]
    return os.path.join(
        _C.RVC_PARAMETER_PREVIEW_CACHE_DIR,
        f"{safe_model}_{model_digest}",
    )


def get_parameter_preview_cache_path(model_name: str, fingerprint: str) -> str:
    """Путь к локальному preview текущих Index/Pitch/f0 для модели."""
    digest = hashlib.sha256(str(fingerprint).encode("utf-8", "replace")).hexdigest()[:24]
    model_cache_dir = _parameter_preview_model_dir(model_name)
    os.makedirs(model_cache_dir, exist_ok=True)
    return os.path.join(model_cache_dir, f"{digest}.wav")


def prune_parameter_preview_cache(model_name: str, keep: int = 6):
    """Оставляет несколько последних вариантов параметрического preview модели."""
    try:
        model_cache_dir = _parameter_preview_model_dir(model_name)
        if not os.path.isdir(model_cache_dir):
            return
        files = [
            os.path.join(model_cache_dir, filename)
            for filename in os.listdir(model_cache_dir)
            if filename.lower().endswith(".wav")
        ]
        files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        for old_path in files[max(1, int(keep)) :]:
            with contextlib.suppress(Exception):
                os.remove(old_path)
    except Exception:
        pass


def _delete_parameter_preview_cache(model_name: str):
    import shutil

    try:
        model_cache_dir = _parameter_preview_model_dir(model_name)
        if os.path.isdir(model_cache_dir):
            shutil.rmtree(model_cache_dir, ignore_errors=True)
    except Exception:
        pass
