"""Safe worker-to-Tk callback delivery through a UI-owned queue poller."""

from __future__ import annotations

import queue
import threading
from typing import Callable, Optional


class UIThreadBridge:
    """Marshal worker callbacks to the Tk thread without calling Tk from workers.

    `begin()` must be called by the UI thread before starting a worker. Workers
    call `post()` and finish with `producer_done()`. The UI-owned poller stops
    automatically when no producers and no queued callbacks remain.
    """

    def __init__(self, widget, poll_ms: int = 16, max_batch: int = 64):
        self._widget = widget
        self._poll_ms = max(4, min(100, int(poll_ms)))
        self._max_batch = max(1, int(max_batch))
        self._queue: queue.Queue[tuple[Callable, tuple, dict]] = queue.Queue()
        self._lock = threading.Lock()
        self._producers = 0
        self._after_id: Optional[str] = None
        self._destroyed = False

    def begin(self) -> None:
        """Register a producer and ensure polling; call from the Tk thread."""
        with self._lock:
            if self._destroyed:
                return
            self._producers += 1
        self._ensure_polling()

    def post(self, callback: Callable, *args, **kwargs) -> bool:
        """Queue a callback. Safe from any thread and never touches Tk."""
        with self._lock:
            if self._destroyed:
                return False
        self._queue.put((callback, args, kwargs))
        return True

    def producer_done(self) -> None:
        """Mark one producer complete. Safe from any thread."""
        with self._lock:
            self._producers = max(0, self._producers - 1)

    def _ensure_polling(self) -> None:
        if self._destroyed or self._after_id is not None:
            return
        try:
            self._after_id = self._widget.after(self._poll_ms, self._drain)
        except Exception:
            self._after_id = None

    def _drain(self) -> None:
        self._after_id = None
        if self._destroyed:
            return
        processed = 0
        while processed < self._max_batch:
            try:
                callback, args, kwargs = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback(*args, **kwargs)
            except Exception:
                # A failed UI callback must not block later events.
                pass
            processed += 1

        with self._lock:
            producers = self._producers
        if producers > 0 or not self._queue.empty():
            self._ensure_polling()

    def destroy(self) -> None:
        """Cancel polling and discard pending callbacks; call from UI thread."""
        with self._lock:
            self._destroyed = True
            self._producers = 0
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def snapshot(self) -> dict[str, int | bool]:
        with self._lock:
            producers = self._producers
            destroyed = self._destroyed
        return {
            "producers": producers,
            "queued": self._queue.qsize(),
            "polling": self._after_id is not None,
            "destroyed": destroyed,
        }
