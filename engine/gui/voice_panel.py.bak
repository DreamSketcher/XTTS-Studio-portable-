# -*- coding: utf-8 -*-
"""engine/gui/voice_panel.py — карточки «Голос-референс» и «Библиотека голосов»
(перенесено из gui.py: refresh_voice_list, on_voice_select, voice_map,
секции Reference / Voice library левой панели)."""
import os
import tkinter as tk

import pygame

from i18n import t

from engine.gui.colors import Colors, scaled_font_size
from engine.gui.tooltip import ToolTip
from engine.gui.widgets import create_card, create_button, create_entry
from engine.gui.statusbar import set_status
from engine.gui.player import (pick_reference, pick_backup_reference,
                               play_reference, seek_back, seek_forward)
from engine.gui import player

# Внедряются из main_window: root, PYGAME_OK, ref_var, voice_manager
root = None
PYGAME_OK = False
ref_var = None
voice_manager = None

# Состояние (перенесено из секции STATE gui.py)
voice_map = {}

# Виджеты (создаются в build_voice_cards)
ref_card = None
ref_btn_row = None
voice_card = None
voice_header = None
_voice_label_var = None
voice_list_frame = None
voice_listbox = None
voice_btn_row = None
lib_btn = None
play_btn = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def refresh_voice_list():
    voice_manager.scan_voices()
    voice_listbox.delete(0, tk.END)
    voice_map.clear()
    for voice in voice_manager.list_voices():
        voice_map[voice.name] = voice
        voice_listbox.insert(tk.END, f"🎤 {voice.name}")
def on_voice_select(event):
    selection = voice_listbox.curselection()
    if not selection:
        return
    raw_name = voice_listbox.get(selection[0])
    voice_name = raw_name.replace("🎤 ", "").strip()
    voice = voice_map.get(voice_name) or voice_manager.get_voice(voice_name)
    if not voice:
        return
    try:
        voice_manager.set_active(voice_name)
    except Exception:
        pass
    ref_loaded = False
    normalized_file = getattr(voice, "normalized", None)
    voice_path = getattr(voice, "path", None)
    if normalized_file and voice_path:
        normalized_path = os.path.join(voice_path, normalized_file)
        if os.path.isfile(normalized_path):
            ref_var.set(normalized_path)
            ref_loaded = True
    if not ref_loaded and voice_path and os.path.isdir(voice_path):
        for f in os.listdir(voice_path):
            if f.lower().endswith((".wav", ".mp3")):
                ref_var.set(os.path.join(voice_path, f))
                ref_loaded = True
                break
    if ref_loaded:
        if PYGAME_OK and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        if PYGAME_OK:
            root.after(100, play_reference)
    set_status(t("active_voice", voice_name))


