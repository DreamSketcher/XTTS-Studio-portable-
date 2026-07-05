# -*- coding: utf-8 -*-
"""engine/gui/toolbar.py — тулбар главного окна: группы Файл / AI / Вывод /
Действия, кнопка ГЕНЕРИРОВАТЬ и её состояние
(перенесено из gui.py: секция TOOLBAR, _make_group, _tb_button,
on_gen_btn_click, update_gen_btn, update_quality_buttons, studio_click,
studio_double + создание кнопок chat_btn / ai_btn / styles_btn / studio_btn /
gen_btn)."""
import tkinter as tk

import customtkinter as ctk

from i18n import t

from engine.settings_store import load_settings
from engine.gui.colors import Colors, scaled_font_size
from engine.gui.tooltip import ToolTip
from engine.gui.widgets import (CompatCTkFrame, CompatCTkLabel,
                                CompatCTkButton, create_button)
from engine.gui import (textbox, dialogs, presets, styles_menu, ai_conductor,
                        chat_panel, word_replacer_panel, history_window,
                        output_window, generation)

# Внедряются из main_window: root, quality_var, lang_var, save_settings
root = None
quality_var = None
lang_var = None
save_settings = None

# Виджеты (создаются в build_toolbar)
toolbar_frame = None
toolbar_frame2 = None
file_grp = file_inner = None
ai_grp = ai_inner = None
output_grp = output_inner = None
action_grp = action_inner = None
chat_btn = None
ai_btn = None
lang_btn = None
dict_btn = None
styles_btn = None
studio_btn = None
gen_btn = None

