"""Optional low-overhead UI performance overlay (XTTS_UI_PERF=1)."""

import os
import tkinter as tk


class PerformanceOverlay:
    def __init__(self, root, interval_ms=500):
        self.root = root
        self.interval_ms = max(250, int(interval_ms))
        self.timer = None
        self.label = None
        self.enabled = os.environ.get("XTTS_UI_PERF") == "1"
        if not self.enabled:
            return
        self.label = tk.Label(
            root,
            text="",
            bg="#111827",
            fg="#9ef01a",
            font=("Consolas", 9),
            justify="left",
            anchor="nw",
            padx=6,
            pady=4,
        )
        self.label.place(relx=1.0, x=-8, y=8, anchor="ne")
        self._refresh()

    def _refresh(self):
        self.timer = None
        if not self.enabled or self.label is None:
            return
        try:
            if not self.root.winfo_exists() or not self.label.winfo_exists():
                return
            from engine.gui.animation_manager import AnimationManager
            from engine.gui.motion_profile import get_effective_motion_profile

            metrics = AnimationManager.get().performance_snapshot()
            self.label.configure(
                text=(
                    f"motion {get_effective_motion_profile()}\n"
                    f"frame {metrics['last_tick_ms']:.1f} ms  "
                    f"avg {metrics['avg_tick_ms']:.1f}  p95 {metrics['p95_tick_ms']:.1f}\n"
                    f"active {metrics['active']}  dropped {metrics['dropped_frames']}  "
                    f"samples {metrics['sample_count']}"
                )
            )
            self.label.lift()
            self.timer = self.root.after(self.interval_ms, self._refresh)
        except Exception:
            self.timer = None

    def destroy(self):
        self.enabled = False
        if self.timer is not None:
            try:
                self.root.after_cancel(self.timer)
            except Exception:
                pass
            self.timer = None
        if self.label is not None:
            try:
                self.label.destroy()
            except Exception:
                pass
            self.label = None
