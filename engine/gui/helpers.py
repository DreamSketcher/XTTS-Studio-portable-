# -*- coding: utf-8 -*-
"""engine/gui/helpers.py — вспомогательные функции, зависящие от tk-окна
(перенесено из gui.py: clean_path)."""
import ntpath

# Внедряется из main_window: root
root = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window.
    Имена совпадают с именами глобальных переменных исходного gui.py."""
    globals().update(deps)


def clean_path(p: str) -> str:
    p = (p or "").strip()
    try:
        if p.startswith("{") or "} {" in p:
            parts = root.tk.splitlist(p)
            if parts:
                p = parts[0]
    except Exception:
        pass
    p = p.strip("{}")
    p = p.replace("/", "\\")
    return ntpath.normpath(p)
