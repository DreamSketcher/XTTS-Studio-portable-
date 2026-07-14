# -*- coding: utf-8 -*-
"""engine/gui/history_window.py — окно «История»

Редизайн окна истории:
- wave-форма встроена непосредственно в каждую аудиокарточку;
- ▶/■ объединяет воспроизведение и остановку, громкость расположена рядом;
- переход по аудио выполняется кликом по wave-форме карточки;
- отдельная нижняя панель проигрывателя полностью удалена;
- для точного seek по WAV используется временный аудиосрез.
"""
import concurrent.futures
import json
import os
import tempfile
import time
import tkinter as tk
from tkinter import messagebox

import pygame
import customtkinter as ctk

try:
    import soundfile as sf
except ImportError:
    sf = None

from i18n import t

from engine.history_store import HISTORY_PATH
from engine.paths import BASE_DIR

try:
    from engine.paths import ICON_PATH
except ImportError:
    ICON_PATH = os.path.join(str(BASE_DIR), "icon.ico")

from engine.gui.colors import Colors, scaled_font_size, scaled_size
from engine.gui.textbox import set_textbox_content
from engine.gui.tooltip import ToolTip
from engine.gui.widgets import CompatCTkFrame, CompatCTkButton, CompatCTkLabel

# Внедряется из main_window: root, PYGAME_OK
root = None
PYGAME_OK = False

_WAVE_BARS = 200
_VOL_TRANSPARENT_KEY = "#ff00ff"


def _safe_t(key, fallback):
    try:
        val = t(key)
        return val if val and val != key else fallback
    except Exception:
        return fallback


def init(**deps):
    globals().update(deps)


