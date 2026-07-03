# -*- coding: utf-8 -*-
"""engine/gui/layout.py — базовая раскладка главного окна
(перенесено из gui.py, секция LAYOUT: градиент, main_container, left/right panel).

Дополнено: левая панель — выдвижная. Между панелями расположена
вертикальная полоса-переключатель с заметной кнопкой-стрелкой («◀»/«▶»),
клик по которой скрывает или показывает левую панель. Положение панели
сохраняется в settings.json (ключ left_panel_visible) и восстанавливается
при следующем запуске.
"""
import json
import os
import tkinter as tk

from engine.gui.colors import Colors
from engine.gui.gradient import GradientBackground
from engine.gui.widgets import CompatCTkFrame

_SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "settings.json",
)

main_gradient = None
main_container = None
left_panel = None
right_panel = None

# ── Состояние выдвижной левой панели ──
toggle_strip = None
_toggle_arrow = None
_left_visible = True


def _load_saved_panel_state() -> bool:
    """Читает сохранённое положение левой панели (по умолчанию — видима)."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(data.get("left_panel_visible", True))
    except Exception:
        return True


def _save_panel_state() -> None:
    """Сохраняет положение левой панели в settings.json
    (не трогая остальные ключи)."""
    try:
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["left_panel_visible"] = _left_visible
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def toggle_left_panel(event=None):
    """Скрывает/показывает левую панель (клик по полосе-переключателю)."""
    global _left_visible
    try:
        if _left_visible:
            left_panel.pack_forget()
            _toggle_arrow.config(text="▶")
        else:
            left_panel.pack(side="left", fill="y", padx=(0, 2),
                            before=toggle_strip)
            _toggle_arrow.config(text="◀")
        _left_visible = not _left_visible
        _save_panel_state()
    except Exception:
        pass


def build_layout(root):
    global main_gradient, main_container, left_panel, right_panel
    global toggle_strip, _toggle_arrow, _left_visible
    main_gradient = GradientBackground(root, Colors.BG_DARK, Colors.GRADIENT_BOTTOM)
    main_container = CompatCTkFrame(root, fg_color="transparent", bg="transparent", corner_radius=0)
    main_container.pack(fill="both", expand=True, padx=8, pady=14)
    left_panel = CompatCTkFrame(main_container, fg_color="transparent", bg="transparent", width=260, corner_radius=0)
    left_panel.pack(side="left", fill="y", padx=(0, 2))
    left_panel.pack_propagate(False)

    # ── Полоса-переключатель левой панели ──
    # Шире, чем раньше (22px), с крупной заметной стрелкой по центру.
    toggle_strip = tk.Frame(main_container, bg=Colors.BG_CARD, width=22,
                            cursor="hand2",
                            highlightthickness=1,
                            highlightbackground=Colors.BORDER)
    toggle_strip.pack(side="left", fill="y", padx=(0, 8))
    toggle_strip.pack_propagate(False)
    _toggle_arrow = tk.Label(
        toggle_strip, text="◀", bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
        font=("Segoe UI", 13, "bold"), cursor="hand2"
    )
    _toggle_arrow.place(relx=0.5, rely=0.5, anchor="center")
    for w in (toggle_strip, _toggle_arrow):
        w.bind("<Button-1>", toggle_left_panel)
        w.bind("<Enter>", lambda e: (_toggle_arrow.config(fg=Colors.ACCENT),
                                     toggle_strip.config(bg=Colors.BG_HOVER),
                                     _toggle_arrow.config(bg=Colors.BG_HOVER)))
        w.bind("<Leave>", lambda e: (_toggle_arrow.config(fg=Colors.TEXT_MAIN),
                                     toggle_strip.config(bg=Colors.BG_CARD),
                                     _toggle_arrow.config(bg=Colors.BG_CARD)))
    _left_visible = True

    right_panel = CompatCTkFrame(main_container, fg_color="transparent", bg="transparent", corner_radius=0)
    right_panel.pack(side="left", fill="both", expand=True)

    # ── Восстановление сохранённого положения панели ──
    if not _load_saved_panel_state():
        # панель была скрыта в прошлой сессии — скрываем без записи в файл
        try:
            left_panel.pack_forget()
            _toggle_arrow.config(text="▶")
            _left_visible = False
        except Exception:
            pass

    return main_container, left_panel, right_panel
