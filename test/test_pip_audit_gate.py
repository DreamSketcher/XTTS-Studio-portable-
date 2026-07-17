"""
test/test_pip_audit_gate.py — unit-тесты для tools/pip_audit_gate.py (TASK-001).

Покрывает ЧИСТУЮ логику gate без сети и без самого pip-audit:
  • формат/схему allowlist (обязательные поля, отказ на мусоре);
  • детектирование просроченных allowlist-записей;
  • политику severity (Critical/High блокируют, если не в allowlist;
    Critical подавляется allowlist'ом как задокументированное исключение;
    Medium/Low — warning; просроченные — fail);
  • корректность CVSS v3.1 base-score калькулятора (эталонные векторы).
"""

import datetime as _dt
import textwrap
from pathlib import Path

import pytest

import tools.pip_audit_gate as gate


# ── allowlist: формат ───────────────────────────────────────────────────────────


def _write_allowlist(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "allowlist.yml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_allowlist_valid(tmp_path):
    path = _write_allowlist(
        tmp_path,
        textwrap.dedent(
            """
            allowlist:
              - id: CVE-2025-3000
                package: torch
                reason: jit.script not used
                expires_at: 2099-01-01
                issue_link: https://example/x
            """
        ),
    )
    entries = gate.load_allowlist(path)
    assert len(entries) == 1
    e = entries[0]
    assert e["id"] == "CVE-2025-3000"
    assert e["package"] == "torch"
    assert e["expires_at"] == "2099-01-01"
    assert e["issue_link"] == "https://example/x"


def test_load_allowlist_rejects_missing_required_field(tmp_path):
    path = _write_allowlist(
        tmp_path,
        textwrap.dedent(
            """
            allowlist:
              - id: CVE-1
                package: torch
                reason: x
                # expires_at отсутствует
            """
        ),
    )
    with pytest.raises(ValueError, match="expires_at"):
        gate.load_allowlist(path)


def test_load_allowlist_rejects_non_mapping_entry(tmp_path):
    path = _write_allowlist(
        tmp_path,
        textwrap.dedent(
            """
            allowlist:
              - "not-a-mapping"
            """
        ),
    )
    with pytest.raises(ValueError):
        gate.load_allowlist(path)


def test_load_allowlist_accepts_bare_list_and_empty(tmp_path):
    # пустой allowlist — валиден
    assert gate.load_allowlist(_write_allowlist(tmp_path, "allowlist: []")) == []
    # bare-список без обёртки — тоже валиден
    p = _write_allowlist(
        tmp_path,
        textwrap.dedent(
            """
            - id: CVE-2
              package: pillow
              reason: y
              expires_at: 2099-01-01
            """
        ),
    )
    assert len(gate.load_allowlist(p)) == 1


# ── allowlist: просрочка ─────────────────────────────────────────────────────────


def test_expired_entries_detected():
    today = _dt.date(2026, 7, 17)
    allowlist = [
        {"id": "CVE-A", "package": "torch", "reason": "r", "expires_at": "2026-07-16"},  # expired
        {"id": "CVE-B", "package": "torch", "reason": "r", "expires_at": "2026-10-17"},  # active
        {"id": "CVE-C", "package": "torch", "reason": "r", "expires_at": "not-a-date"},  # broken
    ]
    expired = gate.expired_entries(allowlist, today=today)
    ids = {e["id"] for e in expired}
    assert ids == {"CVE-A", "CVE-C"}


# ── политика severity ───────────────────────────────────────────────────────────


def _finding(vid, sev, aliases=None):
    return {
        "id": vid,
        "aliases": aliases or [],
        "package": "x",
        "version": "1",
        "fix_versions": [],
        "severity": sev,
    }


def test_critical_not_in_allowlist_blocks():
    res = gate.evaluate([_finding("CVE-1", "critical")], [], today=_dt.date(2026, 7, 17))
    assert res["fail"] is True
    assert len(res["blocking"]) == 1


def test_critical_in_allowlist_is_suppressed():
    allowlist = [
        {"id": "CVE-1", "package": "x", "reason": "r", "expires_at": "2099-01-01"},
    ]
    res = gate.evaluate([_finding("CVE-1", "critical")], allowlist, today=_dt.date(2026, 7, 17))
    assert res["fail"] is False
    assert len(res["allowlisted"]) == 1
    assert res["blocking"] == []


def test_high_blocks_unless_allowlisted():
    allowlist = [
        {"id": "CVE-H", "package": "x", "reason": "r", "expires_at": "2099-01-01"},
    ]
    # allowlisted High → suppressed
    assert (
        gate.evaluate([_finding("CVE-H", "high")], allowlist, today=_dt.date(2026, 7, 17))["fail"]
        is False
    )
    # unallowlisted High → block
    assert (
        gate.evaluate([_finding("CVE-OTHER", "high")], allowlist, today=_dt.date(2026, 7, 17))[
            "fail"
        ]
        is True
    )


def test_allowlist_matches_by_alias():
    allowlist = [
        {"id": "GHSA-xxx", "package": "x", "reason": "r", "expires_at": "2099-01-01"},
    ]
    finding = _finding("PYSEC-1", "high", aliases=["CVE-9", "GHSA-xxx"])
    res = gate.evaluate([finding], allowlist, today=_dt.date(2026, 7, 17))
    assert res["fail"] is False
    assert len(res["allowlisted"]) == 1


def test_medium_and_low_never_block():
    today = _dt.date(2026, 7, 17)
    res = gate.evaluate([_finding("M", "medium"), _finding("L", "low")], [], today=today)
    assert res["fail"] is False
    assert len(res["warned"]) == 2
    assert res["blocking"] == []


def test_expired_allowlist_entry_fails_even_without_findings():
    allowlist = [
        {"id": "CVE-E", "package": "x", "reason": "r", "expires_at": "2020-01-01"},
    ]
    res = gate.evaluate([], allowlist, today=_dt.date(2026, 7, 17))
    assert res["fail"] is True  # просрочка сама по себе валит gate
    assert len(res["expired"]) == 1


def test_unknown_severity_treated_as_high():
    # fail-closed: неизвестная severity → high → блокирует, если не в allowlist
    res = gate.evaluate([_finding("U", "unknown")], [], today=_dt.date(2026, 7, 17))
    assert res["fail"] is True


# ── OSV severity resolution (через инъектируемый fetch) ──────────────────────────


def test_osv_severity_prefers_database_specific():
    def fetch(_vid):
        return {
            "database_specific": {"severity": "HIGH"},
            "severity": [
                {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N"}
            ],
        }

    assert gate.osv_severity("X", fetch=fetch) == "high"


def test_osv_severity_falls_back_to_cvss_vector():
    def fetch(_vid):
        return {
            "severity": [
                {"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"}
            ]
        }

    assert gate.osv_severity("X", fetch=fetch) == "critical"


def test_osv_severity_defaults_on_fetch_error():
    def fetch(_vid):
        raise OSError("network down")

    assert gate.osv_severity("X", fetch=fetch) == gate.DEFAULT_UNKNOWN_SEVERITY


# ── CVSS v3.1 base score (эталонные векторы) ─────────────────────────────────────


@pytest.mark.parametrize(
    "vector,expected",
    [
        # Log4Shell-эквивалент → 10.0 Critical
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0),
        # A:N → 0 информационный вектор, impact=0 → base 0.0
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0),
        # низкая сложность, partial impact → medium-диапазон
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N", pytest.approx(5.3)),
    ],
)
def test_cvss_v3_base_score_known_vectors(vector, expected):
    assert gate.cvss_v3_base_score(vector) == expected


def test_cvss_v3_base_score_rejects_garbage():
    assert gate.cvss_v3_base_score("not-a-vector") is None
    assert gate.cvss_v3_base_score("") is None


def test_parse_pip_audit_report_shape():
    report = (
        '{"dependencies": ['
        '{"name": "torch", "version": "2.2.2", "vulns": ['
        '{"id": "PYSEC-1", "aliases": ["CVE-1"], "fix_versions": ["2.5.0"]}]}], "fixes": []}'
    )
    findings = gate._parse_pip_audit_report(report)
    assert len(findings) == 1
    f = findings[0]
    assert f["id"] == "PYSEC-1"
    assert f["package"] == "torch"
    assert f["version"] == "2.2.2"
    assert f["aliases"] == ["CVE-1"]
    assert f["fix_versions"] == ["2.5.0"]


def test_run_pip_audit_uses_injected_runner():
    captured = {}

    def runner(cmd):
        captured["cmd"] = cmd
        return 0, '{"dependencies": [], "fixes": []}'

    findings = gate.run_pip_audit("requirements.txt", runner=runner)
    assert findings == []
    assert "pip-audit" in captured["cmd"]
    assert "--format" in captured["cmd"]
