#!/usr/bin/env python3
"""
tools/pip_audit_gate.py — блокирующий security-gate поверх pip-audit.

Почему отдельный скрипт, а не «pip-audit || echo» в CI:
  pip-audit сам по себе не знает severity (его JSON-отчёт содержит только
  id/aliases/fix_versions) и не падает при наличии уязвимостей по умолчанию.
  Чтобы реализовать политику из ТЗ (TASK-001) —
    Critical/High → fail, ЕСЛИ уязвимость не listed в allowlist;
    Medium/Low    → warning (не падает);
    allowlist-записи не должны быть просрочены;
  мы запускаем pip-audit, обогащаем каждую уязвимость severity из OSV
  (database_specific.severity либо CVSS v3 вектор) и применяем политику.

Скрипт спроектирован так, чтобы ЧИСТАЯ логика политики (evaluate, load_allowlist,
expired_entries, cvss_v3_base_score) была покрыта unit-тестами без сети и без
самого pip-audit (см. test/test_pip_audit_gate.py).

Запуск:
    python tools/pip_audit_gate.py \
        --requirements requirements.txt \
        --allowlist .security/pip-audit-allowlist.yml
"""
import argparse
import datetime as _dt
import json
import math
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import contextlib

try:
    import yaml
except ImportError:  # pragma: no cover - CI гарантирует pyyaml
    yaml = None


ROOT = Path(__file__).resolve().parents[1]

# Политика severity (см. заголовок модуля). UNKNOWN применяется, когда OSV не
# дал ни qualitative-severity, ни CVSS вектора. По умолчанию — fail-closed (high),
# чтобы неизвестная серьёзность не «проскочила» как warning.
ALLOWLIST_REQUIRED_FIELDS = ("id", "package", "reason", "expires_at")
ALLOWLIST_OPTIONAL_FIELDS = ("issue_link",)
DEFAULT_UNKNOWN_SEVERITY = "high"
VALID_SEVERITIES = ("critical", "high", "medium", "low", "unknown")

_OSV_API = "https://api.osv.dev/v1/vulns/"
_OSV_TIMEOUT = 15


# ── CVSS v3.1 base score ────────────────────────────────────────────────────────
# Эталонная формула first.org CVSS v3.1. Нужна как fallback, когда у OSV-записи
# нет database_specific.severity, но есть CVSS-вектор в поле severity[].score.
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
_UI = {"N": 0.85, "R": 0.62}
_CI = {"H": 0.56, "L": 0.22, "N": 0.0}
_PR_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.50}


def _roundup(x: float) -> float:
    """CVSS roundup — наименьшее число с одним знаком после запятой, >= x."""
    return math.ceil(round(x, 10) * 10) / 10.0


def cvss_v3_base_score(vector: str):
    """Возвращает CVSS v3.1 Base Score (float) или None, если вектор не парсится."""
    if not vector or not vector.startswith("CVSS:3."):
        return None
    parts = {}
    for chunk in vector.split("/")[1:]:
        if ":" not in chunk:
            return None
        k, v = chunk.split(":", 1)
        parts[k] = v
    try:
        scope_changed = parts.get("S") == "C"
        av = _AV[parts["AV"]]
        ac = _AC[parts["AC"]]
        ui = _UI[parts["UI"]]
        pr = (_PR_CHANGED if scope_changed else _PR_UNCHANGED)[parts["PR"]]
        c, i, a = _CI[parts["C"]], _CI[parts["I"]], _CI[parts["A"]]
    except KeyError:
        return None
    isc_base = 1 - ((1 - c) * (1 - i) * (1 - a))
    if scope_changed:
        impact = 7.52 * (isc_base - 0.029) - 3.25 * (isc_base - 0.02) ** 15
    else:
        impact = 6.42 * isc_base
    exploitability = 8.22 * av * ac * pr * ui
    if impact <= 0:
        return 0.0
    if scope_changed:
        return _roundup(min(1.08 * (impact + exploitability), 10.0))
    return _roundup(min(impact + exploitability, 10.0))


def severity_band_from_score(score):
    """CVSS числовой балл → полоса политики."""
    if score is None:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


_QUALITATIVE = {
    "critical": "critical",
    "high": "high",
    "moderate": "medium",
    "medium": "medium",
    "low": "low",
}


def _map_qualitative(value):
    if not value:
        return None
    return _QUALITATIVE.get(str(value).strip().lower())


