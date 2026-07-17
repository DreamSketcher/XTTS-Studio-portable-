"""
test/test_docs_structure.py — TASK-010/012/013/014/015.

Страхует структуру docs и файлов контрибьюции от регрессий:
  • TASK-010: лицензионная таблица + THIRD_PARTY_NOTICES.md + генератор;
  • TASK-012: раздел «как сообщить о проблеме» в обоих DOCUMENTATION;
  • TASK-013: ровно 5 скриншотов встроены в каждый DOCUMENTATION;
  • TASK-014: таблица стартовых значений пресета;
  • TASK-015: GLOSSARY.md и ссылка на него из docs;
  • TASK-011: CONTRIBUTING.md, PR/issue templates, ссылка из README.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RU = (ROOT / "docs" / "DOCUMENTATION.RU.md").read_text(encoding="utf-8")
EN = (ROOT / "docs" / "DOCUMENTATION.EN.md").read_text(encoding="utf-8")
SCREENSHOTS = {
    "01_main_generation",
    "02_rvc_browser",
    "03_history_waveform",
    "04_quality_settings",
    "05_startup_recovery",
}


def test_license_table_present_both_langs():
    # TASK-010: таблица лицензий (XTTS/CPML/PyTorch/RVC/GGUF)
    for text in (RU, EN):
        assert "CPML" in text
        assert "BSD-3-Clause" in text


def test_third_party_notices_exists_and_generated():
    # TASK-010
    tpc = ROOT / "THIRD_PARTY_NOTICES.md"
    assert tpc.exists(), "THIRD_PARTY_NOTICES.md должен существовать"
    body = tpc.read_text(encoding="utf-8")
    # содержит ключевые компоненты и заголовок зависимости
    assert "CPML" in body
    assert "PyTorch" in body


def test_third_party_notices_generator_runs(tmp_path):
    # TASK-010: генератор работает на реальном SBOM
    import sys

    sys.path.insert(0, str(ROOT))
    import importlib

    gen = importlib.import_module("tools.generate_third_party_notices")
    out = tmp_path / "tpc.md"
    rc = gen.main(["--sbom", str(ROOT / "json" / "sbom.cdx.json"), "--output", str(out)])
    assert rc == 0
    assert out.exists()
    assert "PyTorch" in out.read_text(encoding="utf-8")


def test_bug_report_section_present_both_langs():
    # TASK-012
    for text in (RU, EN):
        assert "json/version.json" in text
        assert "logs/recovery_pip_output.log" in text
        assert "logs/startup_recovery_error.log" in text
        assert "github.com/DreamSketcher/XTTS-Studio-AI" in text


@pytest.mark.parametrize("doc", [RU, EN], ids=["RU", "EN"])
def test_exactly_five_screenshots_each(doc):
    # TASK-013: 5 скриншотов встроены
    found = set()
    for line in doc.splitlines():
        if "screenshots/" in line:
            for name in SCREENSHOTS:
                if name in line:
                    found.add(name)
    assert found == SCREENSHOTS, f"missing screenshots: {SCREENSHOTS - found}"


def test_screenshots_directory_and_readme():
    d = ROOT / "docs" / "screenshots"
    assert d.exists() and d.is_dir()
    assert (d / "README.md").exists()


def test_screenshot_readme_lists_five():
    body = (ROOT / "docs" / "screenshots" / "README.md").read_text(encoding="utf-8")
    for name in SCREENSHOTS:
        assert name in body


def test_preset_defaults_table_present_both_langs():
    # TASK-014
    for text in (RU, EN):
        # все 6 параметров фигурируют в таблице дефолтов
        for token in ("Temperature", "Top P", "Top K", "Repetition Penalty", "Speed", "Prosody"):
            assert token in text
        # значения по умолчанию пресета «Высокое качество»
        assert "0.70" in text
        assert "13.0" in text


def test_glossary_exists_and_referenced():
    # TASK-015
    g = ROOT / "docs" / "GLOSSARY.md"
    assert g.exists()
    body = g.read_text(encoding="utf-8")
    # ключевые унификации присутствуют
    for term in ("XTTS", "QC", "чанк", "GGUF"):
        assert term in body
    # ссылка из обоих DOCUMENTATION
    for text in (RU, EN):
        assert "GLOSSARY.md" in text


def test_contributing_and_templates_exist():
    # TASK-011
    assert (ROOT / "CONTRIBUTING.md").exists()
    assert (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").exists()
    issue_bug = ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
    assert issue_bug.exists()
    body = issue_bug.read_text(encoding="utf-8")
    # обязательные поля issue template
    for field in ("version", "cpu", "gpu", "repro"):
        assert field in body


def test_readme_links_contributing():
    for f in ("README.md", "README.ru.md"):
        body = (ROOT / f).read_text(encoding="utf-8")
        assert "CONTRIBUTING.md" in body
