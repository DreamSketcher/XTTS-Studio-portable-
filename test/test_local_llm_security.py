"""
test/test_local_llm_security.py — TASK-004 + TASK-007.

TASK-004: safe_filename (traversal, absolute, reserved Windows-имена, control-chars,
unicode-tricks, happy path) + containment-check внутри MODELS_DIR.
TASK-007: обязательные sha256/size_bytes для каталога, проверка hash/размера после
скачивания (rejection при несовпадении + удаление), флаг verified для ручных моделей.

Без сети: urllib.request.urlopen подменяется. Файл выполняется в CI (не в ignore-списке).
"""

import hashlib
from pathlib import Path

import pytest

import engine.local_llm_client as llc


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    settings_path = tmp_path / "gpt_settings.json"
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    monkeypatch.setattr(llc, "_SETTINGS_PATH", str(settings_path))
    monkeypatch.setattr(llc, "MODELS_DIR", str(models_dir))
    return {"settings_path": settings_path, "models_dir": models_dir}


class _Resp:
    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0
        self.headers = {"Content-Length": str(len(data))}
        self.status = 200

    def read(self, n=-1):
        if self._pos >= len(self._data):
            return b""
        chunk = self._data[self._pos : self._pos + (n if n and n > 0 else len(self._data))]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ── TASK-004: safe_filename ──────────────────────────────────────────────────────


class TestSafeFilename:
    @pytest.mark.parametrize(
        "bad",
        [
            "../evil.gguf",  # traversal
            "..\\evil.gguf",
            "/absolute/x.gguf",  # absolute posix
            "C:\\temp\\x.gguf",  # absolute windows (colon)
            "a:b.gguf",  # colon (drive/alt-stream)
            "model/.gguf",  # embedded slash
            "CON.gguf",  # reserved w/ ext
            "nul",  # reserved no ext
            "PRN",
            "AUX",
            "COM1.gguf",
            "LPT9",
            "com5",  # lowercase reserved
            ".",  # dot
            "..",  # dotdot
            "",  # empty
            "   ",  # whitespace-only
            "a\x00b.gguf",  # NUL
            "a\nb.gguf",  # control char LF
            "a\x1fb.gguf",  # control char US
        ],
    )
    def test_rejects_unsafe(self, bad):
        with pytest.raises(ValueError):
            llc.safe_filename(bad)

    def test_happy_path(self):
        assert llc.safe_filename("model.gguf") == "model.gguf"

    def test_strips_and_keeps_spaces(self):
        assert llc.safe_filename("  Phi-3 mini.gguf  ") == "Phi-3 mini.gguf"

    def test_unicode_allowed(self):
        # unicode в имени разрешён (это не traversal/control)
        assert llc.safe_filename("модель-версия.gguf") == "модель-версия.gguf"

    def test_dotfile_like_not_reserved(self):
        # «.hidden.gguf» — base после точки = «hidden», не reserved
        assert llc.safe_filename(".hidden.gguf") == ".hidden.gguf"


# ── TASK-004: containment в download_model ───────────────────────────────────────


def test_download_blocks_traversal_before_network(tmp_settings, monkeypatch):
    """Имя с traversal отбивается safe_filename ДО любого сетевого запроса."""
    called = {"net": False}

    def fake_urlopen(*a, **k):
        called["net"] = True
        return _Resp(b"x")

    monkeypatch.setattr(llc.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ValueError):
        llc.download_model("http://x/evil.gguf", "../../evil.gguf")
    assert called["net"] is False, "сеть не должна была вызываться для traversal-имени"


# ── TASK-007: проверка целостности после скачивания ───────────────────────────────


def test_download_rejects_hash_mismatch_and_deletes(tmp_settings, monkeypatch):
    content = b"not the real model"
    monkeypatch.setattr(llc.urllib.request, "urlopen", lambda *a, **k: _Resp(content))
    with pytest.raises(RuntimeError, match="SHA-256"):
        llc.download_model("http://x/m.gguf", "m.gguf", expected_sha256="0" * 64)
    # повреждённый/подменённый файл удалён
    assert not (tmp_settings["models_dir"] / "m.gguf").exists()


def test_download_rejects_size_mismatch_and_deletes(tmp_settings, monkeypatch):
    content = b"12345"
    monkeypatch.setattr(llc.urllib.request, "urlopen", lambda *a, **k: _Resp(content))
    with pytest.raises(RuntimeError, match="Размер"):
        llc.download_model("http://x/m.gguf", "m.gguf", expected_size_bytes=999)
    assert not (tmp_settings["models_dir"] / "m.gguf").exists()


def test_download_passes_with_correct_hash_and_size(tmp_settings, monkeypatch):
    content = b"hello model bytes"
    digest = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(llc.urllib.request, "urlopen", lambda *a, **k: _Resp(content))
    path = llc.download_model(
        "http://x/m.gguf",
        "m.gguf",
        expected_sha256=digest,
        expected_size_bytes=len(content),
    )
    assert Path(path).exists()
    assert Path(path).read_bytes() == content


def test_download_without_expected_hash_behaves_as_before(tmp_settings, monkeypatch):
    """Совместимость: без expected_* проверка не запускается (поведение не изменилось)."""
    content = b"legacy"
    monkeypatch.setattr(llc.urllib.request, "urlopen", lambda *a, **k: _Resp(content))
    path = llc.download_model("http://x/m.gguf", "m.gguf")
    assert Path(path).read_bytes() == content


# ── TASK-007: каталог обязан иметь sha256/size_bytes ─────────────────────────────


def test_catalog_model_without_hash_cannot_be_installed(tmp_settings, monkeypatch):
    bad = [
        {
            "id": "broken-q4",
            "label": "Broken",
            "params_b": 1.0,
            "quant": "Q4_K_M",
            "quant_factor": 0.60,
            "description": "d",
            "download_link": "http://x/x.gguf",
            "filename": "x.gguf",
            # sha256/size_bytes отсутствуют — намеренно
        }
    ]
    monkeypatch.setattr(llc, "LOCAL_MODEL_CATALOG", bad)
    with pytest.raises(ValueError, match="sha256"):
        llc.install_catalog_model("broken-q4")


def test_builtin_catalog_has_full_integrity():
    """Все 5 моделей встроенного каталога содержат реальные sha256/size_bytes."""
    for m in llc.LOCAL_MODEL_CATALOG:
        assert m.get("sha256") and len(m["sha256"]) == 64, f"{m['id']} без sha256"
        assert m.get("size_bytes") and int(m["size_bytes"]) > 0, f"{m['id']} без size_bytes"


# ── TASK-007: verified-флаг ───────────────────────────────────────────────────────


def test_register_verified_flag(tmp_settings):
    manual = llc.register_model("/tmp/models/a.gguf")
    assert manual["verified"] is False
    assert llc.is_model_verified(manual) is False

    catalog_like = llc.register_model("/tmp/models/b.gguf", verified=True)
    assert catalog_like["verified"] is True
    assert llc.is_model_verified(catalog_like) is True


def test_move_model_registers_as_unverified(tmp_settings, tmp_path):
    src = tmp_path / "manual.gguf"
    src.write_bytes(b"data")
    entry = llc.move_model_file(str(src))
    assert entry["verified"] is False
