"""
test/test_docs_torch_versions.py — TASK-002.

Гарантирует, что версии torch/torchaudio/torchvision в docs (RU + EN) совпадают с
источником правды: requirements.txt и engine/env_core/torch_setup.py. Раньше docs
отставали (писали 2.11.0/0.26.0) — тест страхует от повторного расхождения.
"""

import re
from pathlib import Path

import pytest

from engine.env_core import torch_setup

ROOT = Path(__file__).resolve().parents[1]


def _requirements() -> dict[str, str]:
    result = {}
    for raw in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        result[name.lower()] = version
    return result


def _docs_versions(doc_path: Path) -> dict[str, str]:
    """Достаёт версии из блока установки Torch в docs (таблица/код)."""
    text = doc_path.read_text(encoding="utf-8")
    found = {}
    for pkg in ("torch", "torchaudio", "torchvision"):
        # строка вида 'torch       2.2.2' (выравнивание пробелами) или 'torch==2.2.2'
        m = re.search(rf"^\s*{pkg}\s+([0-9][0-9.]*)\s*$", text, re.MULTILINE)
        if m:
            found[pkg] = m.group(1)
    return found


def test_source_of_truth_is_consistent():
    """requirements.txt ↔ torch_setup.py (эталон, как в test_dependency_baseline)."""
    req = _requirements()
    assert req["torch"] == torch_setup.TORCH_VERSION == "2.2.2"
    assert req["torchaudio"] == torch_setup.TORCHAUDIO_VERSION == "2.2.2"
    assert req["torchvision"] == torch_setup.TORCHVISION_VERSION == "0.17.2"


@pytest.mark.parametrize("doc_name", ["DOCUMENTATION.RU.md", "DOCUMENTATION.EN.md"])
def test_docs_torch_version_matches_requirements(doc_name):
    req = _requirements()
    docs = _docs_versions(ROOT / "docs" / doc_name)
    assert set(docs) == {
        "torch",
        "torchaudio",
        "torchvision",
    }, f"{doc_name}: не удалось найти версии torch в блоке установки"
    for pkg in ("torch", "torchaudio", "torchvision"):
        assert (
            docs[pkg] == req[pkg] == getattr(torch_setup, f"{pkg.upper()}_VERSION")
        ), f"{doc_name}: {pkg} в docs ({docs[pkg]}) расходится с requirements/code ({req[pkg]})"
