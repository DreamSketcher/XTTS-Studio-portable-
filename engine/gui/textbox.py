# -*- coding: utf-8 -*-
"""engine/gui/textbox.py — текстовое поле, плейсхолдер, подсветка чанков,
контекстное меню и горячие клавиши
(перенесено из gui.py: lock/unlock_textbox, set_textbox_content,
_update_textbox_normalized, clear_chunk_highlight, _highlight_chunk,
_highlight_chunk_by_text, PLACEHOLDER, show/hide_placeholder,
_get_textbox_content, paste_safe, copy_text, cut_text, select_all_text,
on_text_key_press, load_txt, show_text_context_menu, paste_clipboard,
drop_handler, секция RIGHT PANEL / Text card)."""
import os
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkinterdnd2 import DND_FILES

from i18n import t

from engine.logging_utils import write_log
from engine.text_tools import normalize_text
from engine.gui.colors import Colors
from engine.gui.tooltip import ToolTip
from engine.gui.widgets import create_card, create_button

# Внедряются из main_window: root, use_gpt, _textbox_updated, clean_path, show_help
root = None
use_gpt = None
_textbox_updated = None
clean_path = None
show_help = None

# Состояние (перенесено из секции STATE gui.py)
_highlight_pos = 0

# Виджеты (создаются в build_text_card)
text_card = None
text_header = None
text_box = None
gpt_checkbox = None

# ── Размер текста в окне ввода (регулируется ползунком) ──
_text_font_size = {"v": 12}          # стартовый размер (немного увеличен)
_FONT_SIZE_MIN = 9
_FONT_SIZE_MAX = 22
_font_panel = {"btn": None, "panel": None, "open": False, "scale_var": None}


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def _apply_text_font_size(size):
    """Применяет размер шрифта к окну ввода."""
    try:
        size = max(_FONT_SIZE_MIN, min(_FONT_SIZE_MAX, int(round(float(size)))))
    except Exception:
        return
    _text_font_size["v"] = size
    try:
        text_box.configure(font=("Consolas", size))
    except Exception:
        pass


def restore_text_font_size(size):
    """Восстанавливает сохранённый размер текста (вызывается из apply_settings).

    Работает и до, и после построения text_box: значение запоминается в
    _text_font_size и применяется к виджету, если он уже создан.
    """
    try:
        size = max(_FONT_SIZE_MIN, min(_FONT_SIZE_MAX, int(round(float(size)))))
    except Exception:
        return
    _text_font_size["v"] = size
    try:
        if text_box is not None:
            text_box.configure(font=("Consolas", size))
        var = _font_panel.get("scale_var")
        if var is not None:
            var.set(size)
    except Exception:
        pass


def _save_font_size_setting(_e=None):
    """Сохраняет размер текста в settings.json (при отпускании ползунка)."""
    try:
        from engine.gui import settings_ui as _settings_ui
        _settings_ui.save_settings()
    except Exception:
        pass


def _toggle_font_panel(event=None):
    """Показ/скрытие панели с ползунком размера текста."""
    if _font_panel["open"]:
        _hide_font_panel()
    else:
        _show_font_panel()


def _hide_font_panel(event=None):
    panel = _font_panel.get("panel")
    if panel is not None:
        try:
            panel.place_forget()
        except Exception:
            pass
    _font_panel["open"] = False
    btn = _font_panel.get("btn")
    if btn is not None:
        try:
            btn.configure(text="Aa")
        except Exception:
            pass


def _show_font_panel():
    panel = _font_panel.get("panel")
    if panel is None:
        return
    # раскрываем панель слева от кнопки, по центру правого края
    panel.place(relx=1.0, rely=0.5, anchor="e", x=-34)
    panel.lift()
    _font_panel["open"] = True
    btn = _font_panel.get("btn")
    if btn is not None:
        try:
            btn.configure(text="✕")
        except Exception:
            pass


