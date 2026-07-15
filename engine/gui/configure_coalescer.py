"""Coalesce Tk <Configure> storms into one post-layout callback."""

from __future__ import annotations


class ConfigureCoalescer:
    def __init__(self, widget, callback, *, threshold_px: int = 2):
        self.widget = widget
        self.callback = callback
        self.threshold_px = max(0, int(threshold_px))
        self._after_id = None
        self._pending_size = None
        self._last_size = None

    def __call__(self, event=None):
        width = int(getattr(event, "width", 0) or 0)
        height = int(getattr(event, "height", 0) or 0)
        size = (width, height)
        reference = self._pending_size or self._last_size
        if reference is not None and all(
            abs(current - previous) < self.threshold_px
            for current, previous in zip(size, reference)
        ):
            return
        self._pending_size = size
        if self._after_id is not None:
            return
        try:
            self._after_id = self.widget.after_idle(self._flush)
        except Exception:
            self._after_id = None
            self._flush()

    def _flush(self):
        self._after_id = None
        size = self._pending_size
        self._pending_size = None
        if size is None:
            return
        if self._last_size == size:
            return
        self._last_size = size
        self.callback(*size)

    def cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = None
        self._pending_size = None
