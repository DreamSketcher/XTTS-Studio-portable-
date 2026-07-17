"""
engine/rvc_catalog/downloader.py — скачивание RVC-моделей (TASK-008).

Прямые URL (.pth/.zip), HuggingFace /resolve/, Google Drive file (best-effort),
zip → извлечение .pth (+.index). Перенесено дословно из монолитного
engine/rvc_catalog.py. `_download_bytes_to_file` и подменяемые пути читаются через
объект пакета (`import engine.rvc_catalog as _pkg`), чтобы тестовый monkeypatch
оставался рабочим.
"""

import os
import re
import shutil
import urllib.parse
import urllib.request
import zipfile

from engine import rvc_catalog as _pkg
from engine.rvc_catalog import _constants as _C

from engine.updater import _urlopen_with_retry, _is_cancelled


def local_model_path(entry: dict) -> str:
    """Путь, по которому модель должна лежать локально, если скачана."""
    filename = entry.get("filename") or os.path.basename(urllib.parse.urlparse(entry["url"]).path)
    filename = urllib.parse.unquote(filename)
    stem, ext = os.path.splitext(filename)
    if ext.lower() == ".zip":
        filename = stem + ".pth"
    elif not ext:
        filename = filename + ".pth"
    filename = os.path.basename(filename)
    return os.path.join(_pkg.RVC_MODELS_DIR, filename)


def is_downloaded(entry: dict) -> bool:
    return os.path.isfile(local_model_path(entry))


# ----------------------------------------------------------------
#  Google Drive
# ----------------------------------------------------------------


def _gdrive_file_id(url: str):
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def _resolve_download_url(url: str) -> str:
    """Нормализует URL перед скачиванием.

    gdrive file → uc?export=download&id=...; HF blob → resolve.
    """
    u = _pkg._clean_download_url(url)
    if "drive.google.com" in u:
        if "/folders/" in u:
            raise ValueError(
                "Google Drive folder URL — прямое скачивание не поддерживается. "
                "Откройте ссылку в браузере и положите .pth в models/rvc/"
            )
        fid = _gdrive_file_id(u)
        if fid:
            return f"https://drive.google.com/uc?export=download&id={fid}"
    return u


def _download_gdrive(
    uc_url: str, tmp_path: str, progress_callback=None, cancelled_flag=None
) -> None:
    """Best-effort скачивание Google Drive file (с confirm-cookie для больших файлов)."""
    req = urllib.request.Request(uc_url, headers={"User-Agent": _C.VOICE_MODELS_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        ctype = (resp.headers.get("Content-Type") or "").lower()
        data = resp.read()
        if (
            "text/html" not in ctype
            and not data[:200].lstrip().startswith(b"<!DOCTYPE")
            and not data[:200].lstrip().lower().startswith(b"<html")
        ):
            with open(tmp_path, "wb") as f:
                f.write(data)
            if progress_callback:
                progress_callback(len(data), len(data))
            return
        html = data.decode("utf-8", "replace")
        m = re.search(r"confirm=([0-9A-Za-z_]+)", html)
        token = m.group(1) if m else None
        m2 = re.search(r'name="confirm"\s+value="([^"]+)"', html)
        if m2:
            token = m2.group(1)
        fid = None
        m3 = re.search(r'name="id"\s+value="([^"]+)"', html)
        if m3:
            fid = m3.group(1)
        if not fid:
            fid = _gdrive_file_id(uc_url)
        if not token or not fid:
            token = token or "t"
        if not fid:
            raise RuntimeError("Google Drive: не удалось извлечь file id / confirm token")

    final = f"https://drive.google.com/uc?export=download&confirm={token}&id={fid}"
    with _urlopen_with_retry(final, timeout=30, max_retries=_C.MAX_RETRIES) as resp:
        ctype = (resp.headers.get("Content-Type") or "").lower()
        total = resp.headers.get("Content-Length")
        total = int(total) if total and str(total).isdigit() else None
        downloaded = 0
        with open(tmp_path, "wb") as f:
            while True:
                if _is_cancelled(cancelled_flag):
                    raise InterruptedError("Скачивание модели отменено пользователем")
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total)
        if downloaded < 1024:
            with open(tmp_path, "rb") as f:
                head = f.read(256).lstrip().lower()
            if head.startswith(b"<!doctype") or head.startswith(b"<html"):
                raise RuntimeError(
                    "Google Drive вернул HTML вместо файла "
                    "(нужен ручной download / публичный доступ)"
                )


def _download_bytes_to_file(
    url: str, tmp_path: str, progress_callback=None, cancelled_flag=None
) -> None:
    """Качает url во tmp_path с прогрессом. Бросает при ошибке/отмене.

    ВНИМАНИЕ: вызывается из download_model() ЧЕРЕЗ ОБЪЕКТ ПАКЕТА
    (_pkg._download_bytes_to_file), чтобы тесты могли monkeypatch'ить её.
    """
    resolved = _resolve_download_url(url)

    if "drive.google.com" in resolved:
        _download_gdrive(resolved, tmp_path, progress_callback, cancelled_flag)
        return

    with _urlopen_with_retry(resolved, timeout=30, max_retries=_C.MAX_RETRIES) as resp:
        total = resp.headers.get("Content-Length")
        total = int(total) if total and str(total).isdigit() else None
        downloaded = 0
        with open(tmp_path, "wb") as f:
            while True:
                if _is_cancelled(cancelled_flag):
                    raise InterruptedError("Скачивание модели отменено пользователем")
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total)