def osv_severity(vuln_id, fetch=None):
    """
    Запрашивает запись уязвимости из OSV и возвращает полосу severity.
    Приоритет: database_specific.severity → CVSS v3 вектор → DEFAULT_UNKNOWN_SEVERITY.
    `fetch` — инъектируемая функция (id) -> dict для тестов (без сети).
    """
    if not vuln_id:
        return DEFAULT_UNKNOWN_SEVERITY
    try:
        data = fetch(vuln_id) if fetch else _osv_fetch(vuln_id)
    except Exception:
        return DEFAULT_UNKNOWN_SEVERITY
    if not isinstance(data, dict):
        return DEFAULT_UNKNOWN_SEVERITY

    db_specific = data.get("database_specific") or {}
    mapped = _map_qualitative(db_specific.get("severity"))
    if mapped:
        return mapped

    for entry in data.get("severity") or []:
        score = cvss_v3_base_score(entry.get("score"))
        if score is not None:
            band = severity_band_from_score(score)
            if band != "unknown":
                return band
    return DEFAULT_UNKNOWN_SEVERITY


def _osv_fetch(vuln_id):
    req = urllib.request.Request(_OSV_API + urllib.parse.quote(vuln_id))
    with urllib.request.urlopen(req, timeout=_OSV_TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


# ── allowlist ───────────────────────────────────────────────────────────────────


def load_allowlist(path):
    """Читает и валидирует allowlist. Возвращает список записей-словарей."""
    raw = Path(path).read_text(encoding="utf-8")
    if yaml is None:
        raise RuntimeError("PyYAML не установлен — невозможно прочитать allowlist")
    data = yaml.safe_load(raw) or []
    if isinstance(data, dict):
        data = data.get("allowlist") or []
    if not isinstance(data, list):
        raise ValueError("allowlist должен быть списком записей")
    entries = []
    for n, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"allowlist: запись #{n} не является отображением")
        missing = [f for f in ALLOWLIST_REQUIRED_FIELDS if not item.get(f)]
        if missing:
            raise ValueError(f"allowlist: запись #{n} пропускает поля {missing}")
        entry = {f: str(item[f]).strip() for f in ALLOWLIST_REQUIRED_FIELDS}
        for f in ALLOWLIST_OPTIONAL_FIELDS:
            if item.get(f):
                entry[f] = str(item[f]).strip()
        entries.append(entry)
    return entries


def parse_date(value):
    """Парсит дату срока действия (ISO YYYY-MM-DD). ValueError при ошибке."""
    return _dt.date.fromisoformat(str(value).strip())


def expired_entries(allowlist, today=None):
    today = today or _dt.date.today()
    expired = []
    for entry in allowlist:
        try:
            expires = parse_date(entry["expires_at"])
        except ValueError:
            # битая дата — считаем просроченной (требует внимания мейнтейнера)
            expired.append(entry)
            continue
        if expires < today:
            expired.append(entry)
    return expired


def _ids_for(finding):
    ids = {finding.get("id")}
    for alias in finding.get("aliases") or []:
        ids.add(alias)
    ids.discard(None)
    return ids


def _is_allowlisted(finding, active_entries):
    ids = _ids_for(finding)
    return any(e["id"] in ids for e in active_entries)


def evaluate(findings, allowlist, today=None):
    """
    Применяет политику severity к списку findings (каждый уже несёт `severity`).
    Возвращает dict:
      fail: bool, blocking: [...], warned: [...], allowlisted: [...], expired: [...]
    """
    expired = expired_entries(allowlist, today)
    active = [e for e in allowlist if e not in expired]
    blocking, warned, allowlisted = [], [], []
    for finding in findings:
        sev = finding.get("severity") or DEFAULT_UNKNOWN_SEVERITY
        if sev == "unknown":
            sev = DEFAULT_UNKNOWN_SEVERITY
        # Critical и High блокируют, ЕСЛИ уязвимость не listed в allowlist.
        # Это осознанное отклонение от буквального «Critical → fail всегда»: замороженный
        # ML-стек (torch==2.2.2) физически несёт Critical CVE без скорого фикса (см. TASK-002),
        # поэтому Critical допустимо подавлять — но ТОЛЬКО как задокументированную,
        # датированную запись с reason/issue_link (см. docs/SECURITY.md). Новая Critical CVE,
        # которой нет в allowlist, по-прежнему валит gate.
        if sev in ("critical", "high"):
            if _is_allowlisted(finding, active):
                allowlisted.append(finding)
            else:
                blocking.append(finding)
        else:  # medium / low
            warned.append(finding)
    return {
        "fail": bool(blocking) or bool(expired),
        "blocking": blocking,
        "warned": warned,
        "allowlisted": allowlisted,
        "expired": expired,
    }


