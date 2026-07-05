"""
engine/local_llm_client.py — локальные GGUF-модели через llama-cpp-python
(инференс прямо в процессе приложения, без внешних серверов вроде Ollama).
"""

import os
import json
import shutil
import threading

# ── Paths ──────────────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS_PATH = os.path.join(_BASE_DIR, "gpt_settings.json")
MODELS_DIR = os.path.join(_BASE_DIR, "models")

os.makedirs(MODELS_DIR, exist_ok=True)

# ── Каталог известных моделей (прямые ссылки на .gguf — заполним на Шаге Б) ────
LOCAL_MODEL_CATALOG = []


def _read_settings() -> dict:
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_settings(patch: dict):
    data = _read_settings()
    data.update(patch)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Установленные модели (persisted список, не статика) ────────────────────────

def list_installed_models() -> list:
    items = _read_settings().get("installed_local_models", [])
    return items if isinstance(items, list) else []


def _save_installed_models(items: list):
    _write_settings({"installed_local_models": items})


def get_active_model_id() -> str:
    return _read_settings().get("active_local_model_id", "")


def set_active_model_id(model_id: str):
    _write_settings({"active_local_model_id": model_id})


def get_active_model() -> dict:
    """Возвращает запись активной модели (dict) или None."""
    active_id = get_active_model_id()
    for m in list_installed_models():
        if m.get("id") == active_id:
            return m
    return None


def register_model(path: str, label: str = None) -> dict:
    """Регистрирует уже лежащий по path .gguf как установленную модель."""
    import uuid as _uuid
    filename = os.path.basename(path)
    entry = {
        "id": str(_uuid.uuid4()),
        "filename": filename,
        "path": path,
        "label": label or filename,
    }
    items = list_installed_models()
    items.append(entry)
    _save_installed_models(items)
    return entry


def remove_model(model_id: str):
    items = [m for m in list_installed_models() if m.get("id") != model_id]
    _save_installed_models(items)
    if get_active_model_id() == model_id:
        _write_settings({"active_local_model_id": ""})
    _unload_if_current(model_id)


def move_model_file(source_path: str, label: str = None) -> dict:
    """
    Переносит .gguf в /models/ и сразу регистрирует как установленную модель.
    Возвращает добавленную запись (entry).
    """
    if not source_path:
        raise ValueError("Путь к файлу не указан")

    filename = os.path.basename(source_path)
    dest_path = os.path.join(MODELS_DIR, filename)

    try:
        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            shutil.move(source_path, dest_path)
    except Exception as e:
        raise RuntimeError(f"Ошибка при перемещении файла модели: {e}")

    return register_model(dest_path, label=label)


# ── In-process инференс через llama-cpp-python ─────────────────────────────────

_loaded_lock = threading.Lock()
_loaded_path = None
_loaded_llm = None


def _unload_if_current(model_id: str):
    global _loaded_path, _loaded_llm
    removed = next((x for x in list_installed_models() if x.get("id") == model_id), None)
    with _loaded_lock:
        if removed and _loaded_path == removed.get("path"):
            _loaded_llm = None
            _loaded_path = None


def _get_llm(path: str):
    global _loaded_path, _loaded_llm

    with _loaded_lock:
        if _loaded_llm is not None and _loaded_path == path:
            return _loaded_llm

        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError(
                "Библиотека llama-cpp-python не установлена — "
                "локальные модели без неё работать не могут."
            )

        if not os.path.isfile(path):
            raise RuntimeError(f"Файл модели не найден: {path}")

        # Узнаём тренировочный контекст модели заранее (дешёвая операция,
        # только чтение метаданных, без полной загрузки весов)
        try:
            probe = Llama(model_path=path, n_ctx=8, verbose=False, vocab_only=False)
            n_ctx_train = probe.n_ctx_train()
            del probe
        except Exception:
            n_ctx_train = 2048  # безопасный дефолт, если метаданные прочитать не удалось

        safe_ctx = min(4096, n_ctx_train)

        _loaded_llm = Llama(
            model_path=path,
            n_ctx=safe_ctx,
            n_threads=os.cpu_count() or 4,
            verbose=True,
        )
        _loaded_path = path
        return _loaded_llm


def call_local_llm(messages: list, model: str = None, max_tokens: int = 2048) -> str:
    """
    Генерирует ответ активной локальной моделью.
    model (опционально) — id установленной модели или прямой путь к .gguf.
    """
    entry = None
    if model:
        entry = next((m for m in list_installed_models() if m.get("id") == model), None)
        path = entry["path"] if entry else model
    else:
        entry = get_active_model()
        if not entry:
            raise RuntimeError("Локальная модель не выбрана. Выберите файл в Настройках AI.")
        path = entry["path"]

    llm = _get_llm(path)

    # Универсальный потолок для CPU-инференса — не даём случайно уйти в
    # многоминутную генерацию на слабом железе.
    max_tokens = min(max_tokens, 256)

    # Стоп-токены нескольких популярных семейств моделей разом — лишние
    # варианты безвредны, если модель их не использует.
    stop_tokens = [
        "</s>",           # Llama-2 / TinyLlama / Mistral (классика)
        "<|im_end|>",     # ChatML — Qwen, многие современные finetune
        "<|eot_id|>",     # Llama-3 / Llama-3.1
        "<end_of_turn>",  # Gemma
        "<|end|>",        # Phi-3
    ]

    try:
        result = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            repeat_penalty=1.15,
            stop=stop_tokens,
        )
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"Ошибка локальной модели: {e}")