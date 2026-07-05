# -*- coding: utf-8 -*-
"""engine/gui/console.py — встроенная консоль
(перенесено из gui.py: ConsoleRedirect, console_redirect, секция CONSOLE,
toggle_console, show_context_menu, clear_console)."""
import sys
import tkinter as tk

from i18n import t

from engine.gui.colors import Colors, scaled_font_size
from engine.gui.widgets import create_card

# Внедряются из main_window: root, console_visible
root = None
console_visible = None

# Виджеты консоли (создаются в build_console_card)
console_card = None
console_header = None
toggle_btn = None
_clr_btn = None
console_inner = None
console_text = None
console_scroll = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


class ConsoleRedirect:
    def __init__(self):
        self.widget = None
        self._buffer = []
    def attach(self, widget):
        self.widget = widget
        for line in self._buffer:
            try:
                widget.after(0, self._write_to_widget, line)
            except Exception:
                pass
        self._buffer.clear()
    def _write_to_widget(self, text):
        if self.widget is None:
            return
        low = text.lower()
        if "error" in low or "ошибка" in low:
            tag = "error"
        elif "warn" in low or "warning" in low:
            tag = "warn"
        elif "done" in low or "готово" in low or "✔" in text:
            tag = "ok"
        else:
            tag = "info"
        self.widget.insert(tk.END, text, tag)
        self.widget.see(tk.END)
    def write(self, text):
        if self.widget is None:
            self._buffer.append(text)
        else:
            try:
                self.widget.after(0, self._write_to_widget, text)
            except Exception:
                pass
    def flush(self):
        pass


console_redirect = ConsoleRedirect()


def install():
    """Перенаправляет stdout/stderr во встроенную консоль (как в gui.py)."""
    sys.stdout = console_redirect
    sys.stderr = console_redirect


def toggle_console():
    if console_visible.get():
        console_inner.pack_forget()
        console_visible.set(False)
        toggle_btn.config(text=t("console_hide"))
    else:
        console_inner.pack(fill="x", padx=8, pady=(0, 7))
        console_visible.set(True)
        toggle_btn.config(text=t("console_show"))
def show_context_menu(event):
    menu = tk.Menu(
        root, tearoff=0, bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
        activebackground=Colors.BG_HOVER, activeforeground=Colors.TEXT_MAIN,
        relief="flat", borderwidth=1
    )
    menu.add_command(
        label=t("ctx_copy"),
        command=lambda: (
            root.clipboard_clear(),
            root.clipboard_append(console_text.get(tk.SEL_FIRST, tk.SEL_LAST))
        ) if console_text.tag_ranges(tk.SEL) else None
    )
    menu.add_separator()
    menu.add_command(label="🗑 " + t("ctx_clear"), command=clear_console)
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()
def clear_console():
    console_text.delete("1.0", tk.END)


def build_console_card(left_panel, queue_card):
    global console_card, console_header, toggle_btn, _clr_btn
    global console_inner, console_text, console_scroll
    console_card = create_card(left_panel, "")
    console_card.pack(fill="x", pady=(0, 8), after=queue_card)
    console_header = tk.Frame(console_card, bg=Colors.BG_CARD)
    console_header.pack(fill="x", padx=8, pady=(7, 3))
    toggle_btn = tk.Button(
        console_header, text=t("console_show"), command=toggle_console,
        bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
        activebackground=Colors.BG_HOVER, activeforeground=Colors.TEXT_MAIN,
        relief="flat", borderwidth=0, font=("Segoe UI", scaled_font_size(8)),
        cursor="hand2", padx=5, pady=1
    )
    toggle_btn.bind("<Enter>", lambda e: toggle_btn.config(bg=Colors.BG_HOVER))
    toggle_btn.bind("<Leave>", lambda e: toggle_btn.config(bg=Colors.BG_INPUT))
    toggle_btn.pack(side="left")
    _clr_btn = tk.Button(
        console_header, text="🗑", command=clear_console,
        bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
        activebackground=Colors.BG_HOVER, activeforeground=Colors.TEXT_MAIN,
        relief="flat", borderwidth=0, font=("Segoe UI", scaled_font_size(8)),
        cursor="hand2", padx=5, pady=1
    )
    _clr_btn.bind("<Enter>", lambda e: _clr_btn.config(bg=Colors.BG_HOVER))
    _clr_btn.bind("<Leave>", lambda e: _clr_btn.config(bg=Colors.BG_INPUT))
    _clr_btn.pack(side="right")
    console_inner = tk.Frame(console_card, bg=Colors.BG_CARD)
    console_inner.pack(fill="x", padx=8, pady=(0, 7))
    console_text = tk.Text(
        console_inner, height=12,
        bg=Colors.BG_DARK, fg=Colors.TEXT_MAIN,
        font=("Consolas", scaled_font_size(9)), state="normal", wrap="word", cursor="arrow",
        relief="flat", highlightthickness=1, highlightbackground=Colors.BORDER,
        padx=10, pady=10
    )
    console_text.bind("<Control-c>", lambda e: (
        root.clipboard_clear(),
        root.clipboard_append(console_text.get(tk.SEL_FIRST, tk.SEL_LAST)),
        "break"
    )[-1] if console_text.tag_ranges(tk.SEL) else "break")
    console_text.bind("<Control-C>", lambda e: (
        root.clipboard_clear(),
        root.clipboard_append(console_text.get(tk.SEL_FIRST, tk.SEL_LAST)),
        "break"
    )[-1] if console_text.tag_ranges(tk.SEL) else "break")
    console_scroll = tk.Scrollbar(console_inner, command=console_text.yview,
                                  bg=Colors.BG_INPUT, troughcolor=Colors.BG_DARK)
    console_text.configure(yscrollcommand=console_scroll.set)
    console_scroll.pack(side="right", fill="y")
    console_text.pack(fill="both", expand=True)
    console_text.tag_configure("error", foreground=Colors.TEXT_ERROR)
    console_text.tag_configure("warn", foreground=Colors.TEXT_WARNING)
    console_text.tag_configure("ok", foreground=Colors.TEXT_SUCCESS)
    console_text.tag_configure("info", foreground=Colors.TEXT_MAIN)
    console_redirect.attach(console_text)
    console_text.bind("<Button-3>", show_context_menu)