# ── pip-audit runner ─────────────────────────────────────────────────────────────


def _parse_pip_audit_report(report_text):
    data = json.loads(report_text)
    deps = data.get("dependencies") if isinstance(data, dict) else data
    findings = []
    for dep in deps or []:
        name = dep.get("name")
        version = dep.get("version")
        for vuln in dep.get("vulns") or []:
            findings.append(
                {
                    "id": vuln.get("id"),
                    "aliases": list(vuln.get("aliases") or []),
                    "package": name,
                    "version": version,
                    "fix_versions": list(vuln.get("fix_versions") or []),
                }
            )
    return findings


def run_pip_audit(requirements, runner=None):
    """
    Запускает pip-audit над requirements и возвращает findings (без severity).
    `runner` — инъектируемая функция (cmd) -> (returncode, report_text) для тестов.
    """
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tmp:
        report_path = tmp.name
    cmd = [
        "pip-audit",
        "-r",
        str(requirements),
        "--no-deps",
        "--disable-pip",
        "--format",
        "json",
        "-o",
        report_path,
    ]
    if runner is None:
        proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603,S607
        returncode = proc.returncode
        report_text = (
            Path(report_path).read_text(encoding="utf-8") if os.path.exists(report_path) else ""
        )
    else:
        returncode, report_text = runner(cmd)
    with contextlib.suppress(OSError):
        os.remove(report_path)
    if not report_text.strip():
        # pip-audit упал раньше, чем записал отчёт (сеть/коллекция) — это ошибка gate.
        if returncode != 0:
            raise RuntimeError(f"pip-audit завершился с кодом {returncode} и без отчёта")
        return []
    return _parse_pip_audit_report(report_text)


def enrich_with_severity(findings, resolver=osv_severity, cache=None):
    """Добавляет поле `severity` в каждый finding через resolver(id)."""
    cache = {} if cache is None else cache
    for finding in findings:
        vid = finding.get("id")
        if vid not in cache:
            cache[vid] = resolver(vid) if vid else DEFAULT_UNKNOWN_SEVERITY
        finding["severity"] = cache[vid]
    return findings


# ── CLI ──────────────────────────────────────────────────────────────────────────


def _emit(line):
    print(line)


def main(argv=None):
    parser = argparse.ArgumentParser(description="pip-audit blocking gate (High/Critical CVE).")
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--allowlist", default=".security/pip-audit-allowlist.yml")
    parser.add_argument(
        "--report",
        default=None,
        help="готовый pip-audit JSON-отчёт (для отладки; без запуска pip-audit)",
    )
    args = parser.parse_args(argv)

    try:
        allowlist = load_allowlist(args.allowlist)
    except Exception as e:
        _emit(f"❌ allowlist невалиден: {e}")
        return 2

    expired = expired_entries(allowlist)
    for entry in expired:
        _emit(
            f"⏰ Просроченная allowlist-запись: {entry['id']} "
            f"({entry['package']}) — {entry['expires_at']}"
        )

    if args.report:
        findings = _parse_pip_audit_report(Path(args.report).read_text(encoding="utf-8"))
    else:
        findings = run_pip_audit(args.requirements)
    enrich_with_severity(findings)

    result = evaluate(findings, allowlist)

    for f in result["blocking"]:
        _emit(
            f"🚨 BLOCK [{f['severity'].upper()}] {f['package']}=={f['version']}: "
            f"{f['id']} (fix: {', '.join(f['fix_versions']) or '—'})"
        )
    for f in result["warned"]:
        _emit(
            f"⚠️  WARN [{f['severity'].upper()}] {f['package']}=={f['version']}: "
            f"{f['id']} (fix: {', '.join(f['fix_versions']) or '—'})"
        )
    for f in result["allowlisted"]:
        _emit(f"✅ SUPPRESSED [HIGH] {f['package']}=={f['version']}: {f['id']} (в allowlist)")

    if result["fail"]:
        if result["blocking"]:
            _emit(f"\n❌ SECURITY GATE: {len(result['blocking'])} blocking vulnerability(ies).")
        if expired:
            _emit(f"❌ SECURITY GATE: {len(expired)} expired allowlist entry(ies).")
        return 1

    _emit(
        f"\n✅ SECURITY GATE: passed "
        f"({len(result['warned'])} warning(s), {len(result['allowlisted'])} suppressed)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