def _build_font_size_control():
    """Создаёт кнопку «Aa» у правого края окна ввода (по центру) и
    раскрывающуюся по нажатию панель с вертикальным ползунком размера текста."""
    # Кнопка-переключатель — прижата к правому краю, по центру по вертикали
    btn = tk.Button(
        text_box,
        text="Aa",
        command=_toggle_font_panel,
        bg=Colors.BG_HOVER, fg=Colors.TEXT_MAIN,
        activebackground=Colors.ACCENT, activeforeground=Colors.TEXT_MAIN,
        relief="flat", bd=0, font=("Segoe UI", 9, "bold"),
        padx=6, pady=4, cursor="hand2",
    )
    btn.place(relx=1.0, rely=0.5, anchor="e", x=-6)
    ToolTip(btn, t("tip_font_size"))
    _font_panel["btn"] = btn

    # Панель с вертикальным ползунком (скрыта до нажатия)
    panel = tk.Frame(
        text_box,
        bg=Colors.BG_CARD,
        highlightthickness=1,
        highlightbackground=Colors.BORDER,
        bd=0,
    )
    scale_var = tk.IntVar(value=_text_font_size["v"])
    _font_panel["scale_var"] = scale_var

    tk.Label(panel, text="A", bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
             font=("Segoe UI", 11, "bold")).pack(pady=(6, 0))
    scale = tk.Scale(
        panel,
        variable=scale_var,
        from_=_FONT_SIZE_MAX, to=_FONT_SIZE_MIN,   # больший размер сверху
        orient="vertical", length=140, showvalue=True,
        bg=Colors.BG_CARD, fg=Colors.ACCENT,
        troughcolor=Colors.BG_INPUT,
        highlightthickness=0, sliderrelief="flat", sliderlength=18,
        font=("Consolas", 8), bd=0,
        command=_apply_text_font_size,
    )
    # сохраняем выбранный размер в settings.json при отпускании ползунка
    scale.bind("<ButtonRelease-1>", _save_font_size_setting, add="+")
    scale.pack(padx=6, pady=(0, 2))
    tk.Label(panel, text="A", bg=Colors.BG_CARD, fg=Colors.TEXT_DIM,
             font=("Segoe UI", 8)).pack(pady=(0, 6))
    _font_panel["panel"] = panel
    _font_panel["open"] = False


def lock_textbox():
    try:
        text_box.config(state="disabled")
    except Exception:
        pass
def unlock_textbox():
    try:
        text_box.config(state="normal")
    except Exception:
        pass
def set_textbox_content(content: str):
    unlock_textbox()
    text_box.delete("1.0", tk.END)
    if content:
        text_box.insert("1.0", content)
        text_box.config(fg=Colors.TEXT_MAIN)
    else:
        show_placeholder()
def _update_textbox_normalized(text: str):
    """Обновляет text_box финальным нормализованным текстом из runner."""
    try:
        unlock_textbox()
        text_box.delete("1.0", tk.END)
        text_box.insert("1.0", text)
        text_box.config(fg=Colors.TEXT_MAIN)
        lock_textbox()
        _textbox_updated.set()
    except Exception as e:
        print(f"[TextBox update error]: {e}")
def clear_chunk_highlight():
    try:
        text_box.tag_remove("chunk_highlight", "1.0", tk.END)
    except Exception:
        pass
def _highlight_chunk(start, end):
    try:
        clear_chunk_highlight()
        if start is None or end is None:
            return
        start = int(start)
        end = int(end)
        visible_text = text_box.get("1.0", "end-1c")
        text_len = len(visible_text)
        start = max(0, min(start, text_len))
        end = max(0, min(end, text_len))
        if end <= start:
            return
        start_idx = f"1.0+{start} chars"
        end_idx = f"1.0+{end} chars"
        text_box.tag_add("chunk_highlight", start_idx, end_idx)
        text_box.tag_configure("chunk_highlight",
                               background=Colors.CHUNK_BG,
                               foreground=Colors.CHUNK_FG)
        text_box.tag_raise("chunk_highlight")
        text_box.see(start_idx)
    except Exception as e:
        print(f"[Highlight error]: {e}")
def _highlight_chunk_by_text(chunk_raw: str):
    global _highlight_pos
    try:
        clear_chunk_highlight()
        content = text_box.get("1.0", "end-1c")
        if not content or content == PLACEHOLDER:
            return
        chunk = (chunk_raw or "").replace("[NO_PAUSE]", "").strip()
        if not chunk:
            return
        def _make_lookup(s: str):
            norm_chars = []
            index_map = []
            prev_space = False
            for i, ch in enumerate(s or ""):
                if ch.isspace():
                    if prev_space:
                        continue
                    norm_chars.append(" ")
                    index_map.append(i)
                    prev_space = True
                else:
                    norm_chars.append(ch.lower())
                    index_map.append(i)
                    prev_space = False
            while norm_chars and norm_chars[0] == " ":
                norm_chars.pop(0)
                index_map.pop(0)
            while norm_chars and norm_chars[-1] == " ":
                norm_chars.pop()
                index_map.pop()
            return "".join(norm_chars), index_map
        norm_content, index_map = _make_lookup(content)
        norm_chunk, _ = _make_lookup(chunk)
        if not norm_content or not norm_chunk or not index_map:
            return
        norm_search_from = 0
        found_search_pos = False
        for np, op in enumerate(index_map):
            if op >= _highlight_pos:
                norm_search_from = np
                found_search_pos = True
                break
        if not found_search_pos:
            norm_search_from = 0
        idx = norm_content.find(norm_chunk, norm_search_from)
        if idx == -1:
            idx = norm_content.find(norm_chunk)
        match_len = len(norm_chunk)
        if idx == -1:
            words = norm_chunk.split()
            for n in (10, 8, 6, 5, 4, 3, 2):
                if len(words) >= n:
                    probe = " ".join(words[:n])
                    idx = norm_content.find(probe, norm_search_from)
                    if idx == -1:
                        idx = norm_content.find(probe)
                    if idx != -1:
                        match_len = len(norm_chunk)
                        break
        if idx == -1:
            print(f"[HL] chunk not found: {repr(chunk[:80])}")
            return
        end_norm = min(idx + match_len, len(index_map))
        start_orig = index_map[idx]
        if end_norm > idx:
            end_orig = index_map[end_norm - 1] + 1
        else:
            end_orig = start_orig
        text_len = len(content)
        start_orig = max(0, min(start_orig, text_len))
        end_orig = max(start_orig, min(end_orig, text_len))
        if end_orig <= start_orig:
            return
        start_idx = f"1.0+{start_orig} chars"
        end_idx = f"1.0+{end_orig} chars"
        text_box.tag_add("chunk_highlight", start_idx, end_idx)
        text_box.tag_configure(
            "chunk_highlight",
            background=Colors.CHUNK_BG,
            foreground=Colors.CHUNK_FG
        )
        text_box.tag_raise("chunk_highlight")
        text_box.see(start_idx)
        _highlight_pos = end_orig
    except Exception as e:
        print(f"[Highlight error]: {e}")


