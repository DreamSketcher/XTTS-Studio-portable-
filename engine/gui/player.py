# -*- coding: utf-8 -*-
"""engine/gui/player.py — прослушивание голоса-референса
(перенесено из gui.py: pick_reference, pick_backup_reference, play_reference,
_check_playback, seek_forward, seek_back + состояние current_pos/play_btn).

PATCH: pick_backup_reference открывает library/ (normalized.wav + cache),
а НЕ reference/backup. Путь резолвится в GUI-слое, чтобы не зависеть от
устаревшего BACKUP_DIR в engine.paths.

RVC preview: play_rvc_preview()/stop_rvc_preview() используют тот же pygame
mixer без конфликта с обычным прослушиванием reference.
"""
import os
from tkinter import filedialog, messagebox

import pygame

from i18n import t

# Внедряются из main_window: root, PYGAME_OK, ref_var, clean_path
# Опционально: LIBRARY_DIR / BACKUP_DIR (если main_window уже посчитал library/)
root = None
PYGAME_OK = False
ref_var = None
clean_path = None
LIBRARY_DIR = None
BACKUP_DIR = None  # legacy-алиас; если пришёл reference/* — игнорируем

# Состояние (перенесено из секции STATE gui.py)
current_pos = 0
play_btn = None
current_volume = 0.8

# pygame.mixer.music — один общий поток. Владелец не даёт проверке обычного
# reference-плеера вмешиваться в короткий RVC-preview.
_playback_owner = None  # None | "reference" | "rvc_preview"
_rvc_preview_path = None
_rvc_preview_state_callback = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def _base_dir() -> str:
    try:
        from engine.paths import BASE_DIR

        return str(BASE_DIR)
    except Exception:
        # player.py = engine/gui/player.py → 3 уровня вверх = корень приложения
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _is_library_path(p: str | None) -> bool:
    if not p:
        return False
    norm = os.path.normpath(str(p)).replace("\\", "/").lower()
    # старые/неверные корни библиотеки
    if "/reference/backup" in norm:
        return False
    if norm.rstrip("/").endswith("/reference"):
        return False
    if "/reference/" in norm and "/library" not in norm:
        return False
    base = os.path.basename(norm.rstrip("/"))
    return base == "library" or "/library/" in norm or norm.rstrip("/").endswith("/library")


def _resolve_library_dir() -> str:
    """C:\\XTTS Studio\\library — папка голосов после нормализации.

    Приоритет:
      1) LIBRARY_DIR, внедрённый из main_window
      2) BACKUP_DIR, только если он уже указывает на library/
      3) engine.paths.LIBRARY_DIR (если есть)
      4) BASE_DIR/library
    """
    candidates = []
    if LIBRARY_DIR:
        candidates.append(str(LIBRARY_DIR))
    if BACKUP_DIR:
        candidates.append(str(BACKUP_DIR))
    try:
        from engine.paths import LIBRARY_DIR as _P_LIB

        if _P_LIB:
            candidates.append(str(_P_LIB))
    except Exception:
        pass
    try:
        from engine.paths import BACKUP_DIR as _P_BAK

        if _P_BAK:
            candidates.append(str(_P_BAK))
    except Exception:
        pass
    candidates.append(os.path.join(_base_dir(), "library"))

    for c in candidates:
        if _is_library_path(c):
            # создаём, если ещё нет — чтобы диалог не падал в «Документы»
            try:
                os.makedirs(c, exist_ok=True)
            except Exception:
                pass
            return c
    fallback = os.path.join(_base_dir(), "library")
    try:
        os.makedirs(fallback, exist_ok=True)
    except Exception:
        pass
    return fallback


def _resolve_ref_dir() -> str:
    """Папка «сырых» референсов (кнопка выбора reference). Не library."""
    try:
        from engine.paths import REF_DIR

        if REF_DIR and os.path.isdir(str(REF_DIR)):
            return str(REF_DIR)
    except Exception:
        pass
    # fallback: reference/ рядом с приложением (входящие файлы до нормализации)
    d = os.path.join(_base_dir(), "reference")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


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