# ----------------------------------------------------------------
#  zip → .pth (+.index)
# ----------------------------------------------------------------


def _extract_rvc_from_zip(zip_path: str, dest_pth: str) -> bool:
    """Достаёт .pth (+ опционально .index) из zip в models/rvc/."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            infos = [info for info in zf.infolist() if not info.is_dir()]
            if len(infos) > _C.RVC_ARCHIVE_MAX_MEMBERS:
                return False
            names = [info.filename for info in infos]
            pths = [n for n in names if n.lower().endswith(".pth")]
            if not pths:
                return False

            def _sz(n):
                try:
                    return zf.getinfo(n).file_size
                except Exception:
                    return 0

            pths.sort(key=_sz, reverse=True)
            chosen_pth = pths[0]

            def _member_is_safe(name):
                info = zf.getinfo(name)
                if info.file_size < 0 or info.file_size > _C.RVC_ARCHIVE_MAX_EXTRACTED_BYTES:
                    return False
                compressed = max(1, info.compress_size)
                return (info.file_size / compressed) <= _C.RVC_ARCHIVE_MAX_COMPRESSION_RATIO

            if not _member_is_safe(chosen_pth):
                return False

            os.makedirs(os.path.dirname(dest_pth), exist_ok=True)
            temp_pth = dest_pth + ".extracting"
            with zf.open(chosen_pth) as src, open(temp_pth, "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.replace(temp_pth, dest_pth)

            dest_idx = os.path.splitext(dest_pth)[0] + ".index"
            pth_stem = os.path.splitext(os.path.basename(chosen_pth))[0].lower()
            idxs = [n for n in names if n.lower().endswith(".index")]
            chosen_idx = None
            for n in idxs:
                if os.path.splitext(os.path.basename(n))[0].lower() == pth_stem:
                    chosen_idx = n
                    break
            if not chosen_idx and idxs:
                idxs.sort(key=_sz, reverse=True)
                chosen_idx = idxs[0]
            if chosen_idx and _member_is_safe(chosen_idx):
                try:
                    temp_idx = dest_idx + ".extracting"
                    with zf.open(chosen_idx) as src, open(temp_idx, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    os.replace(temp_idx, dest_idx)
                except Exception:
                    _C._cleanup_tmp(dest_idx + ".extracting")
        return True
    except Exception:
        return False


# ----------------------------------------------------------------
#  download_model
# ----------------------------------------------------------------


def download_model(entry: dict, progress_callback=None, cancelled_flag=None) -> bool:
    """
    Скачивает модель из каталога в models/rvc/. Поддерживает прямые URL (.pth/.zip),
    HuggingFace /resolve/, Google Drive file (best-effort), zip → извлечение .pth.
    SHA256 в entry["sha256"] опционален. Возвращает True при успехе, False при ошибке/отмене.
    """
    os.makedirs(_pkg.RVC_MODELS_DIR, exist_ok=True)
    url = entry.get("url") or ""
    expected_sha256 = entry.get("sha256")
    dest_pth = local_model_path(entry)

    if entry.get("downloadable") is False or not _pkg._is_direct_downloadable(url):
        return False

    path_ext = os.path.splitext(urllib.parse.urlparse(_pkg._clean_download_url(url)).path)[
        1
    ].lower()
    if path_ext not in (".zip", ".pth"):
        path_ext = ".bin"
    tmp = dest_pth + ".part" + path_ext

    try:
        # Через _pkg, чтобы тесты могли подменить _download_bytes_to_file.
        _pkg._download_bytes_to_file(url, tmp, progress_callback, cancelled_flag)
        if _C._download_is_html_error(tmp):
            raise RuntimeError("сервер вернул HTML-страницу вместо файла модели")
    except InterruptedError:
        _C._cleanup_tmp(tmp)
        return False
    except Exception as e:
        print(f"[RVC] Ошибка скачивания {entry.get('name', entry.get('id'))}: {e}")
        _C._cleanup_tmp(tmp)
        return False

    if expected_sha256:
        actual = _C._sha256_of_file(tmp)
        if actual.lower() != expected_sha256.lower():
            print(
                f"[RVCCatalog] SHA256 не совпадает для {entry.get('name')}: "
                f"ожидалось {expected_sha256}, получено {actual}"
            )
            _C._cleanup_tmp(tmp)
            return False

    is_zip = False
    try:
        with open(tmp, "rb") as f:
            magic = f.read(4)
        if magic[:2] == b"PK" or path_ext == ".zip":
            is_zip = True
        elif path_ext == ".pth":
            is_zip = False
    except Exception:
        is_zip = path_ext == ".zip"

    try:
        if is_zip:
            ok = _pkg._extract_rvc_from_zip(tmp, dest_pth)
            _C._cleanup_tmp(tmp)
            if not ok or not os.path.isfile(dest_pth):
                return False
            _pkg._save_local_model_metadata(entry, dest_pth)
            return True
        else:
            if os.path.exists(dest_pth):
                os.remove(dest_pth)
            shutil.move(tmp, dest_pth)
            _pkg._save_local_model_metadata(entry, dest_pth)
            return True
    except Exception as e:
        print(f"[RVCCatalog] Ошибка финализации {entry.get('name')}: {e}")
        _C._cleanup_tmp(tmp)
        return False
