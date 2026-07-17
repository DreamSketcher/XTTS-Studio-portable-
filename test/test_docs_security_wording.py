"""
test/test_docs_security_wording.py — TASK-003.

Страхует docs от возврата переоценённых формулировок про Authenticode и pip-audit,
которые расходились с реальным поведением CI/release:
  • release workflow НЕ «требует» Authenticode (он её только проверяет; реальный
    gate целостности — Ed25519-подпись манифеста);
  • pip-audit — это blocking gate по High/Critical CVE с явным allowlist
    (а не просто «проверяется в CI»).
Проверяется в обеих языковых версиях.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RU = (ROOT / "docs" / "DOCUMENTATION.RU.md").read_text(encoding="utf-8")
EN = (ROOT / "docs" / "DOCUMENTATION.EN.md").read_text(encoding="utf-8")


def test_no_overstated_authenticode_claim():
    # старая переоценённая формулировка убрана в обеих версиях
    assert "требует валидную Authenticode-подпись" not in RU
    assert "requires valid EXE Authenticode" not in EN


def test_authenticode_softened_to_ed25519_gate():
    # смягчённая формулировка упоминает проверку подписи + Ed25519 как реальный gate
    assert "Authenticode" in RU and "Ed25519" in RU
    assert "Authenticode" in EN and "Ed25519" in EN


def test_pip_audit_is_blocking_gate_with_allowlist():
    # pip-audit описан как blocking gate с allowlist (не нейтральное «проверяется»)
    for text in (RU, EN):
        assert "pip-audit" in text
    assert "blocking gate" in RU and "allowlist" in RU
    assert "blocking gate" in EN and "allowlist" in EN


def test_security_files_consistent():
    # SECURITY.* также описывают gate, а не молчаливый «dependency review»
    sec_ru = (ROOT / "docs" / "SECURITY.RU.md").read_text(encoding="utf-8")
    sec_en = (ROOT / "docs" / "SECURITY.md").read_text(encoding="utf-8")
    assert "blocking gate" in sec_ru and "allowlist" in sec_ru
    assert "blocking gate" in sec_en and "allowlist" in sec_en
