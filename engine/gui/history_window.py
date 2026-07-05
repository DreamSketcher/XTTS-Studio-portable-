# -*- coding: utf-8 -*-
"""engine/gui/history_window.py — окно «История» (перенесено из gui.py: open_history)."""
import json
import os
import tkinter as tk
from tkinter import messagebox

from i18n import t

from engine.history_store import HISTORY_PATH
from engine.gui.colors import Colors, scaled_font_size
from engine.gui.textbox import set_textbox_content

# Внедряется из main_window: root
root = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def open_history():
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []
    win = tk.Toplevel(root)
    win.title(t("win_history_title"))
    win.geometry("720x500")
    win.resizable(True, True)
    win.configure(bg=Colors.BG_DARK)
    win.grab_set()
    toolbar = tk.Frame(win, bg=Colors.BG_CARD, pady=6)
    toolbar.pack(fill="x")
    lbl_count = tk.Label(toolbar, text=t("entries_count", len(history)),
                         bg=Colors.BG_CARD, fg=Colors.TEXT_DIM, font=("Segoe UI", scaled_font_size(9)))
    lbl_count.pack(side="left", padx=12)
    def clear_history():
        if not messagebox.askyesno(t("ctx_clear"), t("dlg_clear_history"), parent=win):
            return
        try:
            os.remove(HISTORY_PATH)
        except Exception:
            pass
        for w in list(scroll_inner.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        lbl_count.config(text=t("entries_count", 0))
    tk.Button(
        toolbar, text=t("btn_clear_history"), command=clear_history,
        bg=Colors.BG_INPUT, fg=Colors.TEXT_ERROR,
        activebackground=Colors.BG_DANGER, activeforeground=Colors.TEXT_MAIN,
        relief="flat", bd=0, font=("Segoe UI", scaled_font_size(9)), padx=10, pady=4, cursor="hand2"
    ).pack(side="right", padx=10)
    tk.Frame(win, bg=Colors.BORDER, height=1).pack(fill="x")
    list_outer = tk.Frame(win, bg=Colors.BG_DARK)
    list_outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(list_outer, bg=Colors.BG_DARK, bd=0, highlightthickness=0)
    scrollbar = tk.Scrollbar(list_outer, orient="vertical", command=canvas.yview,
                             bg=Colors.BG_INPUT, troughcolor=Colors.BG_DARK)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    scroll_inner = tk.Frame(canvas, bg=Colors.BG_DARK)
    canvas_window = canvas.create_window((0, 0), window=scroll_inner, anchor="nw")
    def _on_frame_configure(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
    def _on_canvas_configure(e):
        canvas.itemconfig(canvas_window, width=e.width)
    scroll_inner.bind("<Configure>", _on_frame_configure)
    canvas.bind("<Configure>", _on_canvas_configure)
    def _on_mousewheel(e):
        try:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except Exception:
            pass
    win.bind("<MouseWheel>", _on_mousewheel)
    for entry in history:
        card = tk.Frame(scroll_inner, bg=Colors.BG_CARD,
                        highlightthickness=1, highlightbackground=Colors.BORDER, bd=0)
        card.pack(fill="x", padx=8, pady=3)
        left = tk.Frame(card, bg=Colors.BG_CARD)
        left.pack(side="left", padx=12, pady=8)
        tk.Label(left, text=entry.get("date", ""),
                 bg=Colors.BG_CARD, fg=Colors.ACCENT,
                 font=("Segoe UI", scaled_font_size(8))).pack(anchor="w")
        tk.Label(left, text=f"🎤 {entry.get('voice', '?')}  ·  ⭐ {entry.get('quality', '?')}  ·  {entry.get('chunks', 0)} {t('chunks_word')}",
                 bg=Colors.BG_CARD, fg=Colors.TEXT_DIM,
                 font=("Segoe UI", scaled_font_size(8))).pack(anchor="w", pady=(2, 0))
        text_preview = entry.get("text", "").replace("\n", " ")
        tk.Label(card, text=text_preview,
                 bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
                 font=("Segoe UI", scaled_font_size(9)), anchor="w",
                 wraplength=480, justify="left").pack(side="left", fill="x",
                                                      expand=True, pady=8)
        def _reuse(t_text=entry.get("text", "")):
            set_textbox_content(t_text)
            win.destroy()
        tk.Button(
            card, text="↩ ", command=_reuse,
            bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
            relief="flat", bd=0, font=("Segoe UI", scaled_font_size(11)),
            padx=8, pady=4, cursor="hand2",
            activebackground=Colors.BG_HOVER
        ).pack(side="right", padx=8)
    def on_close():
        canvas.unbind_all("<MouseWheel>")
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)
    if not history:
        tk.Label(scroll_inner, text=t("history_empty"),
                 bg=Colors.BG_DARK, fg=Colors.TEXT_DIM,
                 font=("Segoe UI", scaled_font_size(10))).pack(pady=40)
