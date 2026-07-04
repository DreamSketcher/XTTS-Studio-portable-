"""
engine/local_llm_client.py — Client for Local LLMs (Ollama, LM Studio, etc.)
"""

import os
import json
import urllib.request
import urllib.error
import shutil

# ── Paths ──────────────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS_PATH = os.path.join(_BASE_DIR, "gpt_settings.json")
MODELS_DIR = os.path.join(_BASE_DIR, "models")

# Ensure models directory exists
os.makedirs(MODELS_DIR, exist_ok=True)

DEFAULT_LOCAL_URL = "http://localhost:11434/v1" # Default for Ollama
DEFAULT_LOCAL_MODEL = "llama3"

# ... (Rest of the file: LOCAL_MODEL_CATALOG, _read_settings, _write_settings)


# ── Local Model Catalogue ──────────────────────────────────────────────────────
# Metadata for common local models
LOCAL_MODEL_CATALOG = [
    {
        "id": "llama3",
        "label": "Llama 3 (8B)",
        "description": "Meta's high-performance small model. Great all-rounder.",
        "download_link": "https://ollama.com/library/llama3",
        "recommended_ram": "8GB+",
    },
    {
        "id": "mistral",
        "label": "Mistral (7B)",
        "description": "Efficient and powerful model, excellent for English/Code.",
        "download_link": "https://ollama.com/library/mistral",
        "recommended_ram": "8GB+",
    },
    {
        "id": "phi3",
        "label": "Phi-3 Mini (3.8B)",
        "description": "Microsoft's tiny but mighty model. Fast and lightweight.",
        "download_link": "https://ollama.com/library/phi3",
        "recommended_ram": "4GB+",
    },
    {
        "id": "deepseek-coder",
        "label": "DeepSeek Coder",
        "description": "Specialized in programming and technical tasks.",
        "download_link": "https://ollama.com/library/deepseek-coder",
        "recommended_ram": "8GB+",
    },
    {
        "id": "qwen2",
        "label": "Qwen 2 (7B)",
        "description": "Alibaba's model, strong in multilingual tasks and logic.",
        "download_link": "https://ollama.com/library/qwen2",
        "recommended_ram": "8GB+",
    },
]

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

# ── Model/URL Management ──────────────────────────────────────────────────────

def get_local_url() -> str:
    return _read_settings().get("local_llm_url", DEFAULT_LOCAL_URL)

def set_local_url(url: str):
    _write_settings({"local_llm_url": url.strip()})

def get_local_model() -> str:
    return _read_settings().get("local_llm_model", DEFAULT_LOCAL_MODEL)

def set_local_model(model: str):
    _write_settings({"local_llm_model": model.strip()})

def move_model_file(source_path: str) -> str:
    """
    Moves a model file from source_path to the project's models directory.
    Returns the new filename (model ID).
    """
    if not source_path:
        raise ValueError("Путь к файлу не указан")
    
    filename = os.path.basename(source_path)
    dest_path = os.path.join(MODELS_DIR, filename)
    
    try:
        shutil.move(source_path, dest_path)
        return filename
    except Exception as e:
        raise RuntimeError(f"Ошибка при перемещении файла модели: {e}")


# ── LLM Call ──────────────────────────────────────────────────────────────────

def call_local_llm(messages: list, model: str = None, max_tokens: int = 2048) -> str:
    """
    Makes a request to the local LLM server using OpenAI-compatible /chat/completions.
    """
    url = get_local_url()
    if not url.endswith("/chat/completions"):
        # Fix URL if it's just the base
        if url.endswith("/v1"):
            url += "/chat/completions"
        elif not url.endswith("/completions"):
            url += "/v1/chat/completions"

    if not model:
        model = get_local_model()

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local LLM HTTP Error {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Local LLM Network Error: {e.reason}. Is the server running?")
    except Exception as e:
        raise RuntimeError(f"Local LLM Error: {e}")