# Функции, определяемые при построении тулбара (используются извне)
update_quality_buttons = None
update_gen_btn = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window."""
    globals().update(deps)


def build_toolbar(text_card):
    global toolbar_frame, toolbar_frame2
    global file_grp, file_inner, ai_grp, ai_inner
    global output_grp, output_inner, action_grp, action_inner
    global chat_btn, ai_btn, lang_btn, dict_btn, styles_btn, studio_btn, gen_btn
    global update_quality_buttons, update_gen_btn
    # Ряды тулбара пакуются side="bottom" (ряд 2 первым — он ниже), а
    # text_box перепаковывается ПОСЛЕДНИМ: при нехватке высоты pack сжимает
    # последний упакованный виджет, поэтому ужимается поле ввода, а кнопки
    # тулбара и статусбар остаются видимыми полностью.
    toolbar_frame2 = CompatCTkFrame(text_card, fg_color=Colors.BG_CARD, corner_radius=0)
    toolbar_frame2.pack(side="bottom", fill="x", padx=10, pady=(0, 7))
    toolbar_frame = CompatCTkFrame(text_card, fg_color=Colors.BG_CARD, corner_radius=0)
    toolbar_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 4))
    try:
        textbox.text_box.pack_forget()
        textbox.text_box.pack(fill="both", expand=True, padx=10, pady=7)
    except Exception:
        pass
    # Uniform icon size / padding constants
    _TB_FONT_SIZE = 11  # немного увеличенный общий размер текста тулбара
    _TB_ICON_SIZE = 18  # for CTkFont sizing
    _TB_PAD_X = 4
    _TB_GROUP_PAD = 8
    _TB_SEP_COLOR = Colors.BORDER
    # ── Helper: group container with subtle background ──
    def _make_group(parent, label_text, bg_color=Colors.GROUP_BG):
        """Create a framed group with a tiny label header."""
        grp = CompatCTkFrame(parent, fg_color=bg_color, corner_radius=8,
                             border_width=1, border_color=Colors.BORDER)
        # Group label
        CompatCTkLabel(grp, text=label_text, fg=Colors.TEXT_DIM, bg=bg_color,
                       font=ctk.CTkFont(family="Segoe UI", size=scaled_font_size(10)),
                       anchor="w").pack(fill="x", padx=6, pady=(3, 0))
        inner = CompatCTkFrame(grp, fg_color=bg_color, corner_radius=0)
        inner.pack(fill="x", padx=4, pady=(0, 4))
        return grp, inner
    # ── Helper: uniform toolbar button ──
    def _tb_button(parent, text, command, bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
                   hover=Colors.BG_HOVER, font_size=_TB_FONT_SIZE):
        btn = create_button(parent, text, command, bg=bg, fg=fg,
                            active_bg=hover, font_size=font_size)
        # FIX: авто-ширина по тексту вместо дефолтных 140px CTkButton —
        # иначе группы «Файл» + «Вывод» требуют ~1045px и последняя кнопка
        # («⭐ Высокое качество») обрезается при стартовой ширине окна.
        btn.configure(width=0)
        return btn
    # ── 1) FILE GROUP ──
    # ADAPTIVE: группы ряда 1 растягиваются на всю ширину (expand=True),
    # а кнопки внутри раскладываются через grid с весами — при широком окне
    # они делят ширину группы, при узком сжимаются пропорционально,
    # не вылезая за край окна.
    file_grp, file_inner = _make_group(toolbar_frame, t("group_file"), Colors.GROUP_FILE_BG)
    # ADAPTIVE + ALIGNED: ширина группы задаётся в _sync_left_column() как
    # доля ряда — колонка растягивается вместе с окном (как «Вывод»/«Действие»)
    # и при этом всегда одинакова у «Файл» и «AI» на любом языке.
    file_grp.pack(side="left", padx=(0, _TB_GROUP_PAD), fill="y")
    for _c in range(3):
        file_inner.grid_columnconfigure(_c, weight=1)
    _tb_button(file_inner, t("btn_load"), textbox.load_txt).grid(row=0, column=0, sticky="ew", padx=(_TB_PAD_X, _TB_PAD_X))
    _tb_button(file_inner, t("btn_paste"), textbox.paste_clipboard).grid(row=0, column=1, sticky="ew", padx=(0, _TB_PAD_X))
    _tb_button(file_inner, t("btn_clear"), lambda: [textbox.set_textbox_content("")]).grid(row=0, column=2, sticky="ew", padx=(0, _TB_PAD_X))
    # ── 2) AI GROUP (unified AI accent colour) ──
    # ADAPTIVE: как и группы ряда 1 — группа растягивается на свою долю ряда,
    # кнопки внутри делят её ширину через grid с весами.
    ai_grp, ai_inner = _make_group(toolbar_frame2, t("group_ai"), Colors.AI_GROUP_BG)
    # ADAPTIVE + ALIGNED: растягивается синхронно с группой «Файл»
    # (одинаковая ширина-доля ряда задаётся в _sync_left_column()).
    ai_grp.pack(side="left", padx=(0, _TB_GROUP_PAD), fill="y")
    for _c in range(2):
        ai_inner.grid_columnconfigure(_c, weight=1)
    # AI edit checkbox is already placed inside text_box — we just add the buttons here
    chat_btn = _tb_button(ai_inner, t("btn_ai_assistant"), chat_panel.toggle_chat_panel,
                          bg=Colors.AI_GROUP_BG, fg=Colors.AI_ACCENT,
                          hover=Colors.AI_ACCENT_HOVER)
    chat_btn.grid(row=0, column=0, sticky="ew", padx=(_TB_PAD_X, _TB_PAD_X))
    ToolTip(chat_btn, t("tip_ai_assistant"))
    # Восстанавливаем состояние кнопки из settings
    _ai_s = load_settings()
    _ai_active = _ai_s.get("ai_conductor_enabled", False)
    # AI Conductor button — in the AI group, using AI accent colour
    ai_btn = _tb_button(ai_inner, t("btn_ai_conductor"),
                        ai_conductor.open_ai_conductor_window,
                        bg=Colors.AI_GROUP_BG,
                        fg=Colors.AI_ACCENT if _ai_active else Colors.TEXT_DIM,
                        hover=Colors.AI_ACCENT_HOVER)
    ai_btn.grid(row=0, column=1, sticky="ew", padx=(0, _TB_PAD_X))
    ToolTip(ai_btn, t("tip_ai_conductor"))
    # ── 3) OUTPUT GROUP (Language, Dictionary, Styles, Quality preset) ──
    # ADAPTIVE: кнопки группы «Вывод» раскладываются через grid с весами —
    # заполняют весь остаток ряда и пропорционально сжимаются/растягиваются
    # при изменении размера окна (ничего не обрезается за краем).
    output_grp, output_inner = _make_group(toolbar_frame, t("group_output"), Colors.GROUP_OUTPUT_BG)
    output_grp.pack(side="left", padx=(0, 0), fill="both", expand=True)
    for _c in range(4):
        output_inner.grid_columnconfigure(_c, weight=1)
    lang_btn = _tb_button(output_inner, t("btn_language"), dialogs.pick_language)
    lang_btn.grid(row=0, column=0, sticky="ew", padx=(_TB_PAD_X, _TB_PAD_X))
    ToolTip(lang_btn, lambda: t("tip_language", lang_var.get()))
    dict_btn = _tb_button(output_inner, t("btn_dictionary"), word_replacer_panel.open_word_replacer)
    dict_btn.grid(row=0, column=1, sticky="ew", padx=(0, _TB_PAD_X))
    ToolTip(dict_btn, t("tip_dictionary"))
    # --- Styles button with popup menu ---
    styles_btn = _tb_button(output_inner, t("btn_styles"), styles_menu.open_styles_menu)
    styles_btn.grid(row=0, column=2, sticky="ew", padx=(0, _TB_PAD_X))
    ToolTip(styles_btn, styles_menu.STYLES_HINT)
    # Quality preset button — NEUTRAL (no longer green)
    def studio_click():
        quality_var.set("Высокое качество")
        save_settings()
    def studio_double(e):
        quality_var.set("Высокое качество")
        save_settings()
        presets.open_quality_settings("Высокое качество")
    studio_btn = CompatCTkButton(
        output_inner,
        text=t("btn_quality_default"),
        command=studio_click,
        fg_color=Colors.BG_INPUT,       # ← neutral, NOT green
        text_color=Colors.TEXT_MAIN,
        hover_color=Colors.BG_HOVER,
        border_width=0,
        corner_radius=10,
        font=ctk.CTkFont(family="Segoe UI", size=scaled_font_size(_TB_FONT_SIZE + 2), weight="normal"),
        height=28,
        width=0  # FIX: авто-ширина по тексту (см. _tb_button)
    )
    studio_btn.grid(row=0, column=3, sticky="ew", padx=(0, _TB_PAD_X))
    studio_btn.bind("<Double-Button-1>", studio_double)
    ToolTip(studio_btn, styles_menu.PRESET_HINT)
    # ── Quality button visual sync ──
    def update_quality_buttons(*args):
        q = quality_var.get()
        if q == "Высокое качество":
            # Active state for default = subtle border highlight, NOT green
            studio_btn.configure(fg_color=Colors.BG_HOVER, text_color=Colors.TEXT_MAIN)
            styles_btn.config(bg=Colors.BG_INPUT)
            styles_btn.config(text=t("btn_styles"))
        else:
            studio_btn.configure(fg_color=Colors.BG_INPUT, text_color=Colors.TEXT_DIM)
            emoji = {"Нарратив": "📖", "Динамика": "⚡", "Экспрессия": "🎭"}.get(q, "🎨")
            styles_btn.config(bg=Colors.BG_HOVER, text=f"{emoji} {q} ▾")
    quality_var.trace_add("write", update_quality_buttons)
    update_quality_buttons()
    # ── 4) ACTION GROUP (History, Audio, GENERATE) ──
    # ADAPTIVE: та же grid-схема; кнопке ГЕНЕРИРОВАТЬ отдан больший вес,
    # чтобы она, как и раньше, доминировала и занимала остаток ряда.
    action_grp, action_inner = _make_group(toolbar_frame2, t("group_action"), Colors.GROUP_ACTION_BG)
    action_grp.pack(side="right", fill="both", expand=True)
    def on_gen_btn_click():
        if generation.current_task is not None:
            generation.cancel_task()
        else:
            generation.generate()
    action_inner.grid_columnconfigure(0, weight=1)
    action_inner.grid_columnconfigure(1, weight=1)
    action_inner.grid_columnconfigure(2, weight=3)  # ГЕНЕРИРОВАТЬ — доминирует
    _tb_button(action_inner, t("btn_history"), history_window.open_history).grid(row=0, column=0, sticky="ew", padx=(_TB_PAD_X, _TB_PAD_X))
    _tb_button(action_inner, t("btn_audio"), output_window.open_outputs_folder).grid(row=0, column=1, sticky="ew", padx=(0, _TB_PAD_X))
    # GENERATE — the ONLY green accent element
    gen_btn = create_button(action_inner, t("btn_generate"), on_gen_btn_click,
                            bg=Colors.BG_ACTIVE, fg=Colors.TEXT_MAIN, height=1.5, font_size=13)
    gen_btn.grid(row=0, column=2, sticky="nsew", padx=(_TB_PAD_X, 0))
    def update_gen_btn(is_running: bool):
        try:
            if is_running:
                gen_btn.configure(
                    text=t("btn_cancel"),
                    fg_color=Colors.BG_DANGER,
                    hover_color="#c0312e"
                )
            else:
                gen_btn.configure(
                    text=t("btn_generate"),
                    fg_color=Colors.BG_ACTIVE,
                    hover_color=Colors.BG_HOVER
                )
        except Exception:
            pass

    # ── связываем созданные кнопки с модулями, которым они нужны ──
    ai_conductor.ai_btn = ai_btn            # пульс-анимация и окно кондуктора
    styles_menu.styles_btn = styles_btn     # позиционирование меню «Стили»
    from engine.gui import settings_ui as _settings_ui
    _settings_ui.ai_btn = ai_btn            # подсветка 🤖 AI из apply_settings

    # ── ALIGNED + ADAPTIVE: выравниваем левую колонку (Файл / AI) ──
    # Обе левые группы получают ОДИНАКОВУЮ ширину, которая растёт вместе
    # с окном (та же доля ряда, что была бы при expand), — колонка ровная
    # на любом языке и растягивается, как «Вывод» и «Действие».
    # Базовые (естественные) размеры запоминаются ОДИН раз — после
    # configure(width=...) winfo_reqwidth() возвращал бы уже заданную
    # ширину, и колонка переставала бы сжиматься при уменьшении окна.
    _left_base = {"l_req": None, "ratio": None, "h_file": None, "h_ai": None}

    def _sync_left_column(_e=None):
        try:
            if _left_base["l_req"] is None:
                file_grp.update_idletasks()
                l_req = max(file_grp.winfo_reqwidth(), ai_grp.winfo_reqwidth())
                r_req = max(output_grp.winfo_reqwidth(), action_grp.winfo_reqwidth())
                if l_req <= 1 or r_req <= 1:
                    return
                _left_base["l_req"] = l_req
                _left_base["ratio"] = l_req / float(l_req + r_req)
                _left_base["h_file"] = file_grp.winfo_reqheight()
                _left_base["h_ai"] = ai_grp.winfo_reqheight()
            l_req = _left_base["l_req"]
            ratio = _left_base["ratio"]
            avail = toolbar_frame.winfo_width()
            if avail <= 1:
                avail = toolbar_frame.winfo_reqwidth()
            # ширина левой колонки: её доля ряда, но не меньше естественной
            w = max(l_req, int((avail - _TB_GROUP_PAD) * ratio))
            file_grp.configure(width=w, height=_left_base["h_file"])
            ai_grp.configure(width=w, height=_left_base["h_ai"])
            file_grp.pack_propagate(False)
            ai_grp.pack_propagate(False)
        except Exception:
            pass

    _sync_left_column()
    # повторный проход после полной отрисовки + пересчёт при ресайзе окна
    text_card.after(150, _sync_left_column)
    toolbar_frame.bind("<Configure>", _sync_left_column, add="+")
