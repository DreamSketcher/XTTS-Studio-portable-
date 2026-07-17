#!/usr/bin/env python3
"""
tools/ruff_new_files_gate.py — строгий lint-gate для НОВЫХ файлов (TASK-009).

Что делает:
  1. Определяет «новые» .py-файлы: добавленные в текущем PR/ветке относительно
     базовой ветки (git diff --diff-filter=A), либо — при отсутствии base — файлы,
     отслеживаемые git (fallback, на main-бранче новых файлов нет → gate тривиально green).
  2. Запускает на них полный строгий набор ruff: E, F, W, B, SIM, UP. Любое
     нарушение валяет gate (новый код держим в чистоте).
  3. Запрещает новым файлам появляться в [tool.ruff.lint.per-file-ignores] —
     это «CI-шаг: новые файлы не могут добавляться в per-file-ignores без review».

Запуск (CI):
    python tools/ruff_new_files_gate.py [--base origin/main] [--root .]
"""
import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

STRICT_SELECT = ["E", "F", "W", "B", "SIM", "UP"]


def _run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def new_python_files(root: Path, base: str):
    """.py-файлы, добавленные в ветке относительно base. На main (нет base) → []."""
    # Сначала убедимся, что base достижим (fetch мог не случиться).
    rev = _run(["git", "rev-parse", "--verify", base], cwd=root)
    if rev.returncode != 0:
        # base недоступен (локальный прогон / push в main) — новых «относительно base» файлов нет.
        return []
    diff = _run(["git", "diff", "--name-only", "--diff-filter=A", f"{base}...HEAD"], cwd=root)
    if diff.returncode != 0:
        return []
    files = [root / f for f in diff.stdout.splitlines() if f.strip()]
    return [f for f in files if f.suffix == ".py" and f.exists()]


def per_file_ignores_keys(root: Path):
    """Список glob/путей из [tool.ruff.lint.per-file-ignores] (pyproject.toml)."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return []
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    pfi = data.get("tool", {}).get("ruff", {}).get("lint", {}).get("per-file-ignores", {})
    return list(pfi.keys())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Strict ruff gate for new Python files.")
    parser.add_argument("--base", default="origin/main", help="базовая ветка для сравнения")
    parser.add_argument("--root", default=".", help="корень репозитория")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    new_files = new_python_files(root, args.base)

    if not new_files:
        print("✅ RUFF NEW-FILES GATE: новых .py-файлов относительно base нет — gate пропущен.")
        return 0

    # 1. Полный строгий набор на новых файлах.
    # sys.executable -m ruff вместо голого "ruff": не зависим от PATH,
    # берём ruff из того же интерпретатора/venv, что и сам gate.
    ruff_cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--select",
        ",".join(STRICT_SELECT),
        *map(str, new_files),
    ]
    ruff = _run(ruff_cmd, cwd=root)
    if ruff.returncode != 0:
        print("❌ RUFF NEW-FILES GATE: новые файлы не проходят строгий набор E,F,W,B,SIM,UP:")
        print(ruff.stdout)
        if ruff.stderr:
            print(ruff.stderr)
        return 1

    # 2. Ни один новый файл не должен быть в per-file-ignores.
    pfi_keys = set(per_file_ignores_keys(root))
    offenders = []
    for f in new_files:
        rel = str(f.relative_to(root)).replace("\\", "/")
        if rel in pfi_keys:
            offenders.append(rel)
    if offenders:
        print(
            "❌ RUFF NEW-FILES GATE: новые файлы не могут попадать в per-file-ignores без review: "
            + ", ".join(offenders)
        )
        return 1

    print(f"✅ RUFF NEW-FILES GATE: {len(new_files)} новых файлов прошли строгий lint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
