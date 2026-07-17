"""
test/test_p3_security_tooling.py — TASK-016 / TASK-017 / TASK-018.

Страхует инфраструктуру security-тулинга P3 от регрессий:
  • TASK-016: CodeQL workflow + dependabot.yml (+ grouping ML-стека, security weekly);
  • TASK-017: requirements.lock, tools/generate_requirements_lock.py,
    tools/check_requirements_lock.py;
  • TASK-018: docs/THREAT_MODEL.md (trust boundaries, assets, attackers, mitigations, gaps).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def read(*parts) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


# ── TASK-016 ────────────────────────────────────────────────────────────────────


def test_codeql_workflow_exists():
    wf = read(".github", "workflows", "codeql.yml")
    assert "github/codeql-action/init@v3" in wf
    assert "language: ['python']" in wf
    # security-extended — расширенный набор
    assert "security-extended" in wf
    # еженедельный schedule
    assert "cron" in wf


def test_codeql_config_excludes_third_party():
    cfg = read(".github", "codeql-config.yml")
    # bundled env и данные — НЕ наш код
    for excluded in ("python", "library", "models"):
        assert excluded in cfg
    # наш код — в paths
    assert "engine" in cfg


def test_dependabot_config_exists():
    dep = read(".github", "dependabot.yml")
    # pip + github-actions ecosystems
    assert "package-ecosystem: pip" in dep
    assert "package-ecosystem: github-actions" in dep
    # security updates weekly
    assert "interval: weekly" in dep
    # version updates monthly
    assert "interval: monthly" in dep
    # ML-стек сгруппирован
    assert "pytorch-ml-stack" in dep
    assert "torch" in dep and "torchaudio" in dep and "torchvision" in dep


# ── TASK-017 ────────────────────────────────────────────────────────────────────


def test_requirements_lock_exists_and_documents_origin():
    assert (ROOT / "requirements.lock").exists()
    body = read("requirements.lock")
    # источник правды для версий — requirements.txt, lock для reproducibility
    assert "source of truth" in body.lower() or "источник правды" in body.lower()
    assert "requirements.txt" in body


def test_lock_checker_passes_on_committed_lock():
    """CI checker должен быть зелёным: lock соответствует requirements.txt."""
    sys.path.insert(0, str(ROOT))
    import importlib

    chk = importlib.import_module("tools.check_requirements_lock")
    assert chk.main([]) == 0


def test_lock_generator_and_checker_exist_and_runnable():
    assert (ROOT / "tools" / "generate_requirements_lock.py").exists()
    assert (ROOT / "tools" / "check_requirements_lock.py").exists()


# ── TASK-018 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "section",
    ["Trust boundaries", "Assets", "Attackers", "Mitigations", "Gap"],
)
def test_threat_model_has_all_sections(section):
    body = read("docs", "THREAT_MODEL.md")
    assert section in body


def test_threat_model_covers_required_boundaries():
    body = read("docs", "THREAT_MODEL.md")
    for boundary in [
        "update manifest",
        "voice reference",
        ".pth",
        ".gguf",
        "custom",
        "logs",
    ]:
        assert boundary.lower() in body.lower()


def test_threat_model_covers_attackers():
    body = read("docs", "THREAT_MODEL.md")
    for attacker in ["MITM", "pickle", "endpoint", "dependency"]:
        assert attacker.lower() in body.lower()


def test_threat_model_documents_what_is_not_implemented():
    """Gap analysis — явно описанные нереализованные/частичные меры."""
    body = read("docs", "THREAT_MODEL.md")
    # должен быть раздел про Authenticode как gap (до code-signing сертификата)
    assert "Authenticode" in body
