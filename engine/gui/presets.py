# -*- coding: utf-8 -*-
"""engine/gui/presets.py — пресеты качества и окно их настроек
(перенесено из gui.py: quality_params, PRESET_DESCRIPTIONS, open_quality_settings)."""
import tkinter as tk

import customtkinter as ctk

from i18n import t

from engine.gui.colors import Colors, scaled_font_size
from engine.gui.tooltip import ToolTip
from engine.gui.widgets import create_button

# Внедряются из main_window: root, use_gpt, save_settings
root = None
use_gpt = None
save_settings = None

quality_params = {}
PRESET_DESCRIPTIONS = {}


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def build_quality_params():
    """Создаёт словарь quality_params (требует созданного tk-root)."""
    global quality_params, PRESET_DESCRIPTIONS
    quality_params = {
        "Высокое качество": {
            "qc_enabled": tk.BooleanVar(value=True),
            "temperature": tk.DoubleVar(value=0.70),
            "top_p": tk.DoubleVar(value=0.30),
            "top_k": tk.IntVar(value=80),
            "repetition_penalty": tk.DoubleVar(value=13.0),
            "prosody_intensity": tk.DoubleVar(value=0.0),
            "de_esser_intensity": tk.DoubleVar(value=0.8),
            "trim_ms": tk.IntVar(value=100),
            "speed": tk.DoubleVar(value=1.0),
            "trim_mode": tk.StringVar(value="auto"),
            "export_format": tk.StringVar(value="wav"),
            "use_gpt": tk.BooleanVar(value=use_gpt.get()),
            "ai_conductor_enabled": tk.BooleanVar(value=False),
        },
        "Нарратив": {
            "qc_enabled": tk.BooleanVar(value=True),
            "temperature": tk.DoubleVar(value=0.75),
            "top_p": tk.DoubleVar(value=0.25),
            "top_k": tk.IntVar(value=85),
            "repetition_penalty": tk.DoubleVar(value=18.0),
            "prosody_intensity": tk.DoubleVar(value=0.5),
            "de_esser_intensity": tk.DoubleVar(value=0.7),
            "trim_ms": tk.IntVar(value=80),
            "speed": tk.DoubleVar(value=0.9),
            "trim_mode": tk.StringVar(value="auto"),
            "export_format": tk.StringVar(value="wav"),
            "use_gpt": tk.BooleanVar(value=use_gpt.get()),
            "ai_conductor_enabled": tk.BooleanVar(value=False),
        },
        "Динамика": {
            "qc_enabled": tk.BooleanVar(value=True),
            "temperature": tk.DoubleVar(value=0.82),
            "top_p": tk.DoubleVar(value=0.20),
            "top_k": tk.IntVar(value=100),
            "repetition_penalty": tk.DoubleVar(value=16.0),
            "prosody_intensity": tk.DoubleVar(value=1.1),
            "de_esser_intensity": tk.DoubleVar(value=1.0),
            "trim_ms": tk.IntVar(value=60),
            "speed": tk.DoubleVar(value=1.1),
            "trim_mode": tk.StringVar(value="auto"),
            "export_format": tk.StringVar(value="wav"),
            "use_gpt": tk.BooleanVar(value=use_gpt.get()),
            "ai_conductor_enabled": tk.BooleanVar(value=False),
        },
        "Экспрессия": {
            "qc_enabled": tk.BooleanVar(value=True),
            "temperature": tk.DoubleVar(value=0.88),
            "top_p": tk.DoubleVar(value=0.30),
            "top_k": tk.IntVar(value=90),
            "repetition_penalty": tk.DoubleVar(value=14.0),
            "prosody_intensity": tk.DoubleVar(value=1.3),
            "de_esser_intensity": tk.DoubleVar(value=1.3),
            "trim_ms": tk.IntVar(value=100),
            "speed": tk.DoubleVar(value=1.0),
            "trim_mode": tk.StringVar(value="auto"),
            "export_format": tk.StringVar(value="wav"),
            "use_gpt": tk.BooleanVar(value=use_gpt.get()),
            "ai_conductor_enabled": tk.BooleanVar(value=False),
        },
    }
    PRESET_DESCRIPTIONS = {
        "Нарратив": t("preset_narrative_desc"),
        "Динамика": t("preset_dynamic_desc"),
        "Экспрессия": t("preset_expressive_desc"),
    }
    return quality_params


