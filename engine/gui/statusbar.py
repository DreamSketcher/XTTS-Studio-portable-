# -*- coding: utf-8 -*-
"""engine/gui/statusbar.py — статусбар и прогресс-бар
(перенесено из gui.py: set_status, set_stage, set_progress, секция STATUS BAR)."""
import tkinter as tk

import customtkinter as ctk

from engine.gui.colors import Colors

# Внедряются из main_window: root, status_var, stage_var, progress_value
root = None
status_var = None
stage_var = None
progress_value = None

status_frame = None
progress_bar = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window.
    Имена совпадают с именами глобальных переменных исходного gui.py."""
    globals().update(deps)


def set_status(text):
    root.after(0, lambda: status_var.set(text))
def set_stage(text):
    root.after(0, lambda: stage_var.set(text))
def set_progress(value):
    try:
        value = max(0, min(100, int(value)))
    except Exception:
        return
    root.after(0, lambda: (progress_value.set(value),
                           globals().get("progress_bar") and progress_bar.set(value / 100)))


def build_statusbar(right_panel):
    global status_frame, progress_bar
    status_frame = tk.Frame(right_panel, bg=Colors.BG_CARD)
    status_frame.pack(fill="x", side="bottom", pady=(0, 0))
    progress_bar = ctk.CTkProgressBar(
        status_frame,
        orientation="horizontal",
        height=14,  # чуть выше — полоса больше не выглядит плоской
        fg_color=Colors.PROGRESS_BG,
        progress_color=Colors.PROGRESS_FG,
        corner_radius=7
    )
    progress_bar.pack(fill="x", padx=10, pady=(10, 5))
    progress_bar.set(0)
    tk.Label(status_frame, textvariable=status_var, anchor="w", bg=Colors.BG_CARD,
             fg=Colors.TEXT_MAIN, font=("Segoe UI", 11)).pack(fill="x", padx=10, pady=(0, 10))
