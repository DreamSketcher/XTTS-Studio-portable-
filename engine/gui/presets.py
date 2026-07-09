# -*- coding: utf-8 -*-
"""engine/gui/presets.py — пресеты качества (компактный редизайн, быстрый скролл)"""
import tkinter as tk
import os

import customtkinter as ctk

from i18n import t
from engine.paths import BASE_DIR
try:
    from engine.paths import ICON_PATH
except ImportError:
    ICON_PATH = os.path.join(str(BASE_DIR), "icon.ico")

from engine.gui.colors import Colors, scaled_font_size, scaled_size
from engine.gui.tooltip import ToolTip
from engine.gui.widgets import CompatCTkFrame, CompatCTkButton, CompatCTkLabel

root = None
use_gpt = None
save_settings = None

quality_params = {}
PRESET_DESCRIPTIONS = {}

def init(**deps):
    globals().update(deps)

def build_quality_params():
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
            "use_gpt": tk.BooleanVar(value=use_gpt.get() if use_gpt else False),
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
            "use_gpt": tk.BooleanVar(value=use_gpt.get() if use_gpt else False),
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
            "use_gpt": tk.BooleanVar(value=use_gpt.get() if use_gpt else False),
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
            "use_gpt": tk.BooleanVar(value=use_gpt.get() if use_gpt else False),
            "ai_conductor_enabled": tk.BooleanVar(value=False),
        },
    }
    PRESET_DESCRIPTIONS = {
        "Нарратив": t("preset_narrative_desc"),
        "Динамика": t("preset_dynamic_desc"),
        "Экспрессия": t("preset_expressive_desc"),
    }
    return quality_params

def _apply_window_icon(win):
    try:
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("XTTSStudio.App")
        except Exception:
            pass
    except Exception:
        pass
    ico = ICON_PATH if os.path.isfile(ICON_PATH) else os.path.join(str(BASE_DIR), "icon.ico")
    if os.path.isfile(ico):
        try:
            win.iconbitmap(default=ico)
            win.after(200, lambda: win.iconbitmap(default=ico))
        except Exception:
            pass
    try:
        png = os.path.join(str(BASE_DIR), "icon.png")
        if os.path.isfile(png):
            photo = tk.PhotoImage(file=png)
            win.iconphoto(True, photo)
            win._icon_photo_ref = photo
    except Exception:
        pass

