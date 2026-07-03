# -*- coding: utf-8 -*-
"""engine/gui/output_window.py — окно «Аудио» / Outputs со встроенным плеером
(перенесено из gui.py: open_outputs_folder)."""
import os
import datetime as _dt
import tkinter as tk
from tkinter import messagebox, ttk

import pygame

try:
    import soundfile as sf
except ImportError:
    sf = None

from i18n import t

from engine.paths import BASE_DIR, OUTPUT_DIR
from engine.gui.colors import Colors

# Внедряются из main_window: root, PYGAME_OK
root = None
PYGAME_OK = False


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def open_outputs_folder():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    win = tk.Toplevel(root)
    win.title(t("win_audio_title"))
    win.geometry("720x560")
    win.minsize(600, 440)
    win.resizable(True, True)
    win.configure(bg=Colors.BG_DARK)
    win.grab_set()
    # ── внутреннее состояние плеера ──
    _p = {
        "playing": False,
        "path": None,
        "pos": 0.0,
        "duration": 0.0,
        "after_id": None,
    }
    # ── helpers ──
    def _fmt(sec):
        sec = max(0, int(sec))
        return f"{sec // 60}:{sec % 60:02d}"
    def _get_duration(path):
        try:
            if sf is None:
                return 0.0
            return sf.info(path).duration
        except Exception:
            return 0.0
    def _file_date(path):
        try:
            ts = os.path.getmtime(path)
            d = _dt.datetime.fromtimestamp(ts)
            today = _dt.date.today()
            if d.date() == today:
                return t("time_today", d.strftime('%H:%M'))
            elif (today - d.date()).days == 1:
                return t("time_yesterday", d.strftime('%H:%M'))
            return d.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return ""
    def _collect_files():
        try:
            files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".wav")]
            files.sort(key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)), reverse=True)
            return files
        except Exception:
            return []
    # ── tick / playback ──
    def _tick():
        if not PYGAME_OK:
            return
        try:
            if pygame.mixer.music.get_busy():
                _p["pos"] += 0.2
                pct = min(100, _p["pos"] / max(_p["duration"], 0.1) * 100)
                seek_var.set(pct)
                pos_lbl.config(text=_fmt(_p["pos"]))
                _p["after_id"] = win.after(200, _tick)
            else:
                _p["playing"] = False
                _p["after_id"] = None
                btn_play.config(text="▶ ")
                seek_var.set(0)
                pos_lbl.config(text="0:00")
        except Exception:
            pass
    def _stop_ticker():
        if _p["after_id"]:
            try:
                win.after_cancel(_p["after_id"])
            except Exception:
                pass
            _p["after_id"] = None
    def _load_play(path, from_pos=0.0):
        if not PYGAME_OK or not path or not os.path.isfile(path):
            return
        _stop_ticker()
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(start=from_pos)
            dur = _get_duration(path)
            _p.update(playing=True, path=path, pos=from_pos, duration=dur)
            dur_lbl.config(text=_fmt(dur))
            btn_play.config(text="⏸")
            now_lbl.config(text=os.path.basename(path), fg=Colors.TEXT_MAIN)
            seek_var.set(from_pos / max(dur, 0.1) * 100)
            pos_lbl.config(text=_fmt(from_pos))
            _tick()
            _highlight_active(path)
        except Exception as e:
            now_lbl.config(text=f"Ошибка: {e}", fg=Colors.TEXT_ERROR)
    def toggle_play():
        if not PYGAME_OK:
            return
        if _p["playing"]:
            pygame.mixer.music.pause()
            _p["playing"] = False
            _stop_ticker()
            btn_play.config(text="▶ ")
        else:
            if _p["path"] and os.path.isfile(_p["path"]):
                pygame.mixer.music.unpause()
                _p["playing"] = True
                btn_play.config(text="⏸")
                _tick()
    def seek_rel(delta):
        if not _p["path"]:
            return
        _load_play(_p["path"], max(0.0, _p["pos"] + delta))
    def on_seek_drag(val):
        if not _p["path"] or not _p["duration"]:
            return
        new_pos = float(val) / 100.0 * _p["duration"]
        _load_play(_p["path"], new_pos)
    # ── карточки файлов ──
    _card_widgets = {}
    _active_path = {"v": None}
    def _highlight_active(path):
        prev = _active_path["v"]
        if prev and prev in _card_widgets:
            try:
                _card_widgets[prev].config(bg=Colors.BG_CARD,
                                           highlightbackground=Colors.BORDER)
            except Exception:
                pass
        _active_path["v"] = path
        if path in _card_widgets:
            try:
                _card_widgets[path].config(bg="#1c2330",
                                           highlightbackground=Colors.ACCENT)
            except Exception:
                pass
    def _make_card(parent, fname):
        path = os.path.join(OUTPUT_DIR, fname)
        dur = _get_duration(path)
        size_kb = os.path.getsize(path) // 1024
        date_str = _file_date(path)
        dur_str = _fmt(dur) if dur > 0 else "?"
        meta = f"{size_kb} KB · {dur_str} · {date_str}"
        card = tk.Frame(
            parent,
            bg=Colors.BG_CARD,
            highlightthickness=1,
            highlightbackground=Colors.BORDER,
            bd=0,
            cursor="hand2",
        )
        card.pack(fill="x", padx=8, pady=3)
        _card_widgets[path] = card
        ico = tk.Label(card, text="🎵", bg=Colors.BG_CARD,
                       font=("Segoe UI", 14), padx=10, pady=8)
        ico.pack(side="left")
        info = tk.Frame(card, bg=Colors.BG_CARD)
        info.pack(side="left", fill="both", expand=True, pady=8)
        name_lbl = tk.Label(
            info, text=fname, bg=Colors.BG_CARD,
            fg=Colors.TEXT_MAIN, font=("Segoe UI", 10, "bold"),
            anchor="w", wraplength=360, justify="left"
        )
        name_lbl.pack(fill="x")
        meta_lbl = tk.Label(
            info, text=meta, bg=Colors.BG_CARD,
            fg=Colors.TEXT_DIM, font=("Segoe UI", 8),
            anchor="w"
        )
        meta_lbl.pack(fill="x")
        btn_frame = tk.Frame(card, bg=Colors.BG_CARD)
        btn_frame.pack(side="right", padx=8)
        btn_pl = tk.Button(
            btn_frame, text="▶ ", bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
            relief="flat", bd=0, font=("Segoe UI", 10), padx=6, pady=3,
            cursor="hand2", activebackground=Colors.BG_ACTIVE,
            activeforeground=Colors.TEXT_MAIN,
            command=lambda p=path: _load_play(p)
        )
        btn_pl.pack(side="left", padx=(0, 4))
        btn_del = tk.Button(
            btn_frame, text="🗑", bg=Colors.BG_INPUT, fg=Colors.TEXT_ERROR,
            relief="flat", bd=0, font=("Segoe UI", 10), padx=6, pady=3,
            cursor="hand2", activebackground=Colors.BG_DANGER,
            activeforeground=Colors.TEXT_MAIN,
            command=lambda p=path, c=card: _delete_file(p, c)
        )
        btn_del.pack(side="left")
        def _enter(e, c=card, p=path):
            if _active_path["v"] != p:
                c.config(bg=Colors.BG_HOVER, highlightbackground=Colors.BORDER)
            for w in c.winfo_children():
                try:
                    w.config(bg=Colors.BG_HOVER if _active_path["v"] != p else "#1c2330")
                except Exception:
                    pass
            for w in btn_frame.winfo_children():
                try:
                    w.config(bg=Colors.BG_INPUT)
                except Exception:
                    pass
        def _leave(e, c=card, p=path):
            active_bg = "#1c2330" if _active_path["v"] == p else Colors.BG_CARD
            c.config(bg=active_bg,
                     highlightbackground=Colors.ACCENT if _active_path["v"] == p else Colors.BORDER)
            for w in c.winfo_children():
                try:
                    w.config(bg=active_bg)
                except Exception:
                    pass
        for widget in [card, ico, info, name_lbl, meta_lbl, btn_frame]:
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)
        card.bind("<Double-Button-1>", lambda e, p=path: _load_play(p))
        ico.bind("<Double-Button-1>", lambda e, p=path: _load_play(p))
        name_lbl.bind("<Double-Button-1>", lambda e, p=path: _load_play(p))
    def _delete_file(path, card_widget):
        fname = os.path.basename(path)
        if not messagebox.askyesno(t("dlg_delete_title"), t("dlg_delete_msg", fname), parent=win):
            return
        if _p.get("path") == path:
            _stop_ticker()
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            _p.update(playing=False, path=None, pos=0.0, duration=0.0)
            btn_play.config(text="▶ ")
            pos_lbl.config(text="0:00")
            dur_lbl.config(text="0:00")
            seek_var.set(0)
            now_lbl.config(text=t("no_file"), fg=Colors.TEXT_DIM)
        try:
            os.remove(path)
        except Exception as e:
            messagebox.showerror("❌", str(e), parent=win)
            return
        if path in _card_widgets:
            del _card_widgets[path]
        try:
            card_widget.destroy()
        except Exception:
            pass
        _update_count()
    def _delete_all():
        files = [f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".wav")]
        if not files:
            messagebox.showinfo(t("dlg_empty"), t("dlg_empty_msg"), parent=win)
            return
        if not messagebox.askyesno(t("dlg_delete_all_title"),
                                   t("dlg_delete_all_msg", len(files)), parent=win):
            return
        _stop_ticker()
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        _p.update(playing=False, path=None, pos=0.0, duration=0.0)
        btn_play.config(text="▶ ")
        pos_lbl.config(text="0:00")
        dur_lbl.config(text="0:00")
        seek_var.set(0)
        now_lbl.config(text=t("no_file"), fg=Colors.TEXT_DIM)
        for f in files:
            try:
                os.remove(os.path.join(OUTPUT_DIR, f))
            except Exception:
                pass
        _card_widgets.clear()
        _active_path["v"] = None
        for w in list(scroll_inner.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        _update_count()
    def _clear_cache():
        cache_dirs = [
            os.path.join(BASE_DIR, "reference"),
            os.path.join(BASE_DIR, "cache"),
            os.path.join(OUTPUT_DIR, "_cache"),
        ]
        removed = 0
        for d in cache_dirs:
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if f.endswith((".pth", ".cache", ".wav")):
                    try:
                        os.remove(os.path.join(d, f))
                        removed += 1
                    except Exception:
                        pass
        messagebox.showinfo(
            t("cache_cleared"),
            t("cache_cleared_msg", removed) if removed else t("cache_already_empty"),
            parent=win,
        )
    def _open_folder():
        try:
            os.startfile(OUTPUT_DIR)
        except Exception:
            messagebox.showinfo("Folder", OUTPUT_DIR, parent=win)
    def _update_count():
        try:
            n = len([f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith(".wav")])
        except Exception:
            n = 0
        count_lbl.config(text=t("files_count", n))
    # ── LAYOUT ──
    toolbar = tk.Frame(win, bg=Colors.BG_CARD, pady=6)
    toolbar.pack(fill="x", padx=0)
    def _tb_btn(parent, text, cmd, fg=Colors.TEXT_MAIN, active_bg=Colors.BG_HOVER):
        b = tk.Button(
            parent, text=text, command=cmd,
            bg=Colors.BG_INPUT, fg=fg,
            activebackground=active_bg, activeforeground=Colors.TEXT_MAIN,
            relief="flat", bd=0, font=("Segoe UI", 9),
            padx=10, pady=4, cursor="hand2"
        )
        b.bind("<Enter>", lambda e: b.config(bg=active_bg))
        b.bind("<Leave>", lambda e: b.config(bg=Colors.BG_INPUT))
        return b
    _tb_btn(toolbar, t("btn_open_folder"), _open_folder).pack(side="left", padx=(10, 4))
    sep1 = tk.Frame(toolbar, bg=Colors.BORDER, width=1, height=18)
    sep1.pack(side="left", padx=6)
    _tb_btn(toolbar, t("btn_delete_all"), _delete_all,
            fg=Colors.TEXT_ERROR, active_bg=Colors.BG_DANGER).pack(side="left", padx=(0, 4))
    _tb_btn(toolbar, t("btn_clear_cache"), _clear_cache).pack(side="left")
    count_lbl = tk.Label(toolbar, text="", bg=Colors.BG_CARD,
                         fg=Colors.TEXT_DIM, font=("Segoe UI", 9))
    count_lbl.pack(side="right", padx=12)
    tk.Frame(win, bg=Colors.BORDER, height=1).pack(fill="x")
    # — Список файлов —
    list_outer = tk.Frame(win, bg=Colors.BG_DARK)
    list_outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(list_outer, bg=Colors.BG_DARK, bd=0, highlightthickness=0)
    scrollbar = tk.Scrollbar(list_outer, orient="vertical", command=canvas.yview,
                             bg=Colors.BG_INPUT, troughcolor=Colors.BG_DARK)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    scroll_inner = tk.Frame(canvas, bg=Colors.BG_DARK)
    canvas_window = canvas.create_window((0, 0), window=scroll_inner, anchor="nw")
    def _on_frame_configure(e):
        canvas.configure(scrollregion=canvas.bbox("all"))
    def _on_canvas_configure(e):
        canvas.itemconfig(canvas_window, width=e.width)
    scroll_inner.bind("<Configure>", _on_frame_configure)
    canvas.bind("<Configure>", _on_canvas_configure)
    def _on_mousewheel(e):
        try:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        except Exception:
            pass
    win.bind("<MouseWheel>", _on_mousewheel)
    tk.Frame(win, bg=Colors.BORDER, height=1).pack(fill="x")
    # — Плеер —
    player = tk.Frame(win, bg=Colors.BG_CARD, pady=10)
    player.pack(fill="x", side="bottom")
    now_lbl = tk.Label(
        player, text=t("no_file"), bg=Colors.BG_CARD,
        fg=Colors.TEXT_DIM, font=("Segoe UI", 9),
        anchor="w", padx=14
    )
    now_lbl.pack(fill="x")
    seek_var = tk.DoubleVar(value=0)
    seek_style = ttk.Style()
    seek_style.configure("Seek.Horizontal.TScale", background=Colors.BG_CARD)
    seek_bar = ttk.Scale(
        player, from_=0, to=100, orient="horizontal",
        variable=seek_var, command=on_seek_drag
    )
    seek_bar.pack(fill="x", padx=14, pady=(6, 2))
    time_row = tk.Frame(player, bg=Colors.BG_CARD)
    time_row.pack(fill="x", padx=14)
    pos_lbl = tk.Label(time_row, text="0:00", bg=Colors.BG_CARD,
                       fg=Colors.TEXT_DIM, font=("Consolas", 8))
    pos_lbl.pack(side="left")
    dur_lbl = tk.Label(time_row, text="0:00", bg=Colors.BG_CARD,
                       fg=Colors.TEXT_DIM, font=("Consolas", 8))
    dur_lbl.pack(side="right")
    ctrl = tk.Frame(player, bg=Colors.BG_CARD)
    ctrl.pack(pady=(8, 0))
    def _ctrl_btn(parent, text, cmd, primary=False):
        bg = Colors.BG_ACTIVE if primary else Colors.BG_INPUT
        ab = Colors.BG_HOVER if not primary else "#2ea043"
        b = tk.Button(
            parent, text=text, command=cmd,
            bg=bg, fg=Colors.TEXT_MAIN,
            activebackground=ab, activeforeground=Colors.TEXT_MAIN,
            relief="flat", bd=0, font=("Segoe UI", 11 if primary else 10),
            padx=10, pady=5, cursor="hand2", width=3
        )
        b.bind("<Enter>", lambda e: b.config(bg=ab))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
        return b
    _ctrl_btn(ctrl, "⏪", lambda: seek_rel(-10)).pack(side="left", padx=3)
    _ctrl_btn(ctrl, "⏮", lambda: seek_rel(-5)).pack(side="left", padx=3)
    btn_play = _ctrl_btn(ctrl, "▶ ", toggle_play, primary=True)
    btn_play.pack(side="left", padx=3)
    _ctrl_btn(ctrl, "⏭", lambda: seek_rel(5)).pack(side="left", padx=3)
    _ctrl_btn(ctrl, "⏩", lambda: seek_rel(10)).pack(side="left", padx=3)
    for fname in _collect_files():
        _make_card(scroll_inner, fname)
    _update_count()
    def on_close():
        canvas.unbind_all("<MouseWheel>")
        _stop_ticker()
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        win.destroy()