def open_quality_settings(preset_name):
    if preset_name not in quality_params:
        preset_name = "Высокое качество"
    win = tk.Toplevel(root)
    win.title(t("win_settings_title", preset_name))
    win.resizable(False, True)
    win.configure(bg=Colors.BG_CARD)
    win.grab_set()
    params = quality_params[preset_name]
    win.update_idletasks()
    screen_h = win.winfo_screenheight()
    max_h = int(screen_h * 0.85)
    win.maxsize(600, max_h)
    fields = [
        ("temperature", t("lbl_temperature"), 0.1, 1.0, 0.05,
         "Случайность голоса.\n\nНизко — стабильно и ровно.\nВысоко — более живо, но менее предсказуемо."),
        ("top_p", t("lbl_top_p"), 0.1, 1.0, 0.05,
         "Ограничивает выбор вариантов.\n\nМеньше — стабильнее.\nБольше — естественнее."),
        ("top_k", t("lbl_top_k"), 10, 100, 5,
         "Сколько вариантов модель рассматривает.\n\nМеньше — чище.\nБольше — разнообразнее."),
        ("repetition_penalty", t("lbl_rep_penalty"), 1.0, 20.0, 0.5,
         "Убирает повторы.\n\nВыше — меньше артефактов.\nНиже — естественнее но рискованнее"),
        ("speed", t("lbl_speed"), 0.75, 2.25, 0.05,
         "Скорость озвучки.\n\nМедленно↔Быстрее"),
        ("prosody_intensity", t("lbl_prosody"), 0.0, 2.0, 0.1,
         "Выразительность речи.\n\n0 — ровно.\n1 — естественно.\n2 — очень эмоционально."),
        ("de_esser_intensity", t("lbl_deesser"), 0.0, 2.0, 0.1,
         "Подавление избыточных шипящих/свистящих звуков (С/Ш/Ц/Щ).\n\n0 — выключено.\n1 — стандартно.\n2 — агрессивно."),
        ("trim_ms", t("lbl_trim"), 0, 300, 10,
         "Обрезка хвоста аудио.\n\nУбирает шум и затухание в конце чанка."),
    ]
    trim_scale = None
    for key, label, from_, to, res, hint in fields:
        row = tk.Frame(win, bg=Colors.BG_CARD)
        row.pack(fill="x", padx=15, pady=5)
        lbl = tk.Label(row, text=label, width=20, anchor="w",
                       bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(10)))
        lbl.pack(side="left")
        ToolTip(lbl, hint)
        scale = tk.Scale(
            row, variable=params[key], from_=from_, to=to, resolution=res,
            orient="horizontal", length=240,
            bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, troughcolor=Colors.BG_INPUT,
            highlightthickness=0, sliderrelief="flat", sliderlength=20, font=("Segoe UI", scaled_font_size(9))
        )
        scale.pack(side="left", padx=(10, 5))
        tk.Label(row, textvariable=params[key], width=6,
                 bg=Colors.BG_CARD, fg=Colors.ACCENT, font=("Consolas", scaled_font_size(9))).pack(side="left")
        if key == "trim_ms":
            trim_scale = scale
    mode_row = tk.Frame(win, bg=Colors.BG_CARD)
    mode_row.pack(fill="x", padx=15, pady=5)
    trim_lbl = tk.Label(mode_row, text=t("lbl_trim_mode"), width=20, anchor="w",
                        bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(10)))
    trim_lbl.pack(side="left")
    ToolTip(trim_lbl, "Авто / Ручной / Выкл")
    tk.Radiobutton(mode_row, text=t("trim_auto"), variable=params["trim_mode"], value="auto",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_CARD,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", scaled_font_size(9))).pack(side="left", padx=5)
    tk.Radiobutton(mode_row, text=t("trim_manual"), variable=params["trim_mode"], value="manual",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_CARD,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", scaled_font_size(9))).pack(side="left", padx=5)
    tk.Radiobutton(mode_row, text=t("trim_off"), variable=params["trim_mode"], value="off",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_CARD,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", scaled_font_size(9))).pack(side="left")
    fmt_row = tk.Frame(win, bg=Colors.BG_CARD)
    fmt_row.pack(fill="x", padx=15, pady=(5, 0))
    tk.Label(fmt_row, text=t("lbl_export_format"), width=20, anchor="w",
             bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(10))).pack(side="left")
    tk.Radiobutton(fmt_row, text="WAV", variable=params["export_format"], value="wav",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_CARD,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", scaled_font_size(9))).pack(side="left", padx=5)
    tk.Radiobutton(fmt_row, text="MP3 192k", variable=params["export_format"], value="mp3",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_CARD,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", scaled_font_size(9))).pack(side="left", padx=5)
    def update_trim_state(*args):
        if trim_scale:
            try:
                if params["trim_mode"].get() == "manual":
                    trim_scale.config(state="normal", fg=Colors.TEXT_MAIN, troughcolor=Colors.BG_INPUT)
                else:
                    trim_scale.config(state="disabled", fg=Colors.TEXT_DIM, troughcolor=Colors.BG_DARK)
            except Exception:
                pass
    params["trim_mode"].trace_add("write", update_trim_state)
    update_trim_state()
    def reset():
        defaults = {
            "Высокое качество": (0.70, 0.30, 80, 13.0, 1.0, 100, "auto", 0.0, 0.8),
            "Нарратив":         (0.75, 0.25, 85, 18.0, 0.9, 80, "auto", 0.5, 0.7),
            "Динамика":         (0.82, 0.20, 100, 16.0, 1.1, 60, "auto", 1.1, 1.0),
            "Экспрессия":       (0.88, 0.30, 90, 14.0, 1.0, 100, "auto", 1.3, 1.3),
        }
        d = defaults.get(preset_name, (0.70, 0.30, 80, 13.0, 1.0, 80, "auto", 0.8, 1.0))
        params["temperature"].set(d[0])
        params["top_p"].set(d[1])
        params["top_k"].set(d[2])
        params["repetition_penalty"].set(d[3])
        params["speed"].set(d[4])
        params["trim_ms"].set(d[5])
        params["trim_mode"].set(d[6])
        params["prosody_intensity"].set(d[7])
        params["de_esser_intensity"].set(d[8])
        params["export_format"].set("wav")
    # QC чекбокс
    qc_row = tk.Frame(win, bg=Colors.BG_CARD)
    qc_row.pack(fill="x", padx=15, pady=(5, 0))
    qc_cb = ctk.CTkCheckBox(
        qc_row, text=t("chk_qc"),
        variable=params["qc_enabled"], fg_color=Colors.BG_ACTIVE, hover_color=Colors.BG_HOVER,
        border_color=Colors.BORDER, text_color=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(9))
    )
    qc_cb.pack(side="left")
    ToolTip(qc_cb, t("tip_qc"))
    btn_frame = tk.Frame(win, bg=Colors.BG_CARD)
    btn_frame.pack(fill="x", padx=15, pady=(10, 15))
    create_button(btn_frame, t("btn_reset"), reset, bg=Colors.BG_INPUT).pack(side="left", padx=(0, 10))
    create_button(btn_frame, t("btn_close"), lambda: [win.destroy(), save_settings()],
                  bg=Colors.BG_ACTIVE).pack(side="left")
