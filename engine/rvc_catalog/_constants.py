"""
engine/rvc_catalog/_constants.py — пути, константы и общие хелперы каталога RVC.

ВЫНЕСЕНО из монолитного engine/rvc_catalog.py (TASK-008).

ВАЖНО для тестов: скалярные кэши и подменяемые пути (_local_catalog_cache,
_github_catalog_fail_*, _vm_search_fail_log_until) хранятся здесь, но функции
подмодулей обращаются к НИМ и к подменяемым константам (BASE_DIR, RVC_MODELS_DIR,
SEED_CATALOG_PATH, CATALOG_CACHE_PATH) ЧЕРЕЗ ОБЪЕКТ ПАКЕТА
(`import engine.rvc_catalog as _pkg; _pkg.RVC_MODELS_DIR`). Только так
monkeypatch.setattr(rvc_catalog, "RVC_MODELS_DIR", ...) в тестах остаётся рабочим.
Dict-кэши (in-place мутация) и непатчимые константы можно импортировать напрямую.
"""

import json
import os

# ----------------------------------------------------------------
#  Пути и константы
# ----------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Каталог, который ставится вместе с приложением (версионируется в git).
SEED_CATALOG_PATH = os.path.join(BASE_DIR, "json", "rvc_catalog_seed.json")

# Директория для скачанных моделей и кэша каталога — данные пользователя.
RVC_MODELS_DIR = os.path.join(BASE_DIR, "models", "rvc")
RVC_PREVIEW_CACHE_DIR = os.path.join(RVC_MODELS_DIR, ".preview_cache")
RVC_PARAMETER_PREVIEW_CACHE_DIR = os.path.join(RVC_MODELS_DIR, ".parameter_preview_cache")
RVC_METADATA_DIR = os.path.join(RVC_MODELS_DIR, ".metadata")
CATALOG_CACHE_PATH = os.path.join(RVC_MODELS_DIR, "catalog_cache.json")
PREVIEW_MAX_BYTES = 32 * 1024 * 1024
RVC_ARCHIVE_MAX_MEMBERS = 10_000
RVC_ARCHIVE_MAX_EXTRACTED_BYTES = 2 * 1024 * 1024 * 1024
RVC_ARCHIVE_MAX_COMPRESSION_RATIO = 200

# raw GitHub-каталог (REPO/BRANCH из updater'а).
try:
    from engine.updater import REPO, BRANCH

    CATALOG_RAW_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/rvc_catalog.json"
except Exception:  # pragma: no cover - updater всегда доступен в рантайме
    CATALOG_RAW_URL = ""

# voice-models.com — community-индекс RVC-моделей.
VOICE_MODELS_HOME_URL = "https://voice-models.com/"
VOICE_MODELS_TOP_URL = "https://voice-models.com/top"
VOICE_MODELS_FETCH_URL = "https://voice-models.com/fetch_data.php"
VOICE_MODELS_SEARCH_URL = "https://voice-models.com/search"
VOICE_MODELS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 XTTS-Studio-RVCCatalog/1.0"
)

MAX_RETRIES = 4
SEARCH_MAX_RESULTS = 30
SEARCH_PAGES = 1
VM_SEARCH_TIMEOUT = 8
VM_SEARCH_ATTEMPTS = 1

# cooldown логов live-поиска — не печатать timeout на каждую букву
_vm_search_fail_log_until = 0.0

# Не долбим GitHub 4×1.5–4.5с на каждый open dropdown / search.
_GITHUB_CATALOG_COOLDOWN_SEC = 6 * 60 * 60  # 6 часов после 404/ошибки
_github_catalog_fail_until = 0.0
_github_catalog_fail_logged = False
_local_catalog_cache = None  # in-memory: seed/кэш без повторного disk+network

# dict-кэши (мутируются in-place, не патчатся тестами напрямую).
_preview_url_cache = {}  # key -> (valid_until_monotonic, url-or-empty)
_browse_catalog_cache = {}  # mode -> (valid_until_monotonic, entries)
_known_entry_cache = {}  # id -> entry, включая результаты поиска текущей сессии

_PREVIEW_SUCCESS_TTL = 24 * 60 * 60
_PREVIEW_FAILURE_TTL = 5 * 60
_BROWSE_CATALOG_TTL = 15 * 60


# ----------------------------------------------------------------
#  Общие хелперы
# ----------------------------------------------------------------


def _load_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _sha256_of_file(path: str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _cleanup_tmp(tmp: str):
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass


def _path_is_inside(path: str, directory: str) -> bool:
    try:
        return os.path.commonpath(
            [os.path.abspath(path), os.path.abspath(directory)]
        ) == os.path.abspath(directory)
    except Exception:
        return False


def _download_is_html_error(path: str) -> bool:
    """True, если сервер вернул HTML/XML-страницу вместо архива или .pth."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096).lstrip().lower()
    except Exception:
        return False
    return (
        head.startswith((b"<", b"&lt;", b"<!doctype", b"<?xml"))
        or b"<html" in head
        or b"<body" in head
    )