def _unload_music():
    if hasattr(pygame.mixer.music, "unload"):
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass


def _reset_reference_button():
    try:
        if play_btn is not None:
            play_btn.config(text="▶ ")
    except Exception:
        pass


def _notify_rvc_preview(playing: bool):
    callback = _rvc_preview_state_callback
    if callback is not None:
        try:
            callback(bool(playing))
        except Exception:
            pass


def is_rvc_preview_playing(path: str | None = None) -> bool:
    if _playback_owner != "rvc_preview" or not PYGAME_OK:
        return False
    if path and os.path.normcase(os.path.abspath(path)) != os.path.normcase(
        os.path.abspath(_rvc_preview_path or "")
    ):
        return False
    try:
        return bool(pygame.mixer.music.get_busy())
    except Exception:
        return False


def stop_rvc_preview() -> bool:
    """Останавливает только RVC-preview и уведомляет кнопку выпадающего списка."""
    global _playback_owner, _rvc_preview_path, _rvc_preview_state_callback
    if _playback_owner != "rvc_preview":
        return False

    callback = _rvc_preview_state_callback
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    _unload_music()
    _playback_owner = None
    _rvc_preview_path = None
    _rvc_preview_state_callback = callback
    _notify_rvc_preview(False)
    _rvc_preview_state_callback = None
    return True


def play_rvc_preview(path: str, on_state_change=None) -> bool:
    """Проигрывает локальный sample через общий pygame-плеер.

    Повторный вызов для того же файла работает как toggle (▶/■). При запуске
    preview обычный reference-плеер корректно останавливается и сбрасывает UI.
    """
    global current_pos, _playback_owner, _rvc_preview_path
    global _rvc_preview_state_callback

    if not PYGAME_OK:
        raise RuntimeError("аудиоплеер pygame недоступен")
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(path or "аудиопример не найден")

    same_preview = is_rvc_preview_playing(path)
    if same_preview:
        stop_rvc_preview()
        return False

    if _playback_owner == "rvc_preview":
        stop_rvc_preview()
    else:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        _unload_music()
        current_pos = 0
        _reset_reference_button()

    _rvc_preview_path = os.path.abspath(path)
    _rvc_preview_state_callback = on_state_change
    try:
        pygame.mixer.music.load(_rvc_preview_path)
        pygame.mixer.music.set_volume(current_volume)
        pygame.mixer.music.play()
        _playback_owner = "rvc_preview"
        _notify_rvc_preview(True)
        _check_rvc_preview()
        return True
    except Exception:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        _unload_music()
        _playback_owner = None
        _rvc_preview_path = None
        _notify_rvc_preview(False)
        _rvc_preview_state_callback = None
        raise


def _check_rvc_preview():
    global _playback_owner, _rvc_preview_path, _rvc_preview_state_callback
    if _playback_owner != "rvc_preview" or not PYGAME_OK:
        return
    try:
        if pygame.mixer.music.get_busy():
            if root is not None:
                root.after(200, _check_rvc_preview)
            return
    except Exception:
        pass

    callback = _rvc_preview_state_callback
    _unload_music()
    _playback_owner = None
    _rvc_preview_path = None
    _rvc_preview_state_callback = callback
    _notify_rvc_preview(False)
    _rvc_preview_state_callback = None


def pick_reference():
    path = filedialog.askopenfilename(
        initialdir=_resolve_ref_dir(), title="Выбор reference", filetypes=[("Audio", "*.wav *.mp3")]
    )
    if path:
        ref_var.set(path)


