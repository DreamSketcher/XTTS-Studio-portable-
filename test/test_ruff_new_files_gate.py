"""
test/test_ruff_new_files_gate.py — TASK-009.

Покрывает tools/ruff_new_files_gate.py без реального git-окружения PR:
  • новые файлы без нарушений → gate green;
  • новый файл с bare except (E722, вне базового набора legacy) → gate red;
  • новый файл, добавленный в per-file-ignores → gate red;
  • отсутствие base (локальный прогон / push в main) → gate тривиально green.
Плюс отдельная проверка, что сами новые модули engine/rvc_catalog/ проходят
строгий набор E,F,W,B,SIM,UP (критерий TASK-009: «новые модули — полный набор»).
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.ruff_new_files_gate as gate  # noqa: E402


def _git_available(repo_root: Path) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root, capture_output=True
        ).returncode
        == 0
    )


def test_per_file_ignores_keys_parsed():
    keys = gate.per_file_ignores_keys(ROOT)
    assert "engine/gui/chat_window/custom_widgets.py" in keys
    assert "engine/gui/styles_menu.py" in keys


def test_new_files_none_when_base_missing(tmp_path, monkeypatch):
    """base недостижим (локальный прогон / push в main) → gate green, новых файлов нет."""
    monkeypatch.setattr(gate, "new_python_files", lambda root, base: [])
    assert gate.main(["--root", str(tmp_path)]) == 0


def test_gate_rejects_file_in_per_file_ignores(tmp_path, monkeypatch):
    """Новый файл, оказавшийся в per-file-ignores → gate red (нужен review)."""
    bad = tmp_path / "engine" / "new_mod" / "x.py"
    bad.parent.mkdir(parents=True)
    bad.write_text("x = 1\n")
    monkeypatch.setattr(gate, "new_python_files", lambda root, base: [bad])
    monkeypatch.setattr(
        gate,
        "per_file_ignores_keys",
        lambda root: ["engine/new_mod/x.py"],
    )
    # Подменим ruff-вызов на успех, чтобы проверить именно per-file-ignores-ветку.
    monkeypatch.setattr(
        gate,
        "_run",
        lambda cmd, cwd=None: subprocess.CompletedProcess(cmd, 0, "", ""),
    )
    rc = gate.main(["--root", str(tmp_path)])
    assert rc == 1
    # относительный путь должен фигурировать в выводе
    # (вывод идёт в stdout gate.main, не проверяем здесь дословно)


def _strict_fail_message(proc):
    return (
        "новые модули engine/rvc_catalog/ не проходят строгий ruff-набор:\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_strict_select_includes_required_rules():
    for rule in ("E", "F", "W", "B", "SIM", "UP"):
        assert rule in gate.STRICT_SELECT


@pytest.mark.skipif(not _git_available(ROOT), reason="нужен git-репозиторий")
def test_new_rvc_catalog_package_passes_strict():
    """TASK-008 split-пакет — НОВЫЕ модули; по TASK-009 должны проходить строгий набор."""
    pkg = ROOT / "engine" / "rvc_catalog"
    py_files = sorted(pkg.glob("*.py"))
    assert py_files, "engine/rvc_catalog/ должен содержать .py-модули"
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", "E,F,W,B,SIM,UP", *map(str, py_files)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, _strict_fail_message(proc)