def build_voice_cards(left_panel):
    global ref_card, ref_btn_row, voice_card, voice_header, _voice_label_var
    global voice_list_frame, voice_listbox, voice_btn_row, lib_btn, play_btn
    # Reference
    ref_card = create_card(left_panel, t("card_voice_ref"))
    ref_card.pack(fill="x", pady=(0, 8))
    create_entry(ref_card, ref_var).pack(fill="x", padx=10, pady=(3, 7))
    ref_btn_row = tk.Frame(ref_card, bg=Colors.BG_CARD)
    ref_btn_row.pack(fill="x", padx=10, pady=(0, 7))
    create_button(ref_btn_row, t("btn_pick_ref"), pick_reference, bg=Colors.BG_INPUT).pack(side="left")
    tk.Label(ref_card, text=t("ref_info"),
             bg=Colors.BG_CARD, fg=Colors.TEXT_DIM, font=("Consolas", scaled_font_size(8)), justify="left", anchor="w"
             ).pack(fill="x", padx=10, pady=(3, 7))
    # Voice library
    voice_card = create_card(left_panel, "")
    voice_card.pack(fill="x", pady=(0, 8))
    voice_header = tk.Frame(voice_card, bg=Colors.BG_CARD)
    voice_header.pack(fill="x", padx=10, pady=(8, 6))
    tk.Label(
        voice_header, text=t("card_voice_lib"),
        bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
        font=("Segoe UI", scaled_font_size(9), "bold"), anchor="w"
    ).pack(side="left")
    def _voice_display_name() -> str:
        p = ref_var.get().strip()
        if not p:
            return ""
        folder = os.path.basename(os.path.dirname(p))
        name = os.path.splitext(os.path.basename(p))[0]
        return folder if name.lower() == "normalized" else name
    _voice_label_var = tk.StringVar()
    def _update_voice_label(*_):
        _voice_label_var.set(_voice_display_name())
    ref_var.trace_add("write", _update_voice_label)
    _update_voice_label()
    tk.Label(
        voice_header, textvariable=_voice_label_var,
        bg=Colors.BG_CARD, fg=Colors.TEXT_DIM,
        font=("Segoe UI", scaled_font_size(7)), anchor="e",
        width=16
    ).pack(side="right")
    tk.Frame(voice_card, bg=Colors.BORDER, height=1).pack(fill="x", padx=10, pady=(0, 4))
    voice_list_frame = tk.Frame(
        voice_card,
        bg=Colors.BORDER,
        highlightthickness=0,
        padx=1, pady=1
    )
    voice_list_frame.pack(fill="x", padx=10, pady=(0, 6))
    voice_listbox = tk.Listbox(
        voice_list_frame, height=6,
        bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
        selectbackground=Colors.ACCENT, selectforeground=Colors.TEXT_MAIN,
        relief="flat", highlightthickness=0,
        font=("Segoe UI", scaled_font_size(9)),
        activestyle="none", exportselection=False
    )
    voice_listbox.pack(fill="both")
    voice_listbox.bind("<<ListboxSelect>>", on_voice_select)
    tk.Frame(voice_card, bg=Colors.BORDER, height=1).pack(fill="x", padx=10, pady=(0, 6))
    voice_btn_row = tk.Frame(voice_card, bg=Colors.BG_CARD)
    voice_btn_row.pack(fill="x", padx=10, pady=(0, 8))
    lib_btn = create_button(voice_btn_row, "📂", pick_backup_reference,
                            bg=Colors.BG_INPUT, width=3)
    lib_btn.pack(side="left", padx=(0, 3))
    ToolTip(lib_btn, t("tip_pick_from_lib"))
    create_button(voice_btn_row, "⏪", seek_back,
                  bg=Colors.BG_INPUT, width=3).pack(side="left", padx=(0, 3))
    play_btn = create_button(voice_btn_row, "▶ ", play_reference,
                             bg=Colors.BG_ACTIVE, width=3)
    play_btn.pack(side="left", padx=(0, 3))
    create_button(voice_btn_row, "⏩", seek_forward,
                  bg=Colors.BG_INPUT, width=3).pack(side="left", padx=(0, 3))
    # Кнопка воспроизведения используется плеером референса
    player.play_btn = play_btn

    # ── Громкость (раскрывающийся попап рядом с кнопками перемотки) ──
    def _volume_icon(vol):
        return "🔇" if vol <= 0.001 else ("🔉" if vol < 0.5 else "🔊")

    vol_btn = create_button(voice_btn_row, _volume_icon(player.get_volume()),
                            None, bg=Colors.BG_INPUT, width=3)
    vol_btn.pack(side="left")

    _vol_popup = {"win": None, "click_bind": None}

    def _close_volume_popup(event=None):
        if _vol_popup["click_bind"] is not None:
            try:
                root.unbind_all("<Button-1>")
            except Exception:
                pass
            _vol_popup["click_bind"] = None
        w = _vol_popup["win"]
        if w is not None:
            try:
                w.destroy()
            except Exception:
                pass
            _vol_popup["win"] = None

    def _toggle_volume_popup():
        if _vol_popup["win"] is not None:
            _close_volume_popup()
            return
        from tkinter import ttk
        popup = tk.Toplevel(vol_btn)
        popup.overrideredirect(True)
        popup.configure(bg=Colors.BG_CARD, highlightthickness=1,
                        highlightbackground=Colors.BORDER)
        popup.attributes("-topmost", True)
        popup_w, popup_h = 44, 150
        x = vol_btn.winfo_rootx() - (popup_w - vol_btn.winfo_width()) // 2
        y = vol_btn.winfo_rooty() - popup_h - 4
        popup.geometry(f"{popup_w}x{popup_h}+{x}+{y}")
        inner = tk.Frame(popup, bg=Colors.BG_CARD)
        inner.pack(fill="both", expand=True, padx=6, pady=6)
        icon_lbl = tk.Label(inner, text=_volume_icon(player.get_volume()),
                            bg=Colors.BG_CARD, fg=Colors.TEXT_DIM,
                            font=("Segoe UI", scaled_font_size(9)))
        icon_lbl.pack(side="bottom", pady=(6, 0))
        vol_var = tk.DoubleVar(value=player.get_volume() * 100)

        def _on_change(val):
            vol = max(0.0, min(1.0, float(val) / 100.0))
            player.set_volume(vol)
            icon = _volume_icon(vol)
            icon_lbl.config(text=icon)
            vol_btn.config(text=icon)

        scale = ttk.Scale(inner, from_=100, to=0, orient="vertical",
                          variable=vol_var, command=_on_change)
        scale.pack(side="top", fill="y", expand=True)
        popup.bind("<Escape>", _close_volume_popup)
        popup.focus_force()


        def _on_global_click(event):
            try:
                wx, wy = popup.winfo_rootx(), popup.winfo_rooty()
                ww, wh = popup.winfo_width(), popup.winfo_height()
                inside_popup = wx <= event.x_root <= wx + ww and wy <= event.y_root <= wy + wh
                bx, by = vol_btn.winfo_rootx(), vol_btn.winfo_rooty()
                bw, bh = vol_btn.winfo_width(), vol_btn.winfo_height()
                inside_btn = bx <= event.x_root <= bx + bw and by <= event.y_root <= by + bh
                if not inside_popup and not inside_btn:
                    _close_volume_popup()
            except Exception:
                _close_volume_popup()

        _vol_popup["click_bind"] = root.bind_all("<Button-1>", _on_global_click, add="+")
        _vol_popup["win"] = popup

    vol_btn.config(command=_toggle_volume_popup)
    ToolTip(vol_btn, "Громкость")

