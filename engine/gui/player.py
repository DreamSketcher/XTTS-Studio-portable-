# -*- coding: utf-8 -*-
"""engine/gui/player.py — прослушивание голоса-референса
(перенесено из gui.py: pick_reference, pick_backup_reference, play_reference,
_check_playback, seek_forward, seek_back + состояние current_pos/play_btn)."""
import os
from tkinter import filedialog, messagebox

import pygame

from i18n import t

from engine.paths import REF_DIR, BACKUP_DIR

# Внедряются из main_window: root, PYGAME_OK, ref_var, clean_path
root = None
PYGAME_OK = False
ref_var = None
clean_path = None

# Состояние (перенесено из секции STATE gui.py)
current_pos = 0
play_btn = None
current_volume = 0.8


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def set_volume(vol):
    """Устанавливает громкость воспроизведения референса (0.0–1.0)."""
    global current_volume
    current_volume = max(0.0, min(1.0, vol))
    if PYGAME_OK:
        try:
            pygame.mixer.music.set_volume(current_volume)
        except Exception:
            pass


def get_volume():
    return current_volume


def pick_reference():
    path = filedialog.askopenfilename(
        initialdir=REF_DIR,
        title="Выбор reference",
        filetypes=[("Audio", "*.wav *.mp3")]
    )
    if path:
        ref_var.set(path)
def pick_backup_reference():
    path = filedialog.askopenfilename(
        initialdir=BACKUP_DIR,
        title="Выбор reference из библиотеки",
        filetypes=[("Audio", "*.wav *.mp3")]
    )
    if path:
        ref_var.set(path)
def play_reference():
    global play_btn, current_pos
    if not PYGAME_OK:
        messagebox.showwarning("⚠", t("dlg_audio_unavailable"))
        return
    ref = clean_path(ref_var.get().strip())
    if not ref or not os.path.isfile(ref):
        messagebox.showwarning("⚠", t("dlg_pick_ref_first"))
        return
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        if hasattr(pygame.mixer.music, "unload"):
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
        play_btn.config(text="▶ ")
        current_pos = 0
        return
    try:
        pygame.mixer.music.load(ref)
        pygame.mixer.music.set_volume(current_volume)
        pygame.mixer.music.play(start=current_pos)
        play_btn.config(text="⏸")
        _check_playback()
    except Exception as e:
        try:
            pygame.mixer.music.play()
            play_btn.config(text="⏸")
            _check_playback()
        except Exception as e2:
            play_btn.config(text="▶ ")
            messagebox.showerror("❌", t("dlg_play_error", e2))
def _check_playback():
    global current_pos, play_btn
    if not PYGAME_OK:
        return
    try:
        if pygame.mixer.music.get_busy():
            current_pos += 0.2
            root.after(200, _check_playback)
        else:
            play_btn.config(text="▶ ")
            current_pos = 0
    except Exception:
        play_btn.config(text="▶ ")
        current_pos = 0
def seek_forward():
    global current_pos, play_btn
    if not PYGAME_OK:
        return
    ref = clean_path(ref_var.get().strip())
    if not ref or not os.path.isfile(ref):
        return
    try:
        current_pos += 5
        pygame.mixer.music.stop()
        pygame.mixer.music.load(ref)
        pygame.mixer.music.set_volume(current_volume)
        pygame.mixer.music.play(start=current_pos)
        play_btn.config(text="⏸")
        _check_playback()
    except Exception as e:
        try:
            pygame.mixer.music.play()
            play_btn.config(text="⏸")
            _check_playback()
        except Exception:
            pass
def seek_back():
    global current_pos, play_btn
    if not PYGAME_OK:
        return
    ref = clean_path(ref_var.get().strip())
    if not ref or not os.path.isfile(ref):
        return
    try:
        current_pos = max(0, current_pos - 5)
        pygame.mixer.music.stop()
        pygame.mixer.music.load(ref)
        pygame.mixer.music.set_volume(current_volume)
        pygame.mixer.music.play(start=current_pos)
        play_btn.config(text="⏸")
        _check_playback()
    except Exception as e:
        try:
            pygame.mixer.music.play()
            play_btn.config(text="⏸")
            _check_playback()
        except Exception:
            pass
