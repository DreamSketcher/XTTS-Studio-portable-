# -*- coding: utf-8 -*-
"""
engine/gui/word_replacer_window.py — окно «Словарь произношений» для XTTS Studio

Управляет фонетическими заменами (engine.word_replacer.WordReplacer):
просмотр, добавление, редактирование и удаление правил, а также
переключатель «Словарь активен».

Архитектура:
    init(root, colors, create_button_fn, word_replacer_enabled_var, save_settings_fn)

Окно не импортирует ничего из gui.py напрямую — все зависимости
приходят через init().

Изменения раскладки (функциональность не тронута):
  • окно теперь resizable (min 560x420) — список правил растягивается;
  • нижние ряды упакованы side="bottom", поэтому при уменьшении окна
    ужимается список, а кнопки и чекбокс всегда видны;
  • кнопки — авто-ширина по тексту (width=0), чекбокс «Словарь активен»
    вынесен в отдельный ряд и больше не выталкивается кнопками.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except Exception:
    CTK_AVAILABLE = False
    ctk = None

# ─────────────────────────────────────────────────────────────────────────────
# Dependency injection
# ─────────────────────────────────────────────────────────────────────────────

_root = None
_colors = None
_create_button = None
_word_replacer_enabled_var = None
_save_settings = None


def init(root, colors, create_button_fn, word_replacer_enabled_var, save_settings_fn):
    global _root, _colors, _create_button, _word_replacer_enabled_var, _save_settings
    _root = root
    _colors = colors
    _create_button = create_button_fn
    _word_replacer_enabled_var = word_replacer_enabled_var
    _save_settings = save_settings_fn


# ─────────────────────────────────────────────────────────────────────────────
# ToolTip (лёгкая копия из gui.py — своя, чтобы не тянуть прямой импорт)
# ─────────────────────────────────────────────────────────────────────────────

class _ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, event=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 15
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip,
            text=self.text() if callable(self.text) else self.text,
            bg=_colors.TOOLTIP_BG,
            fg=_colors.TEXT_MAIN,
            justify="left",
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=7,
            font=("Segoe UI", 9),
            wraplength=280
        ).pack()

    def hide(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ─────────────────────────────────────────────────────────────────────────────
# Window
# ─────────────────────────────────────────────────────────────────────────────

def open_word_replacer():
    """Открывает окно словаря произношений (фонетических замен)."""
    from engine.tts_runner import word_replacer
    colors = _colors

    win = tk.Toplevel(_root)
    win.title("📖 Словарь произношений")
    win.geometry("580x560")
    # ── Изменение размера включено; ниже минимума кнопки не помещаются ──
    win.minsize(560, 480)
    win.resizable(True, True)
    win.configure(bg=colors.BG_CARD)
    win.grab_set()

    # ── Нижние ряды пакуются side="bottom" ПЕРВЫМИ: при нехватке высоты
    #    pack ужимает список, а кнопки/чекбокс остаются видимыми ──
    toggle_frame_wr = tk.Frame(win, bg=colors.BG_CARD)
    toggle_frame_wr.pack(side="bottom", fill="x", padx=15, pady=(0, 10))

    btn_frame_wr = tk.Frame(win, bg=colors.BG_CARD)
    btn_frame_wr.pack(side="bottom", fill="x", padx=15, pady=(0, 6))

    btn_row_top = tk.Frame(btn_frame_wr, bg=colors.BG_CARD)
    btn_row_top.pack(side="top", fill="x", pady=(0, 4))

    btn_row_bottom = tk.Frame(btn_frame_wr, bg=colors.BG_CARD)
    btn_row_bottom.pack(side="top", fill="x")

    meta_frame = tk.Frame(win, bg=colors.BG_CARD)
    meta_frame.pack(side="bottom", fill="x", padx=15, pady=(0, 2))

    input_frame = tk.Frame(win, bg=colors.BG_CARD)
    input_frame.pack(side="bottom", fill="x", padx=15, pady=(6, 6))

    list_frame = tk.Frame(win, bg=colors.BG_CARD)
    list_frame.pack(fill="both", expand=True, padx=15, pady=(10, 4))

    scrollbar = tk.Scrollbar(list_frame, bg=colors.BG_INPUT, troughcolor=colors.BG_DARK)
    scrollbar.pack(side="right", fill="y")

    listbox = tk.Listbox(
        list_frame, yscrollcommand=scrollbar.set,
        font=("Consolas", 12), selectmode="single",
        bg=colors.BG_INPUT, fg=colors.TEXT_MAIN,
        selectbackground=colors.ACCENT, selectforeground=colors.TEXT_MAIN,
        relief="flat", highlightthickness=0
    )
    listbox.pack(fill="both", expand=True)
    scrollbar.config(command=listbox.yview)

    _selected_word = {"word": None, "category": None}

    # ── Метка с метаданными выбранного слова (added_at / context) ──
    meta_label = tk.Label(
        meta_frame, text="", bg=colors.BG_CARD, fg=colors.TEXT_DIM,
        font=("Segoe UI", 8), anchor="w", justify="left", wraplength=540
    )
    meta_label.pack(fill="x")

    def _category_tag(category: str) -> str:
        return {
            "builtin": "[встроено]",
            "auto": "[авто]",
            "ai_corrected": "[ai]",
            "custom": "[ручное]",
        }.get(category, f"[{category}]")

    def refresh():
        listbox.delete(0, tk.END)
        for category, data in word_replacer.data.items():
            if category == "meta":
                continue
            for word, value in data.items():
                text = value["text"] if isinstance(value, dict) else value
                tag = _category_tag(category)
                listbox.insert(tk.END, f"{tag} {word}  →  {text}")
        meta_label.config(text="")

    def _find_entry(word: str):
        """Возвращает (category, entry_dict) для слова, если оно есть."""
        for category, data in word_replacer.data.items():
            if category == "meta":
                continue
            if word in data:
                return category, data[word]
        return None, None

    def on_select(event=None):
        sel = listbox.curselection()
        if not sel:
            return
        item = listbox.get(sel[0])
        # формат: "[tag] слово  →  замена"
        try:
            _, rest = item.split("] ", 1)
        except ValueError:
            rest = item
        word, text = rest.split("  →  ")
        word = word.strip()
        text = text.strip()
        _selected_word["word"] = word

        category, entry = _find_entry(word)
        _selected_word["category"] = category

        entry_word.delete(0, tk.END)
        entry_word.insert(0, word)
        entry_replacement.delete(0, tk.END)
        entry_replacement.insert(0, text)

        # Показываем метаданные, если это словарная запись (не просто строка)
        if isinstance(entry, dict):
            parts = []
            if entry.get("added_at"):
                parts.append(f"Добавлено: {entry['added_at']}")
            if entry.get("occurrences"):
                parts.append(f"встреч: {entry['occurrences']}")
            if entry.get("context"):
                parts.append(f"контекст: «{entry['context']}»")
            meta_label.config(text="  •  ".join(parts) if parts else "")
        else:
            meta_label.config(text="")

    listbox.bind("<<ListboxSelect>>", on_select)
    refresh()

    tk.Label(
        input_frame, text="Слово:", bg=colors.BG_CARD, fg=colors.TEXT_MAIN,
        font=("Segoe UI", 10)
    ).grid(row=0, column=0, sticky="w", padx=(0, 10))

    entry_word = tk.Entry(
        input_frame, width=20, font=("Segoe UI", 10),
        bg=colors.BG_INPUT, fg=colors.TEXT_MAIN,
        insertbackground=colors.TEXT_MAIN, relief="flat",
        highlightthickness=1, highlightbackground=colors.BORDER
    )
    entry_word.grid(row=0, column=1, padx=5, sticky="ew")

    tk.Label(
        input_frame, text="Замена:", bg=colors.BG_CARD, fg=colors.TEXT_MAIN,
        font=("Segoe UI", 10)
    ).grid(row=0, column=2, sticky="w", padx=(10, 10))

    entry_replacement = tk.Entry(
        input_frame, width=20, font=("Segoe UI", 10),
        bg=colors.BG_INPUT, fg=colors.TEXT_MAIN,
        insertbackground=colors.TEXT_MAIN, relief="flat",
        highlightthickness=1, highlightbackground=colors.BORDER
    )
    entry_replacement.grid(row=0, column=3, padx=5, sticky="ew")
    # поля ввода растягиваются при увеличении окна
    input_frame.grid_columnconfigure(1, weight=1)
    input_frame.grid_columnconfigure(3, weight=1)

    def add_rule():
        word = entry_word.get().strip()
        replacement = entry_replacement.get().strip()
        if not word or not replacement:
            messagebox.showwarning("⚠ Поля пусты", "Заполните слово и замену", parent=win)
            return
        if word_replacer.get_category(word) is not None:
            messagebox.showwarning(
                "⚠ Слово уже есть",
                f"«{word}» уже есть в словаре.\nИспользуйте «✏ Сохранить изменения».",
                parent=win
            )
            return
        word_replacer.add_rule(word, replacement, category="custom")
        entry_word.delete(0, tk.END)
        entry_replacement.delete(0, tk.END)
        _selected_word["word"] = None
        _selected_word["category"] = None
        refresh()

    def save_changes():
        original_word = _selected_word["word"]
        if not original_word:
            messagebox.showwarning(
                "⚠ Ничего не выбрано", "Выберите слово в списке для редактирования", parent=win
            )
            return
        new_word = entry_word.get().strip()
        new_text = entry_replacement.get().strip()
        if not new_word or not new_text:
            messagebox.showwarning("⚠ Поля пусты", "Заполните слово и замену", parent=win)
            return
        if new_word != original_word:
            word_replacer.remove_rule(original_word)
        word_replacer.add_rule(new_word, new_text, category="custom")
        entry_word.delete(0, tk.END)
        entry_replacement.delete(0, tk.END)
        _selected_word["word"] = None
        _selected_word["category"] = None
        refresh()

    def remove_rule():
        sel = listbox.curselection()
        if sel:
            item = listbox.get(sel[0])
            try:
                _, rest = item.split("] ", 1)
            except ValueError:
                rest = item
            word = rest.split("  →  ")[0].strip()
            word_replacer.remove_rule(word)
            entry_word.delete(0, tk.END)
            entry_replacement.delete(0, tk.END)
            _selected_word["word"] = None
            _selected_word["category"] = None
            refresh()

    def reset_pronunciation():
        """
        Сбрасывает произношение выбранного слова: удаляет правило замены
        полностью, слово перестаёт транслитерироваться и читается моделью
        как есть (в своём исходном языке). Используется, когда слово
        произносится с акцентом/искажением из-за неверной транслитерации
        (обычно auto-записи от эвристики).
        """
        word = _selected_word["word"]
        if not word:
            messagebox.showwarning(
                "⚠ Ничего не выбрано",
                "Выберите слово в списке, произношение которого нужно сбросить",
                parent=win
            )
            return

        category = _selected_word.get("category") or word_replacer.get_category(word)
        replacement = entry_replacement.get().strip()

        confirm = messagebox.askyesno(
            "↺ Сбросить произношение",
            f"Сбросить произношение для «{word}»?\n\n"
            f"Текущая замена: «{replacement}»\n\n"
            "Слово перестанет принудительно транслитерироваться в кириллицу "
            "и будет прочитано моделью как есть, в своём исходном языке.\n\n"
            "Используйте это, если сейчас слышите акцент или искажение "
            "именно на этом слове.",
            icon="warning",
            parent=win
        )
        if not confirm:
            return

        word_replacer.remove_rule(word)
        entry_word.delete(0, tk.END)
        entry_replacement.delete(0, tk.END)
        _selected_word["word"] = None
        _selected_word["category"] = None
        refresh()

    # ── Кнопки: авто-ширина по тексту (width=0) — не выталкивают соседей ──
    def _wr_btn(parent, text, cmd, **kw):
        b = _create_button(parent, text, cmd, **kw)
        try:
            b.configure(width=0)
        except Exception:
            pass
        try:
            b.configure(padx=6, pady=2)
        except Exception:
            pass
        return b

    _wr_btn(btn_row_top, "➕ Добавить", add_rule,
            bg=colors.BG_INPUT).pack(side="left", padx=(0, 5))
    reset_btn = _wr_btn(btn_row_top, "↺ Сбросить произношение", reset_pronunciation,
                         bg=colors.BG_INPUT)
    reset_btn.pack(side="left")
    _ToolTip(
        reset_btn,
        "Удаляет правило замены для выбранного слова.\n\n"
        "Слово перестанет транслитерироваться и будет\n"
        "прочитано моделью как есть — используйте, если\n"
        "слышите акцент/искажение именно на этом слове."
    )

    _wr_btn(btn_row_bottom, "✏ Сохранить изменения", save_changes,
            bg=colors.BG_INPUT).pack(side="left", padx=(0, 5))
    _wr_btn(btn_row_bottom, "🗑 Удалить", remove_rule, bg=colors.BG_DANGER,
            fg=colors.TEXT_MAIN).pack(side="left")

    # ── Чекбокс «Словарь активен» — отдельный ряд, кнопки его не двигают ──
    wr_cb = ctk.CTkCheckBox(
        toggle_frame_wr, text="Словарь активен", variable=_word_replacer_enabled_var,
        fg_color=colors.BG_ACTIVE, hover_color=colors.BG_HOVER,
        border_color=colors.BORDER, text_color=colors.TEXT_MAIN,
        font=("Segoe UI", 10)
    )
    wr_cb.pack(side="right")
    _ToolTip(
        wr_cb,
        "Включает замену слов по словарю перед синтезом.\n\n"
        "При отключении аббревиатуры, числа и иностранные\n"
        "термины могут читаться некорректно или вызывать\n"
        "артефакты — повторы, обрывы, «каша» в речи."
    )

    def close_window():
        _save_settings()
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", close_window)