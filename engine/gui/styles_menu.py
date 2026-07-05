# -*- coding: utf-8 -*-
"""engine/gui/styles_menu.py — всплывающее меню «Стили» с пресетами
(перенесено из gui.py: PRESET_HINT, STYLES_HINT, open_styles_menu)."""
import tkinter as tk

from i18n import t

from engine.gui.colors import Colors, scaled_font_size
from engine.gui.presets import open_quality_settings

# Внедряются из main_window: root, quality_var, save_settings, PRESET_DESCRIPTIONS
root = None
quality_var = None
save_settings = None
PRESET_DESCRIPTIONS = {}

# Кнопка «Стили» (создаётся в engine.gui.toolbar и внедряется сюда)
styles_btn = None

PRESET_HINT = t("tip_quality_default")
STYLES_HINT = t("tip_styles")


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def open_styles_menu(event=None):
    menu = tk.Toplevel(root)
    menu.wm_overrideredirect(True)
    menu.configure(bg=Colors.MENU_BG, padx=4, pady=4)
    presets = [
        ("📖 " + t("preset_narrative"), "Нарратив"),
        ("⚡ " + t("preset_dynamic"), "Динамика"),
        ("🎭 " + t("preset_expressive"), "Экспрессия"),
    ]
    default_desc = "Наведите на пресет —\nздесь появится его описание."
    def close_menu():
        try:
            menu.destroy()
        except Exception:
            pass
    def select_preset(name):
        quality_var.set(name)
        save_settings()
    def select_and_open(name):
        quality_var.set(name)
        save_settings()
        close_menu()
        open_quality_settings(name)
    for label, value in presets:
        is_active = (quality_var.get() == value)
        item_bg = Colors.MENU_ACTIVE if is_active else Colors.MENU_BG
        item = tk.Label(
            menu,
            text=label,
            bg=item_bg,
            fg=Colors.TEXT_MAIN,
            font=("Segoe UI", scaled_font_size(10), "bold" if is_active else "normal"),
            padx=10, pady=5,
            anchor="w",
            cursor="hand2"
        )
        item.pack(fill="x", pady=1)
        def on_enter(e, w=item, active=is_active, name=value):
            if not active:
                w.config(bg=Colors.MENU_HOVER)
            desc_label.config(text=PRESET_DESCRIPTIONS.get(name, default_desc))
        def on_leave(e, w=item, active=is_active):
            if not active:
                w.config(bg=Colors.MENU_BG)
        item.bind("<Enter>", on_enter)
        item.bind("<Leave>", on_leave)
        item.bind("<Button-1>", lambda e, n=value: select_preset(n))
        item.bind("<Double-Button-1>", lambda e, n=value: select_and_open(n))
    sep = tk.Frame(menu, bg=Colors.BORDER, height=1)
    sep.pack(fill="x", padx=4, pady=(4, 4))
    desc_label = tk.Label(
        menu,
        text=default_desc,
        bg=Colors.MENU_BG,
        fg=Colors.TEXT_DIM,
        font=("Segoe UI", scaled_font_size(8)),
        justify="left",
        anchor="w",
        wraplength=200,
        padx=12, pady=6
    )
    desc_label.pack(fill="x")
    def desc_leave(e):
        desc_label.config(text=default_desc)
    desc_label.bind("<Enter>", lambda e: None)
    desc_label.bind("<Leave>", desc_leave)
    menu.update_idletasks()
    menu_w = menu.winfo_reqwidth()
    menu_h = menu.winfo_reqheight()
    x = styles_btn.winfo_rootx()
    y = styles_btn.winfo_rooty() - menu_h - 4
    if y < 0:
        y = styles_btn.winfo_rooty() + styles_btn.winfo_height() + 4
    menu.wm_geometry(f"+{x}+{y}")
    def click_outside(e):
        try:
            if not menu.winfo_exists():
                try: root.unbind_all("<Button-1>")
                except Exception: pass
                return
            wx, wy = menu.winfo_rootx(), menu.winfo_rooty()
            ww, wh = menu.winfo_width(), menu.winfo_height()
            if not (wx <= e.x_root <= wx + ww and wy <= e.y_root <= wy + wh):
                try: root.unbind_all("<Button-1>")
                except Exception: pass
                close_menu()
        except Exception:
            try: root.unbind_all("<Button-1>")
            except Exception: pass
            close_menu()
    root.after(50, lambda: root.bind_all("<Button-1>", click_outside, add="+"))
    menu.bind("<FocusOut>", lambda e: close_menu())
