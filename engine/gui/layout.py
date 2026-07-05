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

from engine.gui.colors import Colors, scaled_font_size
from engine.gui.gradient import GradientBackground
from engine.gui.widgets import CompatCTkFrame

# --- Layout Preset API ---
# Делегируем в theme_manager, единственный источник истины
try:
    from . import theme_manager
    def get_layout_preset(name: str | None = None) -> dict:
        return theme_manager.get_layout_preset(name)
except Exception:
    # Fallback, если theme_manager ещё не готов
    def get_layout_preset(name=None):
        return {
            "left_panel_width": 260,
            "padding_main_x": 8,
            "padding_main_y": 14,
            "panel_spacing": 2,
            "toggle_strip_width": 22,
            "right_panel_left_pad": 8,
        }

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
_current_layout_preset = {}


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
        preset = _current_layout_preset
        panel_spacing = preset.get("panel_spacing", 2)
        if _left_visible:
            left_panel.pack_forget()
            _toggle_arrow.config(text="▶")
        else:
            left_panel.pack(side="left", fill="y", padx=(0, panel_spacing),
                            before=toggle_strip)
            _toggle_arrow.config(text="◀")
        _left_visible = not _left_visible
        _save_panel_state()
    except Exception:
        pass


def build_layout(root, preset: dict | None = None):
    global main_gradient, main_container, left_panel, right_panel
    global toggle_strip, _toggle_arrow, _left_visible, _current_layout_preset

    # Загружаем пресет раскладки
    if preset is None:
        preset = get_layout_preset()
    _current_layout_preset = preset.copy()

    # Извлекаем геометрию из пресета (Classic = значения по умолчанию, идентичные старому поведению)
    left_panel_width = preset.get("left_panel_width", 260)
    padding_main_x = preset.get("padding_main_x", 8)
    padding_main_y = preset.get("padding_main_y", 14)
    panel_spacing = preset.get("panel_spacing", 2)
    toggle_strip_width = preset.get("toggle_strip_width", 22)
    right_panel_left_pad = preset.get("right_panel_left_pad", 8)

    main_gradient = GradientBackground(root, Colors.BG_DARK, Colors.GRADIENT_BOTTOM)
    main_container = CompatCTkFrame(root, fg_color="transparent", bg="transparent", corner_radius=0)
    main_container.pack(fill="both", expand=True, padx=padding_main_x, pady=padding_main_y)

    left_panel = CompatCTkFrame(main_container, fg_color="transparent", bg="transparent", width=left_panel_width, corner_radius=0)
    left_panel.pack(side="left", fill="y", padx=(0, panel_spacing))
    left_panel.pack_propagate(False)

    # ── Полоса-переключатель левой панели ──
    # Шире, чем раньше (22px), с крупной заметной стрелкой по центру.
    toggle_strip = tk.Frame(main_container, bg=Colors.BG_CARD, width=toggle_strip_width,
                            cursor="hand2",
                            highlightthickness=1,
                            highlightbackground=Colors.BORDER)
    toggle_strip.pack(side="left", fill="y", padx=(0, right_panel_left_pad))
    toggle_strip.pack_propagate(False)
    _toggle_arrow = tk.Label(
        toggle_strip, text="◀", bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
        font=("Segoe UI", scaled_font_size(13), "bold"), cursor="hand2"
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


def apply_layout_preset(preset: dict) -> bool:
    """
    Live-применение пресета раскладки.
    Возвращает True если хоть что-то применилось.

    ИСПРАВЛЕНО: раньше ширина left_panel и отступы main_container намеренно
    НЕ применялись live («чтобы не сломать pack-геометрию») — но это как раз
    ГЛАВНЫЕ визуальные параметры, отличающие Classic/Compact/Wide, поэтому
    переключение пресетов выглядело так, будто ничего не происходит.
    На практике left_panel создаётся с pack_propagate(False) (см. build_layout
    выше), поэтому left_panel.configure(width=...) и pack_configure(padx=...)
    у main_container/left_panel/toggle_strip применяются мгновенно и безопасно.
    """
    global _current_layout_preset
    _current_layout_preset = preset.copy()
    changed = False

    # 1. Ширина полосы-переключателя (toggle_strip)
    try:
        if toggle_strip is not None:
            w = preset.get("toggle_strip_width", 22)
            toggle_strip.config(width=w)
            changed = True
    except Exception:
        pass

    # 2. Ширина левой панели — теперь применяется live (см. docstring выше)
    try:
        if left_panel is not None:
            new_width = preset.get("left_panel_width", 260)
            left_panel.configure(width=new_width)
            changed = True
    except Exception:
        pass

    # 3. Отступы главного контейнера (main_container padx/pady) — live
    try:
        if main_container is not None:
            padx = preset.get("padding_main_x", 8)
            pady = preset.get("padding_main_y", 14)
            main_container.pack_configure(padx=padx, pady=pady)
            changed = True
    except Exception:
        pass

    # 4. Отступ между left_panel и toggle_strip (panel_spacing) — live,
    # только если панель сейчас видима (иначе left_panel не управляется
    # pack'ом и pack_configure бросит исключение — это нормально: новый
    # отступ применится сам собой при следующем показе панели, т.к.
    # toggle_left_panel() читает актуальный _current_layout_preset).
    try:
        if left_panel is not None and _left_visible:
            spacing = preset.get("panel_spacing", 2)
            left_panel.pack_configure(padx=(0, spacing))
            changed = True
    except Exception:
        pass

    # 5. Отступ между toggle_strip и right_panel (right_panel_left_pad) — live
    try:
        if toggle_strip is not None:
            right_pad = preset.get("right_panel_left_pad", 8)
            toggle_strip.pack_configure(padx=(0, right_pad))
            changed = True
    except Exception:
        pass

    return changed

