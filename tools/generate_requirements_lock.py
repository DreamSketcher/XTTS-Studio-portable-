#!/usr/bin/env python3
"""
tools/generate_requirements_lock.py — TASK-017.

Генерирует hash-locked requirements.lock из requirements.txt (источник правды для
ВЕРСИЙ), используя pip-compile (pip-tools) ИЛИ uv pip compile — что доступно.

Политика (ТЗ):
  • requirements.txt — source of truth для версий (прямые пины);
  • requirements.lock — полный resolved граф + --hash для reproducibility;
  • CI и installer используют lock с hash-verification (pip install --require-hashes).

Запуск:
    python tools/generate_requirements_lock.py            # авто: uv → pip-compile
    python tools/generate_requirements_lock.py --tool uv
    python tools/generate_requirements_lock.py --tool pip-compile

Lock-файл генерируется мейнтейнером и коммитится; перегенерация — при смене
requirements.txt (CI это подсказывает через tools/check_requirements_lock.py).
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements.lock"
HEADERS = [
    "# requirements.lock — hash-locked, reproducible runtime graph (TASK-017).",
    "#",
    "# НЕ редактируйте вручную. Источник правды для ВЕРСИЙ — requirements.txt;",
    "# этот файл = полный resolved граф + SHA-256 хеши для pip --require-hashes.",
    "# Перегенерация: python tools/generate_requirements_lock.py",
    "# Проверка актуальности в CI: python tools/check_requirements_lock.py",
    "#",
    "# Замечания про fairseq/rvc-python (ставятся отдельно через --no-deps, см.",
    "# requirements.txt) — их нет в lock: они не тянутся pip install -r requirements.txt.",
    "",
]


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def compile_with_uv() -> bool:
    if not shutil.which("uv"):
        return False
    print("[lock] using uv pip compile")
    proc = _run(
        [
            "uv",
            "pip",
            "compile",
            "--generate-hashes",
            "--no-emit-package",
            "fairseq",
            "--no-emit-package",
            "rvc-python",
            "--output-file",
            str(LOCK),
            "requirements.txt",
        ]
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        return False
    return True


def compile_with_piptools() -> bool:
    bin_ = shutil.which("pip-compile")
    if not bin_:
        return False
    print("[lock] using pip-compile (pip-tools)")
    proc = _run(
        [
            bin_,
            "requirements.txt",
            "--generate-hashes",
            "--output-file",
            str(LOCK),
            "--no-emit-index-url",
            "--allow-unsafe",
        ]
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        return False
    return True


def _prepend_headers():
    existing = LOCK.read_text(encoding="utf-8") if LOCK.exists() else ""
    LOCK.write_text("\n".join(HEADERS) + "\n" + existing, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate hash-locked requirements.lock.")
    parser.add_argument("--tool", choices=["auto", "uv", "pip-compile"], default="auto")
    args = parser.parse_args(argv)

    if args.tool in ("auto", "uv") and compile_with_uv():
        _prepend_headers()
        print(f"✅ Written {LOCK} (uv)")
        return 0
    if args.tool in ("auto", "pip-compile") and compile_with_piptools():
        _prepend_headers()
        print(f"✅ Written {LOCK} (pip-compile)")
        return 0
    print(
        "❌ Не удалось сгенерировать lock. Установите uv (`pip install uv`) или "
        "pip-tools (`pip install pip-tools`) и повторите.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
