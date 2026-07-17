"""
engine/rvc_catalog/sources.py — источники каталога RVC-моделей (TASK-008).

seed/кэш + GitHub raw (редко) + живой парсинг voice-models.com. Перенесено
дословно из монолитного engine/rvc_catalog.py; подменяемые имена читаются через
объект пакета, чтобы тестовый monkeypatch оставался рабочим.
"""

import html as htmlmod
import json
import os
import re
import time
import urllib.parse
import urllib.request

from engine import rvc_catalog as _pkg
from engine.rvc_catalog import _constants as _C
import contextlib


# ----------------------------------------------------------------
#  Каталог: кэш/seed сразу, GitHub — редко и без 4 ретраев
# ----------------------------------------------------------------


def _validate_catalog(data) -> list:
    """Отбрасывает записи без обязательных полей вместо падения на всём каталоге."""
    if not isinstance(data, list):
        return []
    valid = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        if not entry.get("id") or not entry.get("name") or not entry.get("url"):
            continue
        valid.append(entry)
    return valid


def _load_local_catalog() -> list:
    """Кэш на диске → seed. Без сети. Кэшируется в памяти процесса."""
    if _pkg._local_catalog_cache is not None:
        return _pkg._local_catalog_cache

    cached = _C._load_json(_pkg.CATALOG_CACHE_PATH)
    valid_cached = _validate_catalog(cached) if cached is not None else []
    if valid_cached:
        _pkg._local_catalog_cache = valid_cached
        return valid_cached

    seed = _C._load_json(_pkg.SEED_CATALOG_PATH)
    valid_seed = _validate_catalog(seed) if seed is not None else []
    _pkg._local_catalog_cache = valid_seed
    return valid_seed