def open_quality_settings(preset_name):
    if preset_name not in quality_params:
        preset_name = "Высокое качество"
    win = tk.Toplevel(root)
    win.title(t("win_settings_title", preset_name))
    win.geometry("640x640")
    win.minsize(560, 480)
    win.resizable(True, True)
    win.configure(bg=Colors.BG_DARK)
    _apply_window_icon(win)
    win.grab_set()

    params = quality_params[preset_name]

    def _round_btn(parent, text, cmd, primary=False, width=None):
        bg = Colors.BG_ACTIVE if primary else Colors.BG_INPUT
        hover = "#2ea043" if primary else Colors.BG_HOVER
        return CompatCTkButton(
            parent, text=text, command=cmd,
            width=width if width else scaled_size(100, min_size=90),
            height=scaled_size(28, min_size=26),
            corner_radius=12,
            fg_color=bg, text_color=Colors.TEXT_MAIN, hover_color=hover,
            font=("Segoe UI", scaled_font_size(10)),
        )

    # Header — компактнее: было 20px/16pt, стало 10px/12pt
    header = CompatCTkFrame(win, fg_color=Colors.BG_CARD, corner_radius=10,
                            border_width=1, border_color=Colors.BORDER)
    header.pack(fill="x", padx=8, pady=8)
    h_inner = tk.Frame(header, bg=Colors.BG_CARD)
    h_inner.pack(fill="x", padx=10, pady=8)
    CompatCTkLabel(h_inner, text=f"⚙ {preset_name}", fg_color=Colors.BG_CARD,
                  text_color=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(12), "bold"),
                  anchor="w").pack(side="left")
    CompatCTkLabel(h_inner, text=PRESET_DESCRIPTIONS.get(preset_name, ""), fg_color=Colors.BG_CARD,
                  text_color=Colors.TEXT_DIM, font=("Segoe UI", scaled_font_size(9)),
                  anchor="w", wraplength=280, justify="left").pack(side="left", padx=(8,0))

    # Scrollable — с ускоренным скроллом
    scroll = ctk.CTkScrollableFrame(win, fg_color=Colors.BG_DARK, corner_radius=10)
    scroll.pack(fill="both", expand=True, padx=10, pady=(0,6))

    # Быстрый скролл ТОЛЬКО для этого окна — 10 строк за тик (было 1, стало заметно быстрее)
    def _fast_scroll_up(e=None):
        try:
            scroll._parent_canvas.yview_scroll(-10, "units")
            return "break"
        except Exception:
            pass
    def _fast_scroll_down(e=None):
        try:
            scroll._parent_canvas.yview_scroll(10, "units")
            return "break"
        except Exception:
            pass
    def _fast_wheel(e):
        try:
            if hasattr(e, 'delta') and e.delta:
                steps = int(e.delta/120)
                scroll._parent_canvas.yview_scroll(-steps*10, "units")
                return "break"
        except Exception:
            pass

    try:
        # Перебиваем дефолтный бинд CTkScrollableFrame — вешаем быстрый поверх
        # и возвращаем break чтобы старый медленный не срабатывал второй раз
        scroll._parent_canvas.bind("<MouseWheel>", _fast_wheel, add=False)
        scroll._parent_canvas.bind("<Button-4>", lambda e: _fast_scroll_up(), add=False)
        scroll._parent_canvas.bind("<Button-5>", lambda e: _fast_scroll_down(), add=False)

        # На сам фрейм и окно тоже — чтобы скролл работал когда курсор над карточкой
        win.bind("<MouseWheel>", _fast_wheel, add=False)
        scroll.bind("<MouseWheel>", _fast_wheel, add=False)

        def _bind_recursive_fast(w):
            try:
                w.bind("<MouseWheel>", _fast_wheel, add=False)
                w.bind("<Button-4>", lambda e: _fast_scroll_up() or "break", add=False)
                w.bind("<Button-5>", lambda e: _fast_scroll_down() or "break", add=False)
                for child in w.winfo_children():
                    _bind_recursive_fast(child)
            except Exception:
                pass

        # Биндим после построения всех карточек
        win.after(100, lambda: _bind_recursive_fast(scroll))
        win.after(300, lambda: _bind_recursive_fast(scroll))
    except Exception:
        pass

    fields = [
        ("temperature", t("lbl_temperature"), 0.1, 1.0, 0.05, "Случайность голоса."),
        ("top_p", t("lbl_top_p"), 0.1, 1.0, 0.05, "Ограничивает выбор вариантов."),
        ("top_k", t("lbl_top_k"), 10, 100, 5, "Сколько вариантов рассматривает модель."),
        ("repetition_penalty", t("lbl_rep_penalty"), 1.0, 20.0, 0.5, "Убирает повторы."),
        ("speed", t("lbl_speed"), 0.75, 2.25, 0.05, "Скорость озвучки."),
        ("prosody_intensity", t("lbl_prosody"), 0.0, 2.0, 0.1, "Выразительность речи."),
        ("de_esser_intensity", t("lbl_deesser"), 0.0, 2.0, 0.1, "Подавление шипящих."),
        ("trim_ms", t("lbl_trim"), 0, 300, 10, "Обрезка хвоста."),
    ]

    trim_scale = None
    for key, label, from_, to, res, hint in fields:
        # еще компактнее: 8px radius, 8x5 padding, шрифты -1pt
        card = CompatCTkFrame(scroll, fg_color=Colors.BG_CARD, corner_radius=8,
                              border_width=1, border_color=Colors.BORDER)
        card.pack(fill="x", padx=1, pady=2.5)

        inner = tk.Frame(card, bg=Colors.BG_CARD)
        inner.pack(fill="x", padx=8, pady=5)

        top_row = tk.Frame(inner, bg=Colors.BG_CARD)
        top_row.pack(fill="x")

        lbl = tk.Label(top_row, text=label, width=15, anchor="w",
                       bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(10)))
        lbl.pack(side="left")
        ToolTip(lbl, hint)

        val_lbl = tk.Label(top_row, textvariable=params[key], width=5,
                 bg=Colors.BG_CARD, fg=Colors.ACCENT, font=("Consolas", scaled_font_size(9), "bold"))
        val_lbl.pack(side="right")

        scale = tk.Scale(
            inner, variable=params[key], from_=from_, to=to, resolution=res,
            orient="horizontal",
            bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, troughcolor=Colors.BG_INPUT,
            highlightthickness=0, sliderrelief="flat", sliderlength=14,
            font=("Segoe UI", scaled_font_size(8))
        )
        scale.pack(fill="x", pady=(2,0))
        if key == "trim_ms":
            trim_scale = scale

    # Trim mode — компактная
    mode_card = CompatCTkFrame(scroll, fg_color=Colors.BG_CARD, corner_radius=8,
                               border_width=1, border_color=Colors.BORDER)
    mode_card.pack(fill="x", padx=1, pady=2.5)
    mode_inner = tk.Frame(mode_card, bg=Colors.BG_CARD)
    mode_inner.pack(fill="x", padx=8, pady=5)

    tk.Label(mode_inner, text=t("lbl_trim_mode"), anchor="w",
             bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(10))).pack(anchor="w", pady=(0,2))

    mode_row = tk.Frame(mode_inner, bg=Colors.BG_CARD)
    mode_row.pack(fill="x")
    for txt_key, val in [(t("trim_auto"), "auto"), (t("trim_manual"), "manual"), (t("trim_off"), "off")]:
        tk.Radiobutton(mode_row, text=txt_key, variable=params["trim_mode"], value=val,
                       bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_INPUT,
                       activebackground=Colors.BG_CARD, font=("Segoe UI", scaled_font_size(9))).pack(side="left", padx=(0,8))

    # Export format — компактная
    fmt_card = CompatCTkFrame(scroll, fg_color=Colors.BG_CARD, corner_radius=8,
                              border_width=1, border_color=Colors.BORDER)
    fmt_card.pack(fill="x", padx=1, pady=2.5)
    fmt_inner = tk.Frame(fmt_card, bg=Colors.BG_CARD)
    fmt_inner.pack(fill="x", padx=8, pady=5)
    tk.Label(fmt_inner, text=t("lbl_export_format"), anchor="w",
             bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, font=("Segoe UI", scaled_font_size(10))).pack(anchor="w", pady=(0,2))
    fmt_row = tk.Frame(fmt_inner, bg=Colors.BG_CARD)
    fmt_row.pack(fill="x")
    tk.Radiobutton(fmt_row, text="WAV", variable=params["export_format"], value="wav",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_INPUT,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", scaled_font_size(9))).pack(side="left", padx=(0,8))
    tk.Radiobutton(fmt_row, text="MP3 192k", variable=params["export_format"], value="mp3",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_INPUT,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", scaled_font_size(9))).pack(side="left")

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
            "Нарратив": (0.75, 0.25, 85, 18.0, 0.9, 80, "auto", 0.5, 0.7),
            "Динамика": (0.82, 0.20, 100, 16.0, 1.1, 60, "auto", 1.1, 1.0),
            "Экспрессия": (0.88, 0.30, 90, 14.0, 1.0, 100, "auto", 1.3, 1.3),
        }
        d = defaults.get(preset_name, (0.70, 0.30, 80, 13.0, 1.0, 80, "auto", 0.8, 1.0))
        params["temperature"].set(d[0]); params["top_p"].set(d[1]); params["top_k"].set(d[2])
        params["repetition_penalty"].set(d[3]); params["speed"].set(d[4]); params["trim_ms"].set(d[5])
        params["trim_mode"].set(d[6]); params["prosody_intensity"].set(d[7]); params["de_esser_intensity"].set(d[8])
        params["export_format"].set("wav")

    qc_card = CompatCTkFrame(scroll, fg_color=Colors.BG_CARD, corner_radius=8,
                             border_width=1, border_color=Colors.BORDER)
    qc_card.pack(fill="x", padx=1, pady=2.5)
    qc_inner = tk.Frame(qc_card, bg=Colors.BG_CARD)
    qc_inner.pack(fill="x", padx=8, pady=5)
    qc_cb = ctk.CTkCheckBox(
        qc_inner, text=t("chk_qc"), variable=params["qc_enabled"],
        fg_color=Colors.BG_ACTIVE, hover_color=Colors.BG_HOVER,
        border_color=Colors.BORDER, text_color=Colors.TEXT_MAIN,
        font=("Segoe UI", scaled_font_size(10))
    )
    qc_cb.pack(anchor="w")
    ToolTip(qc_cb, t("tip_qc"))

    # Bottom — еще компактнее: 10px radius, 8px padding
    bottom_wrap = tk.Frame(win, bg=Colors.BG_DARK)
    bottom_wrap.pack(fill="x", side="bottom")
    bottom_card = CompatCTkFrame(bottom_wrap, fg_color=Colors.BG_CARD, corner_radius=10,
                                 border_width=1, border_color=Colors.BORDER)
    bottom_card.pack(fill="x", padx=8, pady=6)
    bottom_row = tk.Frame(bottom_card, bg=Colors.BG_CARD)
    bottom_row.pack(fill="x", padx=10, pady=6)

    _round_btn(bottom_row, t("btn_reset"), reset, width=scaled_size(90, min_size=80)).pack(side="left")
    _round_btn(bottom_row, t("btn_close"), lambda: [win.destroy(), save_settings()],
               primary=True, width=scaled_size(110, min_size=90)).pack(side="right")

    win.after(150, lambda: _apply_window_icon(win))
