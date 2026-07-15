"""Thread-safe rate limiting for high-frequency GUI progress events."""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional


class ProgressThrottle:
    """Coalesce progress updates while always allowing boundary states.

    The class is Tk-independent and may be called from download/inference
    workers. It only decides whether an update should be emitted; the caller is
    responsible for marshalling accepted values to the Tk thread.
    """

    def __init__(self, max_hz: float = 10.0, clock: Optional[Callable[[], float]] = None):
        self._interval = 1.0 / max(1.0, float(max_hz))
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._last_emit = float("-inf")
        self._last_value = None

    def should_emit(self, value: int | float, *, force: bool = False) -> bool:
        now = self._clock()
        boundary = value <= 0 or value >= 100
        with self._lock:
            if value == self._last_value and not force:
                return False
            if not (force or boundary) and now - self._last_emit < self._interval:
                return False
            self._last_emit = now
            self._last_value = value
            return True

    def reset(self) -> None:
        with self._lock:
            self._last_emit = float("-inf")
            self._last_value = None