PLACEHOLDER = t("placeholder")
def show_placeholder():
    unlock_textbox()
    if not text_box.get("1.0", "end-1c"):
        text_box.insert("1.0", PLACEHOLDER)
        text_box.config(fg=Colors.TEXT_DIM)
def hide_placeholder(event=None):
    unlock_textbox()
    if text_box.get("1.0", "end-1c") == PLACEHOLDER:
        text_box.delete("1.0", tk.END)
        text_box.config(fg=Colors.TEXT_MAIN)
def _get_textbox_content():
    return text_box.get("1.0", "end-1c").strip()
def paste_safe(event=None):
    hide_placeholder()
    try:
        text_box.insert(tk.INSERT, normalize_text(root.clipboard_get()))
        text_box.config(fg=Colors.TEXT_MAIN)
    except Exception:
        pass
    return "break"
def copy_text(event=None):
    """Копировать выделенный текст в буфер обмена"""
    try:
        if text_box.tag_ranges(tk.SEL):
            selected = text_box.get(tk.SEL_FIRST, tk.SEL_LAST)
            root.clipboard_clear()
            root.clipboard_append(selected)
    except Exception:
        pass
    return "break"
def cut_text(event=None):
    """Вырезать выделенный текст (копировать и удалить)"""
    try:
        if text_box.tag_ranges(tk.SEL):
            selected = text_box.get(tk.SEL_FIRST, tk.SEL_LAST)
            root.clipboard_clear()
            root.clipboard_append(selected)
            text_box.delete(tk.SEL_FIRST, tk.SEL_LAST)
    except Exception:
        pass
    return "break"
def select_all_text(event=None):
    """Выделить весь текст"""
    try:
        text_box.tag_add(tk.SEL, "1.0", tk.END)
        text_box.mark_set(tk.INSERT, tk.END)
        text_box.see(tk.INSERT)
    except Exception:
        pass
    return "break"
def on_text_key_press(event):
    """Обработчик горячих клавиш для любой раскладки (физические коды клавиш)"""
    if event.state & 0x4:  # Ctrl нажат
        if event.keycode == 65:  # A
            return select_all_text(event)
        elif event.keycode == 67:  # C
            return copy_text(event)
        elif event.keycode == 88:  # X
            return cut_text(event)
        elif event.keycode == 86:  # V
            return paste_safe(event)
    return None
def load_txt():
    hide_placeholder()
    path = filedialog.askopenfilename(filetypes=[("TXT", "*.txt")])
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = normalize_text(f.read())
            set_textbox_content(content)
        except Exception:
            write_log(traceback.format_exc())
            messagebox.showerror("❌", t("dlg_error_open_file"))
def show_text_context_menu(event):
    hide_placeholder()
    menu = tk.Menu(
        root, tearoff=0,
        bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
        activebackground=Colors.BG_HOVER, activeforeground=Colors.TEXT_MAIN,
        relief="flat", borderwidth=1
    )
    menu.add_command(label=t("ctx_copy"), command=lambda: (
        root.clipboard_clear(),
        root.clipboard_append(text_box.get(tk.SEL_FIRST, tk.SEL_LAST))
    ) if text_box.tag_ranges(tk.SEL) else None)
    menu.add_command(label=t("ctx_paste"), command=paste_safe)
    menu.add_command(label=t("ctx_cut"), command=lambda: (
        root.clipboard_clear(),
        root.clipboard_append(text_box.get(tk.SEL_FIRST, tk.SEL_LAST)),
        text_box.delete(tk.SEL_FIRST, tk.SEL_LAST)
    ) if text_box.tag_ranges(tk.SEL) else None)
    menu.add_separator()
    menu.add_command(label=t("ctx_select_all"), command=lambda: text_box.tag_add(tk.SEL, "1.0", tk.END))
    menu.add_command(label=t("ctx_clear"), command=lambda: (
        text_box.delete("1.0", tk.END),
        text_box.config(fg=Colors.TEXT_MAIN)
    ))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()