def pick_backup_reference():
    """Выбор голоса из библиотеки: library/<name>/normalized.wav (+ cache рядом).

    Раньше initialdir=BACKUP_DIR из engine.paths → reference/backup — баг GUI-слоя.
    """
    lib = _resolve_library_dir()
    path = filedialog.askopenfilename(
        initialdir=lib,
        title="Выбор reference из библиотеки",
        filetypes=[("Audio", "*.wav *.mp3 *.flac *.ogg"), ("WAV", "*.wav"), ("All", "*.*")],
    )
    if not path:
        return
    # если выбрали любой файл в папке голоса — предпочитаем normalized.wav рядом
    folder = os.path.dirname(path)
    preferred = os.path.join(folder, "normalized.wav")
    if os.path.isfile(preferred):
        path = preferred
    ref_var.set(path)


def play_reference():
    global play_btn, current_pos, _playback_owner
    if not PYGAME_OK:
        messagebox.showwarning("⚠", t("dlg_audio_unavailable"))
        return
    ref = clean_path(ref_var.get().strip()) if clean_path else ref_var.get().strip()
    if not ref or not os.path.isfile(ref):
        messagebox.showwarning("⚠", t("dlg_pick_ref_first"))
        return

    # Если звучит RVC-preview, останавливаем его и сразу запускаем reference.
    # Повторный клик при обычном reference по-прежнему работает как Stop.
    if _playback_owner == "rvc_preview":
        stop_rvc_preview()
    elif pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        _unload_music()
        _reset_reference_button()
        current_pos = 0
        _playback_owner = None
        return
    try:
        pygame.mixer.music.load(ref)
        pygame.mixer.music.set_volume(current_volume)
        pygame.mixer.music.play(start=current_pos)
        _playback_owner = "reference"
        play_btn.config(text="⏸")
        _check_playback()
    except Exception:
        try:
            pygame.mixer.music.play()
            _playback_owner = "reference"
            play_btn.config(text="⏸")
            _check_playback()
        except Exception as e2:
            _playback_owner = None
            play_btn.config(text="▶ ")
            messagebox.showerror("❌", t("dlg_play_error", e2))


def _check_playback():
    global current_pos, play_btn, _playback_owner
    if not PYGAME_OK or _playback_owner != "reference":
        return
    try:
        if pygame.mixer.music.get_busy():
            current_pos += 0.2
            root.after(200, _check_playback)
        else:
            play_btn.config(text="▶ ")
            current_pos = 0
            _playback_owner = None
    except Exception:
        play_btn.config(text="▶ ")
        current_pos = 0
        _playback_owner = None


def seek_forward():
    global current_pos, play_btn, _playback_owner
    if not PYGAME_OK:
        return
    if _playback_owner == "rvc_preview":
        stop_rvc_preview()
    ref = clean_path(ref_var.get().strip()) if clean_path else ref_var.get().strip()
    if not ref or not os.path.isfile(ref):
        return
    try:
        current_pos += 5
        pygame.mixer.music.stop()
        pygame.mixer.music.load(ref)
        pygame.mixer.music.set_volume(current_volume)
        pygame.mixer.music.play(start=current_pos)
        _playback_owner = "reference"
        play_btn.config(text="⏸")
        _check_playback()
    except Exception:
        try:
            pygame.mixer.music.play()
            _playback_owner = "reference"
            play_btn.config(text="⏸")
            _check_playback()
        except Exception:
            pass


def seek_back():
    global current_pos, play_btn, _playback_owner
    if not PYGAME_OK:
        return
    if _playback_owner == "rvc_preview":
        stop_rvc_preview()
    ref = clean_path(ref_var.get().strip()) if clean_path else ref_var.get().strip()
    if not ref or not os.path.isfile(ref):
        return
    try:
        current_pos = max(0, current_pos - 5)
        pygame.mixer.music.stop()
        pygame.mixer.music.load(ref)
        pygame.mixer.music.set_volume(current_volume)
        pygame.mixer.music.play(start=current_pos)
        _playback_owner = "reference"
        play_btn.config(text="⏸")
        _check_playback()
    except Exception:
        try:
            pygame.mixer.music.play()
            _playback_owner = "reference"
            play_btn.config(text="⏸")
            _check_playback()
        except Exception:
            pass