def _compute_waveform_peaks(path, num_bars=_WAVE_BARS):
    if sf is None:
        return []
    try:
        with sf.SoundFile(path) as f:
            frames = f.frames
            if frames <= 0:
                return []
            block = max(1, frames // num_bars)
            peaks = []
            for start in range(0, frames, block):
                f.seek(start)
                data = f.read(min(block, frames - start), dtype="float32", always_2d=True)
                if data.size == 0:
                    continue
                mono = data.mean(axis=1)
                peaks.append((float(mono.min()), float(mono.max())))
                if len(peaks) >= num_bars:
                    break
            return peaks
    except Exception:
        return []


def _round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [
        x1 + r,
        y1,
        x2 - r,
        y1,
        x2,
        y1,
        x2,
        y1 + r,
        x2,
        y2 - r,
        x2,
        y2,
        x2 - r,
        y2,
        x1 + r,
        y2,
        x1,
        y2,
        x1,
        y2 - r,
        x1,
        y1 + r,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def _apply_window_icon(win: tk.Toplevel):
    """Фикс иконки в панели задач Windows (как в output_window)."""
    try:
        import ctypes

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("XTTSStudio.App")
        except Exception:
            pass
    except Exception:
        pass

    candidates = []
    if ICON_PATH:
        candidates.append(ICON_PATH)
    candidates.extend(
        [
            os.path.join(str(BASE_DIR), "icon.ico"),
            os.path.join(str(BASE_DIR), "icon.png"),
            os.path.join(str(BASE_DIR), "images", "icon.ico"),
            os.path.join(str(BASE_DIR), "images", "icon.png"),
        ]
    )
    ico_file = None
    png_file = None
    for p in candidates:
        try:
            if p and os.path.isfile(p):
                if p.lower().endswith(".ico") and ico_file is None:
                    ico_file = p
                elif p.lower().endswith(".png") and png_file is None:
                    png_file = p
        except Exception:
            continue

    if ico_file:
        try:
            win.iconbitmap(default=ico_file)
        except Exception:
            try:
                win.iconbitmap(ico_file)
            except Exception:
                pass

        def _reapply_icon():
            try:
                win.iconbitmap(default=ico_file)
            except Exception:
                try:
                    win.iconbitmap(ico_file)
                except Exception:
                    pass

        try:
            win.after(100, _reapply_icon)
            win.after(400, _reapply_icon)
            win.after(1000, _reapply_icon)
        except Exception:
            pass

    try:
        photo = None
        if png_file:
            try:
                photo = tk.PhotoImage(file=png_file)
            except Exception:
                photo = None
        if photo is None and ico_file:
            try:
                from PIL import Image, ImageTk

                im = Image.open(ico_file)
                im = im.resize((32, 32), Image.LANCZOS)
                photo = ImageTk.PhotoImage(im)
            except Exception:
                try:
                    photo = tk.PhotoImage(file=ico_file)
                except Exception:
                    photo = None
        if photo is not None:
            try:
                win.iconphoto(True, photo)
                win._icon_photo_ref = photo
            except Exception:
                pass
    except Exception:
        pass


def open_history():
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as history_file:
            history = json.load(history_file)
    except Exception:
        history = []

    win = tk.Toplevel(root)
    win.title(t("win_history_title"))
    win.geometry("860x700")
    win.minsize(700, 540)
    win.resizable(True, True)
    win.configure(bg=Colors.BG_DARK)
    _apply_window_icon(win)
    win.grab_set()

    # Плеер один на всё окно, а визуальные wave-формы находятся на карточках.
    _p = {
        "playing": False,
        "path": None,
        "pos": 0.0,
        "duration": 0.0,
        "after_id": None,
        "volume": 0.8,
        "started_at": None,
        "temp_path": None,
        "error": None,
    }
    _card_widgets = {}  # path -> list[{card, canvas, play_btn, vol_btn, duration}]
    _wave_cache = {}
    _wave_pending = set()
    _active_path = {"v": None}
    _vol_popup = {"win": None, "anchor": None, "bind_id": None}
    _empty_state = {"widget": None}
    _closing = {"v": False}
    _wave_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix="history-wave",
    )

    def _round_btn(
        parent,
        text,
        cmd,
        diameter=36,
        primary=False,
        danger=False,
        disabled=False,
    ):
        bg = Colors.BG_ACTIVE if primary else Colors.BG_INPUT
        if disabled:
            bg = Colors.BG_DARK
        if primary:
            hover = "#2ea043"
        elif danger:
            hover = Colors.BG_DANGER
        else:
            hover = Colors.BG_HOVER if not disabled else Colors.BG_DARK
        scaled_diameter = scaled_size(diameter, min_size=diameter)
        button = CompatCTkButton(
            parent,
            text=text,
            command=cmd if not disabled else None,
            width=scaled_diameter,
            height=scaled_diameter,
            corner_radius=scaled_diameter // 2,
            fg_color=bg,
            text_color=Colors.TEXT_MAIN if not disabled else Colors.TEXT_DIM,
            hover_color=hover,
            border_width=0,
            font=("Segoe UI", scaled_font_size(16 if primary else 14)),
        )
        if disabled:
            button.configure(state="disabled")
        return button

    def _fmt(seconds):
        seconds = max(0, int(seconds or 0))
        return f"{seconds // 60}:{seconds % 60:02d}"

    def _truncate(value, max_chars=44):
        value = str(value or "")
        return value if len(value) <= max_chars else value[: max_chars - 1] + "…"

    def _get_duration(path):
        try:
            if sf is None:
                return 0.0
            return float(sf.info(path).duration)
        except Exception:
            return 0.0

    def _volume_icon(volume):
        if volume <= 0.001:
            return "🔇"
        return "🔉" if volume < 0.5 else "🔊"

    def _states_for(path):
        return _card_widgets.get(path, []) if path else []

    def _safe_unload_music():
        if hasattr(pygame.mixer.music, "unload"):
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass

    def _cleanup_temp_audio():
        temp_path = _p.get("temp_path")
        _p["temp_path"] = None
        if not temp_path:
            return
        try:
            if os.path.isfile(temp_path):
                os.remove(temp_path)
        except Exception:
            pass

    def _set_card_play_state(path, playing):
        for state in _states_for(path):
            button = state.get("play_btn")
            if button is None:
                continue
            try:
                button.configure(
                    text="■" if playing else "▶",
                    fg_color=Colors.BG_ACTIVE if playing else Colors.BG_INPUT,
                    hover_color="#a3342e" if playing else Colors.BG_HOVER,
                )
            except Exception:
                pass

    def _set_active_card(path):
        previous = _active_path["v"]
        if previous and previous != path:
            for state in _states_for(previous):
                try:
                    state["card"].configure(
                        border_color=Colors.BORDER,
                        border_width=1,
                    )
                except Exception:
                    pass
        _active_path["v"] = path
        if path:
            for state in _states_for(path):
                try:
                    state["card"].configure(
                        border_color=Colors.ACCENT,
                        border_width=2,
                    )
                except Exception:
                    pass

    def _clear_active_card(path=None):
        target = path or _active_path["v"]
        if target:
            for state in _states_for(target):
                try:
                    state["card"].configure(
                        border_color=Colors.BORDER,
                        border_width=1,
                    )
                except Exception:
                    pass
        if not path or _active_path["v"] == path:
            _active_path["v"] = None

    def _redraw_card_wave(path):
        for state in list(_states_for(path)):
            canvas = state.get("canvas")
            if canvas is None:
                continue
            try:
                if not canvas.winfo_exists():
                    continue
                canvas.delete("all")
                width = max(1, canvas.winfo_width())
                height = max(1, canvas.winfo_height())
                duration = float(state.get("duration") or 0.0)
                active = _p["path"] == path
                position = _p["pos"] if active else 0.0
                fraction = 0.0
                if duration > 0:
                    fraction = min(1.0, max(0.0, position / duration))
                played_x = fraction * width

                header_h = scaled_size(17, min_size=15)
                body_top = header_h + 2
                body_h = max(10, height - body_top - 3)
                middle = body_top + body_h / 2
                peaks = state.get("peaks") or _wave_cache.get(path, [])

                if not state.get("audio_exists"):
                    canvas.create_line(
                        0,
                        middle,
                        width,
                        middle,
                        fill=Colors.BORDER,
                        dash=(3, 3),
                    )
                    canvas.create_text(
                        4,
                        header_h / 2,
                        text=_safe_t("tip_audio_missing", "Аудиофайл удалён"),
                        anchor="w",
                        fill=Colors.TEXT_ERROR,
                        font=("Segoe UI", scaled_font_size(8)),
                    )
                    continue

                if not peaks:
                    canvas.create_line(
                        0,
                        middle,
                        width,
                        middle,
                        fill=Colors.BORDER,
                    )
                    loading_text = (
                        _safe_t("history_wave_unavailable", "Wave недоступна")
                        if state.get("wave_ready")
                        else _safe_t("history_wave_loading", "Загрузка wave…")
                    )
                    canvas.create_text(
                        4,
                        header_h / 2,
                        text=loading_text,
                        anchor="w",
                        fill=Colors.TEXT_DIM,
                        font=("Segoe UI", scaled_font_size(8)),
                    )
                else:
                    max_peak = max(
                        max(abs(float(minimum)), abs(float(maximum))) for minimum, maximum in peaks
                    )
                    max_peak = max(max_peak, 0.04)
                    scale = (body_h / 2 - 2) / max_peak
                    count = len(peaks)
                    bar_width = width / max(count, 1)
                    for index, (minimum, maximum) in enumerate(peaks):
                        x0 = index * bar_width
                        x1 = x0 + max(1.0, bar_width - 1)
                        y0 = middle - float(maximum) * scale
                        y1 = middle - float(minimum) * scale
                        if y1 - y0 < 1.5:
                            y0 -= 0.75
                            y1 += 0.75
                        color = Colors.ACCENT if active and x0 <= played_x else Colors.BORDER
                        canvas.create_rectangle(
                            x0,
                            y0,
                            x1,
                            y1,
                            fill=color,
                            outline="",
                        )

                if active:
                    canvas.create_line(
                        played_x,
                        body_top - 1,
                        played_x,
                        height,
                        fill=Colors.TEXT_MAIN,
                        width=1,
                    )

                if _p.get("error") and active:
                    left_text = _truncate(_p["error"], 58)
                    left_color = Colors.TEXT_ERROR
                else:
                    left_text = _safe_t(
                        "history_wave_seek_hint",
                        "Нажмите на волну для перемотки",
                    )
                    left_color = Colors.TEXT_DIM
                canvas.create_text(
                    4,
                    header_h / 2,
                    text=left_text,
                    anchor="w",
                    fill=left_color,
                    font=("Segoe UI", scaled_font_size(8)),
                )
                canvas.create_text(
                    width - 4,
                    header_h / 2,
                    text=f"{_fmt(position)} / {_fmt(duration)}",
                    anchor="e",
                    fill=Colors.TEXT_DIM,
                    font=("Consolas", scaled_font_size(8)),
                )
            except Exception:
                pass

    def _load_waveform_async(path):
        if not path or path in _wave_pending:
            return
        if path in _wave_cache:
            for state in _states_for(path):
                state["peaks"] = _wave_cache[path]
                state["wave_ready"] = True
            _redraw_card_wave(path)
            return

        _wave_pending.add(path)

        def worker():
            return _compute_waveform_peaks(path)

        future = _wave_executor.submit(worker)

        def done_callback(done_future):
            try:
                peaks = done_future.result()
            except Exception:
                peaks = []

            def apply():
                _wave_pending.discard(path)
                if _closing["v"]:
                    return
                _wave_cache[path] = peaks
                for state in _states_for(path):
                    state["peaks"] = peaks
                    state["wave_ready"] = True
                _redraw_card_wave(path)

            try:
                win.after(0, apply)
            except Exception:
                pass

        future.add_done_callback(done_callback)

    def _stop_ticker():
        after_id = _p.get("after_id")
        if after_id:
            try:
                win.after_cancel(after_id)
            except Exception:
                pass
            _p["after_id"] = None

    def _stop_playback(reset_position=True):
        previous = _p.get("path")
        _stop_ticker()
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        _safe_unload_music()
        _cleanup_temp_audio()
        _p.update(
            playing=False,
            path=None,
            pos=0.0 if reset_position else _p.get("pos", 0.0),
            duration=0.0,
            started_at=None,
            error=None,
        )
        if previous:
            _set_card_play_state(previous, False)
            _clear_active_card(previous)
            _redraw_card_wave(previous)

    def _make_seek_temp(path, from_pos):
        if sf is None or from_pos <= 0.01:
            return None
        temp_handle = tempfile.NamedTemporaryFile(
            prefix="xtts_history_seek_",
            suffix=".wav",
            delete=False,
        )
        temp_path = temp_handle.name
        temp_handle.close()
        try:
            with sf.SoundFile(path, "r") as source:
                start_frame = min(
                    source.frames,
                    max(0, int(float(from_pos) * source.samplerate)),
                )
                source.seek(start_frame)
                with sf.SoundFile(
                    temp_path,
                    "w",
                    samplerate=source.samplerate,
                    channels=source.channels,
                    format="WAV",
                    subtype="PCM_16",
                ) as target:
                    while True:
                        data = source.read(65536, dtype="float32", always_2d=True)
                        if data.size == 0:
                            break
                        target.write(data)
            if os.path.getsize(temp_path) > 44:
                return temp_path
        except Exception:
            pass
        try:
            os.remove(temp_path)
        except Exception:
            pass
        return None

    def _tick():
        if not PYGAME_OK or not _p["playing"] or not _p["path"]:
            return
        try:
            if pygame.mixer.music.get_busy():
                if _p.get("started_at") is not None:
                    current = time.monotonic() - _p["started_at"]
                    if _p["duration"] > 0:
                        current = min(current, _p["duration"])
                    _p["pos"] = max(0.0, current)
                _redraw_card_wave(_p["path"])
                _p["after_id"] = win.after(100, _tick)
            else:
                _p["after_id"] = None
                _stop_playback(reset_position=True)
        except Exception as error:
            _p["error"] = str(error)
            if _p["path"]:
                _redraw_card_wave(_p["path"])

    def _load_play(path, from_pos=0.0):
        if not PYGAME_OK:
            messagebox.showwarning("⚠", t("dlg_audio_unavailable"), parent=win)
            return
        if not path or not os.path.isfile(path):
            messagebox.showwarning(
                "⚠",
                _safe_t("tip_audio_missing", "Аудиофайл удалён"),
                parent=win,
            )
            return

        # Останавливаем RVC-preview через общий player.py, чтобы его кнопка
        # также вернулась из ■ в ▶.
        try:
            from engine.gui import player as shared_player

            shared_player.stop_rvc_preview()
        except Exception:
            pass

        previous = _p.get("path")
        _stop_ticker()
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        _safe_unload_music()
        _cleanup_temp_audio()
        if previous:
            _set_card_play_state(previous, False)
            if previous != path:
                _clear_active_card(previous)
            _redraw_card_wave(previous)

        duration = _get_duration(path)
        if duration > 0:
            from_pos = min(max(0.0, float(from_pos)), max(0.0, duration - 0.02))
        else:
            from_pos = max(0.0, float(from_pos))

        play_path = path
        temp_path = None
        try:
            # Для WAV play(start=) зависит от SDL_mixer и часто игнорирует seek.
            # В таком случае проигрываем временный WAV-срез с нужной позиции.
            if from_pos > 0.01 and os.path.splitext(path)[1].lower() == ".wav":
                temp_path = _make_seek_temp(path, from_pos)
                if temp_path:
                    play_path = temp_path

            pygame.mixer.music.load(play_path)
            pygame.mixer.music.set_volume(_p["volume"])
            if temp_path or from_pos <= 0.01:
                pygame.mixer.music.play()
            else:
                try:
                    pygame.mixer.music.play(start=from_pos)
                except Exception:
                    pygame.mixer.music.play()
                    try:
                        pygame.mixer.music.set_pos(from_pos)
                    except Exception:
                        from_pos = 0.0

            _p.update(
                playing=True,
                path=path,
                pos=from_pos,
                duration=duration,
                started_at=time.monotonic() - from_pos,
                temp_path=temp_path,
                error=None,
            )
            _set_active_card(path)
            _set_card_play_state(path, True)
            _redraw_card_wave(path)
            _tick()
        except Exception as error:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            _safe_unload_music()
            if temp_path:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            _p.update(
                playing=False,
                path=path,
                pos=0.0,
                duration=duration,
                started_at=None,
                temp_path=None,
                error=str(error),
            )
            _set_card_play_state(path, False)
            _set_active_card(path)
            _redraw_card_wave(path)

    def _toggle_card_play(path):
        if _p["playing"] and _p["path"] == path:
            _stop_playback(reset_position=True)
        else:
            _load_play(path, 0.0)

    def _wave_seek(path, event):
        states = _states_for(path)
        if not states or not os.path.isfile(path):
            return
        canvas = event.widget
        width = max(1, canvas.winfo_width())
        duration = float(states[0].get("duration") or _get_duration(path))
        if duration <= 0:
            return
        fraction = min(1.0, max(0.0, float(event.x) / width))
        _load_play(path, fraction * duration)

    def on_volume_change(volume):
        volume = max(0.0, min(1.0, float(volume)))
        _p["volume"] = volume
        if PYGAME_OK:
            try:
                pygame.mixer.music.set_volume(volume)
            except Exception:
                pass
        icon = _volume_icon(volume)
        for states in _card_widgets.values():
            for state in states:
                button = state.get("vol_btn")
                if button is not None:
                    try:
                        button.configure(text=icon)
                    except Exception:
                        pass

    def _close_volume_popup(event=None):
        popup = _vol_popup.get("win")
        bind_id = _vol_popup.get("bind_id")
        if bind_id:
            try:
                win.unbind("<Button-1>", bind_id)
            except Exception:
                pass
        _vol_popup.update(win=None, anchor=None, bind_id=None)
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass

    def _toggle_volume_popup(anchor_button):
        if _vol_popup["win"] is not None:
            same_anchor = _vol_popup.get("anchor") == anchor_button
            _close_volume_popup()
            if same_anchor:
                return

        popup_width, popup_height = 56, 168
        popup = tk.Toplevel(win)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        try:
            popup.configure(bg=_VOL_TRANSPARENT_KEY)
            popup.attributes("-transparentcolor", _VOL_TRANSPARENT_KEY)
            canvas_bg = _VOL_TRANSPARENT_KEY
        except Exception:
            popup.configure(bg=Colors.BG_DARK)
            canvas_bg = Colors.BG_DARK

        x = anchor_button.winfo_rootx() - (popup_width - anchor_button.winfo_width()) // 2
        y = anchor_button.winfo_rooty() - popup_height - 8
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        popup_canvas = tk.Canvas(
            popup,
            width=popup_width,
            height=popup_height,
            bg=canvas_bg,
            highlightthickness=0,
            bd=0,
        )
        popup_canvas.pack(fill="both", expand=True)

        track_top, track_bottom = 16, popup_height - 40
        track_height = track_bottom - track_top
        center_x = popup_width / 2

        def redraw_slider():
            popup_canvas.delete("all")
            _round_rect(
                popup_canvas,
                2,
                2,
                popup_width - 2,
                popup_height - 2,
                18,
                fill=Colors.BG_CARD,
                outline=Colors.BORDER,
            )
            _round_rect(
                popup_canvas,
                center_x - 3,
                track_top,
                center_x + 3,
                track_bottom,
                3,
                fill=Colors.BG_INPUT,
                outline="",
            )
            fill_top = track_top + track_height * (1 - _p["volume"])
            if track_bottom - fill_top > 1:
                _round_rect(
                    popup_canvas,
                    center_x - 3,
                    fill_top,
                    center_x + 3,
                    track_bottom,
                    3,
                    fill=Colors.ACCENT,
                    outline="",
                )
            thumb_y = track_top + track_height * (1 - _p["volume"])
            popup_canvas.create_oval(
                center_x - 7,
                thumb_y - 7,
                center_x + 7,
                thumb_y + 7,
                fill=Colors.TEXT_MAIN,
                outline="",
            )
            popup_canvas.create_text(
                center_x,
                popup_height - 18,
                text=_volume_icon(_p["volume"]),
                font=("Segoe UI", scaled_font_size(14)),
                fill=Colors.TEXT_DIM,
            )

        def on_slider_drag(event):
            fraction = 1 - min(
                1.0,
                max(0.0, (event.y - track_top) / track_height),
            )
            on_volume_change(fraction)
            redraw_slider()

        popup_canvas.bind("<Button-1>", on_slider_drag)
        popup_canvas.bind("<B1-Motion>", on_slider_drag)
        popup.bind("<Escape>", _close_volume_popup)
        redraw_slider()
        popup.focus_force()

        def on_window_click(event):
            try:
                px, py = popup.winfo_rootx(), popup.winfo_rooty()
                pw, ph = popup.winfo_width(), popup.winfo_height()
                inside_popup = px <= event.x_root <= px + pw and py <= event.y_root <= py + ph
                bx, by = anchor_button.winfo_rootx(), anchor_button.winfo_rooty()
                bw, bh = anchor_button.winfo_width(), anchor_button.winfo_height()
                inside_button = bx <= event.x_root <= bx + bw and by <= event.y_root <= by + bh
                if not inside_popup and not inside_button:
                    _close_volume_popup()
            except Exception:
                _close_volume_popup()

        bind_id = win.bind("<Button-1>", on_window_click, add="+")
        _vol_popup.update(win=popup, anchor=anchor_button, bind_id=bind_id)

    def clear_history():
        if not messagebox.askyesno(
            t("ctx_clear"),
            t("dlg_clear_history"),
            parent=win,
        ):
            return
        _stop_playback(reset_position=True)
        try:
            os.remove(HISTORY_PATH)
        except Exception:
            pass
        for widget in list(list_frame.winfo_children()):
            try:
                widget.destroy()
            except Exception:
                pass
        _card_widgets.clear()
        _wave_cache.clear()
        _active_path["v"] = None
        count_lbl.configure(text=t("entries_count", 0))
        _maybe_show_empty_state()

    def _maybe_show_empty_state():
        if list_frame.winfo_children():
            if _empty_state["widget"] is not None:
                try:
                    _empty_state["widget"].destroy()
                except Exception:
                    pass
                _empty_state["widget"] = None
            return
        if _empty_state["widget"] is None:
            label = CompatCTkLabel(
                list_frame,
                text=t("history_empty"),
                fg_color=Colors.BG_DARK,
                text_color=Colors.TEXT_DIM,
                font=("Segoe UI", scaled_font_size(13)),
            )
            label.pack(pady=50)
            _empty_state["widget"] = label

    def _make_card(parent, entry):
        output_path = str(entry.get("output", "") or "")
        audio_exists = bool(output_path) and os.path.isfile(output_path)

        card = CompatCTkFrame(
            parent,
            fg_color=Colors.BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=Colors.BORDER,
        )
        card.pack(fill="x", padx=4, pady=5)

        top_row = tk.Frame(card, bg=Colors.BG_CARD)
        top_row.pack(fill="x", padx=12, pady=(9, 2))

        # Кнопки пакуются первыми справа: Play/Stop и громкость всегда видны.
        actions = tk.Frame(top_row, bg=Colors.BG_CARD)
        actions.pack(side="right", padx=(10, 0), anchor="ne")

        play_button = _round_btn(
            actions,
            "▶",
            lambda path=output_path: _toggle_card_play(path),
            diameter=34,
            disabled=not audio_exists,
        )
        play_button.pack(side="left", padx=(0, 4))
        ToolTip(
            play_button,
            (
                _safe_t("history_play_stop_tip", "Воспроизвести / остановить")
                if audio_exists
                else _safe_t("tip_audio_missing", "Аудио удалено")
            ),
        )

        volume_button = None
        if audio_exists:
            volume_button = _round_btn(
                actions,
                _volume_icon(_p["volume"]),
                lambda: _toggle_volume_popup(volume_button),
                diameter=34,
            )
            volume_button.pack(side="left", padx=(0, 6))
            ToolTip(volume_button, _safe_t("history_volume_tip", "Громкость"))

        def reuse_text(text=entry.get("text", "")):
            set_textbox_content(text)
            on_close()

        reuse_button = _round_btn(actions, "↩", reuse_text, diameter=34)
        reuse_button.pack(side="left")
        ToolTip(reuse_button, _safe_t("tip_reuse", "Вставить текст обратно"))

        text_column = tk.Frame(top_row, bg=Colors.BG_CARD)
        text_column.pack(side="left", fill="both", expand=True)

        CompatCTkLabel(
            text_column,
            text=entry.get("date", ""),
            fg_color=Colors.BG_CARD,
            text_color=Colors.ACCENT,
            font=("Segoe UI", scaled_font_size(10), "bold"),
            anchor="w",
        ).pack(fill="x")

        meta = (
            f"🎤 {entry.get('voice', '?')}   ·   ⭐ {entry.get('quality', '?')}"
            f"   ·   {entry.get('chunks', 0)} {t('chunks_word')}"
        )
        CompatCTkLabel(
            text_column,
            text=meta,
            fg_color=Colors.BG_CARD,
            text_color=Colors.TEXT_DIM,
            font=("Segoe UI", scaled_font_size(10)),
            anchor="w",
        ).pack(fill="x", pady=(2, 3))

        text_preview = str(entry.get("text", "") or "").replace("\n", " ")
        CompatCTkLabel(
            text_column,
            text=_truncate(text_preview, 72),
            fg_color=Colors.BG_CARD,
            text_color=Colors.TEXT_MAIN,
            font=("Segoe UI", scaled_font_size(12)),
            anchor="w",
            justify="left",
        ).pack(fill="x")

        wave_canvas = tk.Canvas(
            card,
            bg=Colors.BG_CARD,
            height=scaled_size(58, min_size=52),
            bd=0,
            highlightthickness=0,
            cursor="hand2" if audio_exists else "arrow",
        )
        wave_canvas.pack(fill="x", padx=14, pady=(1, 10))

        duration = _get_duration(output_path) if audio_exists else 0.0
        state = {
            "card": card,
            "canvas": wave_canvas,
            "play_btn": play_button,
            "vol_btn": volume_button,
            "duration": duration,
            "peaks": [],
            "wave_ready": not audio_exists,
            "audio_exists": audio_exists,
        }
        card_key = output_path or f"__missing_audio_{id(card)}"
        _card_widgets.setdefault(card_key, []).append(state)

        if audio_exists:
            wave_canvas.bind(
                "<Button-1>",
                lambda event, path=output_path: _wave_seek(path, event),
            )
            ToolTip(
                wave_canvas,
                _safe_t(
                    "history_wave_seek_tooltip",
                    "Нажмите на волну, чтобы перейти к нужному месту",
                ),
            )
            _load_waveform_async(output_path)
        wave_canvas.bind(
            "<Configure>",
            lambda event, path=card_key: _redraw_card_wave(path),
        )
        _redraw_card_wave(card_key)

    # ── Layout: только шапка и прокручиваемые карточки; нижнего плеера нет. ──
    header = tk.Frame(win, bg=Colors.BG_DARK, pady=12)
    header.pack(fill="x", padx=16)

    clear_pill = CompatCTkFrame(
        header,
        fg_color=Colors.BG_CARD,
        corner_radius=18,
        border_width=1,
        border_color=Colors.BORDER,
    )
    clear_pill.pack(side="left")
    clear_row = tk.Frame(clear_pill, bg=Colors.BG_CARD)
    clear_row.pack(padx=6, pady=6)
    clear_button = _round_btn(clear_row, "🗑", clear_history, diameter=36, danger=True)
    clear_button.pack(side="left")
    ToolTip(clear_button, t("btn_clear_history"))

    count_pill = CompatCTkFrame(
        header,
        fg_color=Colors.BG_CARD,
        corner_radius=14,
        border_width=1,
        border_color=Colors.BORDER,
    )
    count_pill.pack(side="right")
    count_lbl = CompatCTkLabel(
        count_pill,
        text=t("entries_count", len(history)),
        fg_color=Colors.BG_CARD,
        text_color=Colors.TEXT_DIM,
        font=("Segoe UI", scaled_font_size(12)),
    )
    count_lbl.pack(padx=16, pady=9)

    list_frame = ctk.CTkScrollableFrame(
        win,
        fg_color=Colors.BG_DARK,
        corner_radius=12,
    )
    list_frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    for history_entry in history:
        _make_card(list_frame, history_entry)
    _maybe_show_empty_state()

    if PYGAME_OK:
        try:
            pygame.mixer.music.set_volume(_p["volume"])
        except Exception:
            pass

    try:
        win.after(150, lambda: _apply_window_icon(win))
    except Exception:
        pass

    def on_close():
        if _closing["v"]:
            return
        _closing["v"] = True
        _close_volume_popup()
        _stop_playback(reset_position=True)
        try:
            _wave_executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            try:
                _wave_executor.shutdown(wait=False)
            except Exception:
                pass
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass

    win.protocol("WM_DELETE_WINDOW", on_close)
