# -*- coding: utf-8 -*-
"""engine/gui/ai_status_window.py — окно «AI статус» (перенесено из gui.py: open_ai_status_window)."""
import tkinter as tk

from i18n import t

from engine.gui.colors import Colors, scaled_font_size
from engine.gui.widgets import create_button

# Внедряется из main_window: root
root = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def open_ai_status_window():
    from engine.gpt_client import get_chain_diagnostics
    diag = get_chain_diagnostics()
    win = tk.Toplevel(root)
    win.title(t("win_ai_status_title"))
    win.geometry("560x520")
    win.resizable(True, True)
    win.configure(bg=Colors.BG_DARK)
    win.grab_set()
    try:
        from engine.tts_runner import detect_device
        device_str = detect_device().upper()
    except Exception:
        device_str = "?"
    header = tk.Frame(win, bg=Colors.BG_CARD, pady=10)
    header.pack(fill="x")
    tk.Label(
        header, text=t("ai_xtts_device", device_str),
        bg=Colors.BG_CARD, fg=Colors.TEXT_DIM, font=("Segoe UI", scaled_font_size(9))
    ).pack(anchor="w", padx=14)
    active_info = next((p for p in diag["providers"] if p["id"] == diag["active"]), None)
    active_label = active_info["label"] if active_info else diag["active"]
    active_key_ok = active_info["has_key"] if active_info else False
    tk.Label(
        header, text=t("ai_active_provider", active_label),
        bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(11), "bold")
    ).pack(anchor="w", padx=14, pady=(4, 0))
    tk.Label(
        header,
        text=(t("ai_key_set") if active_key_ok else t("ai_key_missing")),
        bg=Colors.BG_CARD,
        fg=Colors.TEXT_SUCCESS if active_key_ok else Colors.TEXT_ERROR,
        font=("Segoe UI", scaled_font_size(9))
    ).pack(anchor="w", padx=14, pady=(2, 0))
    if diag["chain_order"]:
        chain_labels = []
        for pid in diag["chain_order"]:
            entry = next((p for p in diag["providers"] if p["id"] == pid), None)
            chain_labels.append(entry["label"] if entry else pid)
        chain_text = " → ".join(chain_labels)
    else:
        chain_text = t("ai_fallback_empty")
    tk.Label(
        header, text=t("ai_fallback_order", chain_text),
        bg=Colors.BG_CARD, fg=Colors.ACCENT, font=("Segoe UI", scaled_font_size(9)),
        wraplength=520, justify="left"
    ).pack(anchor="w", padx=14, pady=(6, 10))
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
    cw = canvas.create_window((0, 0), window=scroll_inner, anchor="nw")
    scroll_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))
    def _on_mousewheel(e):
        try:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except Exception:
            pass
    win.bind("<MouseWheel>", _on_mousewheel)
    status_meta = {
        "active":   ("🟢", Colors.TEXT_SUCCESS),
        "in_chain": ("🔵", Colors.ACCENT),
        "skipped":  ("⚪", Colors.TEXT_DIM),
        "hidden":   ("🚫", Colors.TEXT_DIM),
    }
    for entry in diag["providers"]:
        icon, color = status_meta.get(entry["status"], ("•", Colors.TEXT_DIM))
        card = tk.Frame(scroll_inner, bg=Colors.BG_CARD,
                        highlightthickness=1, highlightbackground=Colors.BORDER, bd=0)
        card.pack(fill="x", padx=8, pady=3)
        top_row = tk.Frame(card, bg=Colors.BG_CARD)
        top_row.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(top_row, text=f"{icon} {entry['label']}", bg=Colors.BG_CARD,
                 fg=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(10), "bold"),
                 anchor="w").pack(side="left")
        tk.Label(top_row, text=t("ai_builtin") if entry["builtin"] else t("ai_custom"),
                 bg=Colors.BG_CARD, fg=Colors.TEXT_DIM,
                 font=("Segoe UI", scaled_font_size(8)), anchor="e").pack(side="right")
        tk.Label(card, text=entry["reason"], bg=Colors.BG_CARD, fg=color,
                 font=("Segoe UI", scaled_font_size(9)), anchor="w", justify="left",
                 wraplength=480).pack(fill="x", padx=10, pady=(0, 2))
        if entry["model"]:
            tk.Label(card, text=t("ai_model_label", entry['model']), bg=Colors.BG_CARD,
                     fg=Colors.TEXT_DIM, font=("Consolas", scaled_font_size(8)),
                     anchor="w").pack(fill="x", padx=10, pady=(0, 8))
        else:
            tk.Frame(card, bg=Colors.BG_CARD, height=4).pack()
    def on_close():
        canvas.unbind_all("<MouseWheel>")
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)
    bottom = tk.Frame(win, bg=Colors.BG_CARD, pady=8)
    bottom.pack(fill="x", side="bottom")
    create_button(bottom, "🔄 " + t("btn_update").replace("🆕 ", ""), lambda: (win.destroy(), open_ai_status_window()),
                  bg=Colors.BG_INPUT).pack(side="left", padx=(12, 6))
    create_button(bottom, t("btn_close"), win.destroy, bg=Colors.BG_ACTIVE).pack(side="left")