def paste_clipboard():
    hide_placeholder()
    try:
        text_box.insert("insert", normalize_text(root.clipboard_get()))
        text_box.config(fg=Colors.TEXT_MAIN)
    except Exception:
        messagebox.showwarning("⚠", t("dlg_clipboard_empty"))
def drop_handler(event):
    hide_placeholder()
    path = clean_path(event.data)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = normalize_text(f.read())
            set_textbox_content(content)
        except Exception:
            write_log(traceback.format_exc())
            messagebox.showerror("❌", t("dlg_error_open_file"))


def build_text_card(right_panel):
    global text_card, text_header, text_box, gpt_checkbox
    # Text — НАВЕРХ
    text_card = create_card(right_panel, "")
    text_card.pack(fill="both", expand=True, pady=(0, 10))
    text_header = tk.Frame(text_card, bg=Colors.BG_CARD)
    text_header.pack(fill="x", padx=10, pady=(7, 0))
    tk.Label(
        text_header,
        text=t("card_text"),
        bg=Colors.BG_CARD,
        fg=Colors.TEXT_MAIN,
        font=("Segoe UI", 11, "bold"),
        anchor="w"
    ).pack(side="left")
    create_button(text_header, t("btn_help"), show_help, bg=Colors.BG_INPUT).pack(side="right")
    # ── Кнопка переключения языка приложения (рядом со «Справка») ──
    from engine.gui import header_panel as _header_panel
    ui_lang_btn = create_button(text_header, "RU/EN", _header_panel.switch_ui_lang,
                                bg=Colors.BG_INPUT, width=50)
    ui_lang_btn.pack(side="right", padx=(0, 6))
    ToolTip(ui_lang_btn, "Switch UI language / Переключить язык интерфейса")
    # ── Кнопка переключения темы (символ, рядом с RU/EN) ──
    from engine.gui import theme as _theme

    def _toggle_theme():
        new_theme = "light" if _theme.get_theme() == "dark" else "dark"
        _theme.set_theme(new_theme)
        try:
            theme_btn.configure(text="☀" if new_theme == "dark" else "🌙")
        except Exception:
            pass
        # окно чата пересоздаётся динамически — применяем тему сразу
        try:
            from engine.gui import chat_window as _cw
            _cw.reapply_language()
        except Exception:
            pass
        messagebox.showinfo(
            t("theme_title"),
            "Theme changed. Restart the app to fully apply.\n"
            "Тема изменена. Перезапустите приложение для полного применения.")

    theme_btn = create_button(
        text_header,
        "☀" if _theme.get_theme() == "dark" else "🌙",
        _toggle_theme,
        bg=Colors.BG_INPUT, width=34)
    theme_btn.pack(side="right", padx=(0, 6))
    ToolTip(theme_btn, t("tip_theme"))
    text_box = tk.Text(
        text_card,
        bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN, insertbackground=Colors.TEXT_MAIN,
        relief="flat", highlightthickness=0, font=("Consolas", _text_font_size["v"]),
        padx=10, pady=10, wrap="word", undo=True
    )
    text_box.pack(fill="both", expand=True, padx=10, pady=7)
    _build_font_size_control()
    # AI edit checkbox stays inside text_box via place() — same variable, same command
    gpt_checkbox = ctk.CTkCheckBox(
        text_box,
        text=t("chk_ai_edit"),
        variable=use_gpt,
        fg_color=Colors.AI_ACCENT,
        hover_color=Colors.AI_ACCENT_HOVER,
        border_color=Colors.BORDER,
        text_color=Colors.TEXT_MAIN,
        font=("Segoe UI", 11),
    )
    gpt_checkbox.place(x=8, rely=1.0, anchor="sw", y=-8)
    ToolTip(gpt_checkbox, t("tip_ai_edit"))
    text_box.bind("<FocusIn>", hide_placeholder)
    text_box.bind("<FocusOut>", lambda e: show_placeholder())
    text_box.drop_target_register(DND_FILES)
    text_box.dnd_bind("<<Drop>>", drop_handler)
    text_box.bind("<Button-3>", show_text_context_menu)
    text_box.bind("<Key>", on_text_key_press, add="+")
    text_box.tag_configure("chunk_highlight", background=Colors.CHUNK_BG, foreground=Colors.CHUNK_FG)
    show_placeholder()