def _fetch_remote_catalog_once() -> list:
    """Одна попытка GitHub raw (без 4 ретраев updater'а)."""
    req = urllib.request.Request(
        _C.CATALOG_RAW_URL,
        headers={"User-Agent": _C.VOICE_MODELS_UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read().decode("utf-8"))
    return _validate_catalog(data)


def _save_cache(entries: list):
    try:
        os.makedirs(_pkg.RVC_MODELS_DIR, exist_ok=True)
        with open(_pkg.CATALOG_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_catalog(force_refresh: bool = False) -> list:
    """
    Возвращает список моделей каталога. Локальный кэш/seed — сразу; GitHub raw —
    только при force_refresh или пустом локальном каталоге (1 попытка, cooldown 6ч).
    """
    local = _load_local_catalog()
    now = time.monotonic()

    should_try_github = force_refresh or not local
    if should_try_github and (now < _pkg._github_catalog_fail_until) and not force_refresh:
        should_try_github = False

    if should_try_github:
        try:
            entries = _fetch_remote_catalog_once()
            if entries:
                _save_cache(entries)
                _pkg._local_catalog_cache = entries
                _pkg._github_catalog_fail_until = 0.0
                _pkg._github_catalog_fail_logged = False
                return entries
            _pkg._github_catalog_fail_logged = True
            _pkg._github_catalog_fail_until = now + _C._GITHUB_CATALOG_COOLDOWN_SEC
        except Exception:
            _pkg._github_catalog_fail_until = now + _C._GITHUB_CATALOG_COOLDOWN_SEC
            _pkg._github_catalog_fail_logged = True

    return local


# ----------------------------------------------------------------
#  URL/имя-хелперы
# ----------------------------------------------------------------


def _clean_download_url(url: str) -> str:
    if not url:
        return ""
    u = htmlmod.unescape(url.strip())
    u = u.replace("%3Fdownload%3Dtrue", "")
    while u.endswith("?download=true"):
        u = u[: -len("?download=true")]
    if "/blob/" in u and "huggingface.co" in u:
        u = u.replace("/blob/", "/resolve/")
    u = u.replace("https://voice-model.com/", "https://voice-models.com/")
    u = u.replace("http://voice-model.com/", "https://voice-models.com/")
    return u


def _safe_filename_stem(name: str, url: str, mid: str) -> str:
    path = urllib.parse.urlparse(url or "").path
    base = urllib.parse.unquote(os.path.basename(path))
    stem = re.sub(r"\.(zip|pth|index)$", "", base, flags=re.I)
    stem = re.sub(r"[^\w\-]+", "_", stem, flags=re.U).strip("_")
    if not stem or stem.lower() in ("resolve", "main", "blob", "view"):
        stem = re.sub(r"[^\w\-]+", "_", (name or "")[:48], flags=re.U).strip("_")
    if not stem:
        stem = f"model_{mid or int(time.time())}"
    return stem[:80]


def _guess_filename(name: str, url: str, mid: str) -> str:
    stem = _safe_filename_stem(name, url, mid)
    path = urllib.parse.urlparse(url or "").path.lower()
    if path.endswith(".pth"):
        return stem + ".pth"
    if (
        path.endswith(".zip")
        or "huggingface.co" in (url or "")
        or "drive.google.com" in (url or "")
    ):
        return stem + ".zip"
    return stem + ".zip"


def _is_direct_downloadable(url: str) -> bool:
    """True, если URL можно качать urllib'ом (HF / прямой файл / gdrive file)."""
    if not url:
        return False
    u = url.lower()
    if "huggingface.co" in u and "/resolve/" in u:
        return True
    if re.search(r"\.(zip|pth)(\?|$)", u):
        return True
    if "drive.google.com" in u and ("/file/d/" in u or "id=" in u or "uc?export=download" in u):
        return True
    if "drive.google.com" in u and "/folders/" in u:
        return False
    return False


# ----------------------------------------------------------------
#  voice-models.com — парсинг таблиц
# ----------------------------------------------------------------


def _vm_request(url: str, data: bytes = None, timeout: int = None):
    """HTTP GET/POST к voice-models.com. Без ретраев — UI и так debounce'ит."""
    if timeout is None:
        timeout = _C.VM_SEARCH_TIMEOUT
    headers = {
        "User-Agent": _C.VOICE_MODELS_UA,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://voice-models.com/",
    }
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def _parse_vm_table(table_html: str) -> list:
    """Парсит HTML-таблицу из fetch_data.php → список сырых dict."""
    if not table_html:
        return []
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", table_html, re.S | re.I):
        m = re.search(r"href='(/model/[^']+)'[^>]*class='fs-5'>(.*?)</a>", tr, re.S)
        if not m:
            continue
        path, title_html = m.group(1), m.group(2)
        mid = path.rstrip("/").rsplit("/", 1)[-1]
        creator = None
        cm = re.search(r"title='Uploaded by ([^']+)'", tr)
        if cm:
            creator = cm.group(1)
        size = None
        sm = re.search(r"badge bg-secondary[^>]*>([^<]+)</span>", tr)
        if sm:
            size = sm.group(1).strip()
        dl = None
        dm = re.search(r"data-clipboard-text='([^']+)'", tr)
        if dm:
            dl = htmlmod.unescape(dm.group(1))
        if not dl:
            rm = re.search(r"easyaivoice\.com/run\?url=([^'\"&]+)", tr)
            if rm:
                dl = urllib.parse.unquote(rm.group(1))
        title = re.sub(r"<[^>]+>", "", title_html or "")
        title = htmlmod.unescape(title).strip()
        rows.append(
            {
                "mid": mid,
                "path": path,
                "title": title,
                "author": creator or "Community",
                "size": size,
                "download": _clean_download_url(dl or ""),
            }
        )
    return rows


def _row_to_entry(row: dict):
    """Сырой ряд voice-models → entry формата каталога (или None)."""
    mid = row.get("mid") or ""
    title = (row.get("title") or "").strip()
    url = _clean_download_url(row.get("download") or "")
    if not mid or not title:
        return None
    page_url = f"https://voice-models.com/model/{mid}"
    if not url:
        url = page_url
    filename = _guess_filename(title, url, mid)
    entry = {
        "id": f"vm_{mid}",
        "name": title[:160],
        "url": url,
        "filename": filename,
        "author": row.get("author") or "Community",
        "license": "Community (voice-models.com)",
        "description": page_url + (f" · {row['size']}" if row.get("size") else ""),
        "source": "voice-models",
        "page_url": page_url,
        "downloadable": _is_direct_downloadable(url),
    }
    if row.get("size"):
        entry["size"] = row["size"]
    return entry


def _remember_catalog_entries(entries):
    for entry in entries or []:
        try:
            entry_id = entry.get("id")
            if entry_id:
                _C._known_entry_cache[entry_id] = dict(entry)
        except Exception:
            pass


def browse_voice_models(
    mode: str = "new", max_results: int = 50, force_refresh: bool = False
) -> list:
    """Загружает публичные каталоги сайта: ``new`` или ``top``. Кэш 15 минут."""
    catalog_mode = str(mode or "new").strip().lower()
    if catalog_mode not in ("new", "top"):
        return []

    now = time.monotonic()
    cached = _C._browse_catalog_cache.get(catalog_mode)
    if cached and not force_refresh and now < cached[0]:
        return [dict(entry) for entry in cached[1][:max_results]]

    entries = []
    try:
        if catalog_mode == "new":
            data = urllib.parse.urlencode({"page": "1", "search": ""}).encode()
            with _vm_request(
                _C.VOICE_MODELS_FETCH_URL, data=data, timeout=_C.VM_SEARCH_TIMEOUT
            ) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
            html_table = payload.get("table", "") if isinstance(payload, dict) else ""
        else:
            request = urllib.request.Request(
                _C.VOICE_MODELS_TOP_URL,
                headers={
                    "User-Agent": _C.VOICE_MODELS_UA,
                    "Accept": "text/html,application/xhtml+xml",
                    "Referer": _C.VOICE_MODELS_HOME_URL,
                },
            )
            with urllib.request.urlopen(request, timeout=_C.VM_SEARCH_TIMEOUT) as response:
                html_table = response.read(2 * 1024 * 1024).decode("utf-8", "replace")

        seen = set()
        for row in _parse_vm_table(html_table):
            entry = _row_to_entry(row)
            if not entry or entry["id"] in seen:
                continue
            seen.add(entry["id"])
            entry["catalog"] = catalog_mode
            entries.append(entry)
            if len(entries) >= max_results:
                break
    except Exception:
        entries = []

    if entries:
        _C._browse_catalog_cache[catalog_mode] = (
            now + _C._BROWSE_CATALOG_TTL,
            [dict(entry) for entry in entries],
        )
        _remember_catalog_entries(entries)
        return entries
    if cached:
        return [dict(entry) for entry in cached[1][:max_results]]
    return []


def search_voice_models(query: str, max_results: int = _C.SEARCH_MAX_RESULTS) -> list:
    """Живой поиск по voice-models.com. Пустой query → []. Ошибки сети глотаются."""
    q = (query or "").strip()
    if len(q) < 2:
        return []

    seen_ids = set()
    results = []
    errors = []

    try:
        for page in range(1, _C.SEARCH_PAGES + 1):
            if len(results) >= max_results:
                break
            data = urllib.parse.urlencode({"page": str(page), "search": q}).encode()
            with _vm_request(
                _C.VOICE_MODELS_FETCH_URL, data=data, timeout=_C.VM_SEARCH_TIMEOUT
            ) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace"))
            table = payload.get("table") if isinstance(payload, dict) else ""
            for row in _parse_vm_table(table or ""):
                entry = _row_to_entry(row)
                if not entry or entry["id"] in seen_ids:
                    continue
                seen_ids.add(entry["id"])
                results.append(entry)
                if len(results) >= max_results:
                    break
    except Exception as e:
        errors.append(f"fetch_data: {e}")

    if len(results) < 5:
        try:
            url = _C.VOICE_MODELS_SEARCH_URL + "?search=" + urllib.parse.quote(q)
            with _vm_request(url, data=None, timeout=min(6, _C.VM_SEARCH_TIMEOUT)) as resp:
                raw = resp.read().decode("utf-8", "replace")
            items = json.loads(raw) if raw.strip().startswith("[") else []
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                title = (item.get("title") or "").strip()
                link = _clean_download_url(item.get("url") or "")
                m = re.search(r"/model/([^/?#]+)", link)
                mid = m.group(1) if m else ""
                if not mid or not title:
                    continue
                eid = f"vm_{mid}"
                if eid in seen_ids:
                    continue
                entry = _row_to_entry(
                    {
                        "mid": mid,
                        "title": title,
                        "author": "Community",
                        "size": None,
                        "download": link if _is_direct_downloadable(link) else "",
                    }
                )
                if not entry:
                    continue
                if not entry.get("downloadable"):
                    entry["url"] = entry.get("page_url") or link
                    entry["downloadable"] = False
                seen_ids.add(eid)
                results.append(entry)
                if len(results) >= max_results:
                    break
        except Exception as e:
            errors.append(f"autocomplete: {e}")

    if errors and not results:
        _pkg._vm_search_fail_log_until = time.monotonic() + 60

    results.sort(key=lambda e: (0 if e.get("downloadable") else 1, e.get("name", "").lower()))
    return results[:max_results]


def search_catalog(query: str, max_results: int = _C.SEARCH_MAX_RESULTS, live: bool = True) -> list:
    """Поиск по seed/кэшу + (опционально) live voice-models.com. Локальные — первыми."""
    q = (query or "").strip().lower()
    if len(q) < 2:
        return []

    local_hits = []
    try:
        for entry in _load_local_catalog() or get_catalog(force_refresh=False):
            blob = " ".join(
                [
                    str(entry.get("name") or ""),
                    str(entry.get("author") or ""),
                    str(entry.get("description") or ""),
                    str(entry.get("id") or ""),
                ]
            ).lower()
            if q in blob:
                e = dict(entry)
                e.setdefault("downloadable", _is_direct_downloadable(e.get("url") or ""))
                e.setdefault("source", e.get("source") or "seed")
                local_hits.append(e)
    except Exception:
        pass

    live_hits = []
    if live:
        with contextlib.suppress(Exception):
            live_hits = search_voice_models(query, max_results=max_results)

    seen = set()
    out = []
    for e in local_hits + live_hits:
        eid = e.get("id")
        if not eid or eid in seen:
            continue
        seen.add(eid)
        out.append(e)
        if len(out) >= max_results:
            break
    _remember_catalog_entries(out)
    return out
