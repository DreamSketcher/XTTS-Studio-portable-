# -*- coding: utf-8 -*-
"""engine/gui/gradient.py — градиентный фон главного окна
(перенесено из gui.py: PIL-блок и class GradientBackground)."""
import os
import tkinter as tk

from engine.gui.configure_coalescer import ConfigureCoalescer
from engine.gui.motion_profile import get_motion_profile

try:
    from PIL import Image, ImageTk, ImageDraw

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    try:
        import subprocess, sys

        target_py = r"C:\XTTS Studio\python\xtts_env\Scripts\python.exe"
        py_exe = target_py if os.path.isfile(target_py) else sys.executable
        subprocess.check_call(
            [py_exe, "-m", "pip", "install", "Pillow"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        from PIL import Image, ImageTk, ImageDraw

        PIL_AVAILABLE = True
    except Exception:
        PIL_AVAILABLE = False
        Image = ImageTk = ImageDraw = None


class GradientBackground:
    def __init__(self, win, color1="#0d1117", color2="#1a1f29"):
        self.win = win
        self.color1 = color1
        self.color2 = color2
        self.canvas = tk.Canvas(win, highlightthickness=0, bd=0, bg=color1)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.canvas.tk.call("lower", self.canvas._w)
        self._photo = None
        self._resize = ConfigureCoalescer(win, self._draw_for_size, threshold_px=4)
        win.bind("<Configure>", self._on_resize, add="+")
        win.after_idle(self._draw)

    def _on_resize(self, event):
        if event.widget == self.win:
            self._resize(event)

    def _draw_for_size(self, _width, _height):
        self._draw()

    def _draw(self):
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        if w < 10 or h < 10:
            return
        if not PIL_AVAILABLE or Image is None or get_motion_profile() in ("performance", "off"):
            self.canvas.configure(bg=self.color1)
            return
        try:
            # The gradient is vertical, so render one pixel per row and expand
            # horizontally in C instead of drawing `w * h` Python-level lines.
            strip = Image.new("RGB", (1, h), self.color1)
            draw = ImageDraw.Draw(strip)
            c1 = tuple(int(self.color1[i : i + 2], 16) for i in (1, 3, 5))
            c2 = tuple(int(self.color2[i : i + 2], 16) for i in (1, 3, 5))
            for y in range(h):
                ratio = y / max(1, h)
                r = int(c1[0] + (c2[0] - c1[0]) * ratio)
                g = int(c1[1] + (c2[1] - c1[1]) * ratio)
                b = int(c1[2] + (c2[2] - c1[2]) * ratio)
                draw.point((0, y), fill=(r, g, b))
            base = strip.resize((w, h))
            self._photo = ImageTk.PhotoImage(base)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        except Exception:
            self.canvas.configure(bg=self.color1)
