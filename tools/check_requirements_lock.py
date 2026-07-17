#!/usr/bin/env python3
"""
tools/check_requirements_lock.py — TASK-017.

Проверка актуальности requirements.lock относительно requirements.txt в CI.
Не падает, если lock отсутствует (он опционален — генерируется мейнтейнером), но
если lock существует, то каждый прямой pin из requirements.txt обязан присутствовать
в lock с совпадающей версией. Иначе CI напоминает перегенерировать lock.

Запуск (CI):
    python tools/check_requirements_lock.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*==\s*([^;\s]+)")


def parse_requirements(path: Path) -> dict:
    pins = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = PIN_RE.match(line)
        if not m:
            continue
        pins[m.group(1).lower()] = m.group(2)
    return pins


def main(argv=None):
    req_path = ROOT / "requirements.txt"
    lock_path = ROOT / "requirements.lock"
    if not lock_path.exists():
        print("ℹ️ requirements.lock отсутствует — hash-locking опционален (TASK-017). Пропуск.")
        return 0

    req_pins = parse_requirements(req_path)
    lock_text = lock_path.read_text(encoding="utf-8")

    stale = []
    for name, version in req_pins.items():
        # lock-строка вида 'name==version' или 'name==version \\\n  --hash=...'
        pat = re.compile(rf"(?m)^\s*{re.escape(name)}\s*==\s*{re.escape(version)}(?:\s|$|\\)", re.I)
        if not pat.search(lock_text):
            stale.append(f"{name}=={version}")

    if stale:
        print("❌ requirements.lock устарел относительно requirements.txt:")
        for s in stale:
            print(f"   - {s}")
        print("\nПерегенерируйте lock: python tools/generate_requirements_lock.py")
        return 1

    print(f"✅ requirements.lock актуален ({len(req_pins)} прямых пинов найдены).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
