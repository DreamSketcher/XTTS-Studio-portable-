from __future__ import annotations
import json
import os
import threading
import uuid
from datetime import datetime
from tkinter import filedialog, messagebox
import tkinter as tk

import engine.gui.chat_window.state as state
from engine.gui.chat_window.custom_widgets import CTK_AVAILABLE, CTkFrame, CTkLabel, CTkButton, TkFrame, TkLabel, TkButton, TkRawFrame

def _c(name: str) -> str:
    if state._colors is not None and hasattr(state._colors, name):
        return getattr(state._colors, name)
    return state._FALLBACK_COLORS.get(name, "#ffffff")

def _safe_after(delay: int, callback):
    try:
        if state._root is not None:
            return state._root.after(delay, callback)
    except Exception:
        return None
    return None

def _widget_exists(widget) -> bool:
    try:
        return widget is not None and bool(widget.winfo_exists())
    except Exception:
        return False

def _set_dark_titlebar(win):
    try:
        # Remove default Tkinter icon
        win.iconbitmap('blank_icon.ico')
        
        import ctypes
        win.update()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        bg_color = win.cget("bg")
        is_dark = 1
        if bg_color.startswith("#"):
            r = int(bg_color[1:3], 16)
            g = int(bg_color[3:5], 16)
            b = int(bg_color[5:7], 16)
            if (r*0.299 + g*0.587 + b*0.114) > 150:
                is_dark = 0
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(ctypes.c_int(is_dark)), ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass

def _get_app_parent():
    if _widget_exists(state._chat_window):
        return state._chat_window
    return state._root

def _show_window(win) -> bool:
    if not _widget_exists(win):
        return False
    try:
        win.deiconify()
    except Exception:
        pass
    try:
        win.lift()
    except Exception:
        pass
    try:
        win.focus_force()
    except Exception:
        pass
    return True

def _call_and_break(func, *args, **kwargs):
    func(*args, **kwargs)
    return "break"

def _ask_simple_text(parent, title: str, prompt: str, initial: str = "") -> str | None:
    result = {"value": None}
    dlg = tk.Toplevel(parent)
    _set_dark_titlebar(dlg)
    dlg.title(title)
    dlg.configure(bg=_c("BG_CARD"))
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()
    
    TkLabel(
        dlg, text=prompt, bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
        font=("Segoe UI", 9), wraplength=320, justify="left",
    ).pack(padx=16, pady=(16, 8), anchor="w")

    var = tk.StringVar(value=initial)
    entry = tk.Entry(
        dlg, textvariable=var, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"),
        insertbackground=_c("TEXT_MAIN"), relief="flat",
        highlightthickness=1, highlightbackground=_c("BORDER"),
        highlightcolor=_c("ACCENT"), font=("Segoe UI", 10), width=36,
    )
    entry.pack(padx=16, pady=(0, 12), ipady=5)
    entry.select_range(0, tk.END)

    btn_row = TkFrame(dlg, bg=_c("BG_CARD"))
    btn_row.pack(padx=16, pady=(0, 16), fill="x")

    def confirm(event=None):
        result["value"] = var.get().strip()
        dlg.destroy()

    def cancel(event=None):
        result["value"] = None
        dlg.destroy()

    _make_button(
        btn_row, "Отмена", cancel, bg=_c("BG_INPUT"), font_size=8, height=1, padx=8, pady=3,
    ).pack(side="right", padx=(6, 0))
    _make_button(
        btn_row, "ОК", confirm, bg=_c("BG_ACTIVE"), font_size=8, height=1, padx=8, pady=3,
    ).pack(side="right")

    entry.bind("<Return>", confirm)
    dlg.bind("<Escape>", cancel)
    dlg.protocol("WM_DELETE_WINDOW", cancel)
    entry.focus_set()
    dlg.wait_window()
    return result["value"]

def _make_button(parent, text: str, command=None, **kwargs):
    if state._create_button is not None:
        attempts = (
            lambda: state._create_button(parent, text, command, **kwargs),
            lambda: state._create_button(parent, text, command),
        )
        for attempt in attempts:
            try:
                btn = attempt()
                if btn is not None:
                    return btn
            except TypeError:
                continue
            except Exception:
                break

    bg = kwargs.get("bg", _c("BG_CARD"))
    fg = kwargs.get("fg", _c("TEXT_MAIN"))
    width = kwargs.get("width", None)
    height = kwargs.get("height", 1)
    font_size = kwargs.get("font_size", 9)
    padx = kwargs.get("padx", 10)
    pady = kwargs.get("pady", 5)

    btn = TkButton(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=_c("BG_ACTIVE"),
        activeforeground=_c("TEXT_MAIN"),
        relief="flat",
        cursor="hand2",
        font=("Segoe UI", font_size, "bold"),
        padx=padx,
        pady=pady,
        height=height,
    )
    if width is not None:
        try:
            btn.config(width=width)
        except Exception:
            pass
    return btn

def _set_button_text(button, text: str):
    if not _widget_exists(button):
        return
    try:
        button.config(text=text)
    except Exception:
        try:
            button.configure(text=text)
        except Exception:
            pass

def _set_button_state(button, state: str):
    if not _widget_exists(button):
        return
    try:
        button.config(state=state)
    except Exception:
        pass

def _is_descendant(widget, ancestor) -> bool:
    try:
        while widget is not None:
            if widget == ancestor:
                return True
            widget = widget.master
    except Exception:
        return False
    return False

def _get_widget_text(widget) -> str:
    if not _widget_exists(widget):
        return ""
    try:
        if isinstance(widget, tk.Text):
            return widget.get("1.0", "end-1c")
        if isinstance(widget, tk.Entry):
            return widget.get()
    except Exception:
        return ""
    return ""

def _select_all_widget(widget):
    if not _widget_exists(widget):
        return "break"
    try:
        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set(tk.INSERT, "1.0")
            widget.see(tk.INSERT)
            return "break"
        if isinstance(widget, tk.Entry):
            widget.selection_range(0, tk.END)
            widget.icursor(tk.END)
            return "break"
    except Exception:
        pass
    return "break"

def _paste_clipboard_into_widget(widget):
    if not _widget_exists(widget):
        return "break"
    try:
        text = (_get_app_parent() or state._root).clipboard_get()
    except Exception:
        return "break"
    try:
        if isinstance(widget, tk.Text):
            try:
                widget.delete("sel.first", "sel.last")
            except Exception:
                pass
            widget.insert(tk.INSERT, text)
        elif isinstance(widget, tk.Entry):
            try:
                widget.delete("sel.first", "sel.last")
            except Exception:
                pass
            widget.insert(tk.INSERT, text)
    except Exception:
        pass
    try:
        widget.event_generate("<<Modified>>")
    except Exception:
        pass
    return "break"

def _copy_to_clipboard(text: str):
    try:
        target = _get_app_parent() or state._root
        if target is None:
            return
        target.clipboard_clear()
        target.clipboard_append(text)
        # Note: set_chat_status needs to be defined or imported
    except Exception as e:
        print(f"Clipboard error: {e}")
