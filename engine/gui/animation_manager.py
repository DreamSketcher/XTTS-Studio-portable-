# -*- coding: utf-8 -*-
"""engine/gui/animation_manager.py — централизованный AnimationManager.

Единый тик-цикл (root.after) для всех анимаций приложения.
Graceful degradation при отсутствии root/дисплея (CI, smoke-тесты).

Содержит:
  - Чистые easing-функции (stateless, покрыты unit-тестами)
  - AnimationManager — синглтон с ленивой инициализацией
  - animate() / cancel() / cancel_target() / stop_all() / destroy()

Использование:
    from engine.gui.animation_manager import AnimationManager
    AnimationManager.init(root)  # однократно при создании главного окна
    mgr = AnimationManager.get()
    mgr.animate(target, lambda v: widget.configure(...), 0, 1, duration_ms=300)
"""

from __future__ import annotations

import time
import tkinter
from collections import deque
from typing import Any, Callable, Optional


# ═══════════════════════════════════════════════════════════════════
#  Easing Functions (чистые, без сайд-эффектов)
# ═══════════════════════════════════════════════════════════════════


def ease_linear(t: float) -> float:
    """:math:`f(t) = t`"""
    return t


def ease_in_quad(t: float) -> float:
    """:math:`f(t) = t^2`"""
    return t * t


def ease_out_quad(t: float) -> float:
    """:math:`f(t) = t(2 - t)`"""
    return t * (2.0 - t)


def ease_in_out_quad(t: float) -> float:
    if t < 0.5:
        return 2.0 * t * t
    return -1.0 + (4.0 - 2.0 * t) * t


def ease_in_cubic(t: float) -> float:
    """:math:`f(t) = t^3`"""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """:math:`f(t) = (t-1)^3 + 1`"""
    return (t - 1.0) ** 3 + 1.0


def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4.0 * t * t * t
    return (t - 1.0) * (2.0 * t - 2.0) * (2.0 * t - 2.0) + 1.0


def ease_in_quart(t: float) -> float:
    """:math:`f(t) = t^4`"""
    return t * t * t * t


def ease_out_quart(t: float) -> float:
    """:math:`f(t) = 1 - (t-1)^4`"""
    return 1.0 - (t - 1.0) ** 4


def ease_in_out_quart(t: float) -> float:
    if t < 0.5:
        return 8.0 * t * t * t * t
    return 1.0 - 8.0 * (t - 1.0) ** 4


def ease_out_back(t: float) -> float:
    """:math:`f(t) = 1 + c3*(t-1)^3 + c1*(t-1)^2` с небольшим overshoot."""
    c1: float = 1.70158
    c3: float = c1 + 1.0
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


# Карта имён → функции (используется в AnimationManager и тестах)
EASING_MAP: dict[str, Callable[[float], float]] = {
    "linear": ease_linear,
    "ease_in": ease_in_quad,
    "ease_out": ease_out_quad,
    "ease_in_out": ease_in_out_quad,
    "ease_in_cubic": ease_in_cubic,
    "ease_out_cubic": ease_out_cubic,
    "ease_in_out_cubic": ease_in_out_cubic,
    "ease_in_quart": ease_in_quart,
    "ease_out_quart": ease_out_quart,
    "ease_in_out_quart": ease_in_out_quart,
    "ease_out_back": ease_out_back,
}


def _resolve_easing(name: str) -> Callable[[float], float]:
    """Вернуть easing-функцию по имени; fallback — ease_in_out_quad."""
    return EASING_MAP.get(name, ease_in_out_quad)


# ═══════════════════════════════════════════════════════════════════
#  Animation — внутренняя структура одной анимации
# ═══════════════════════════════════════════════════════════════════


class Animation:
    """Хранилище состояния одной анимации. __slots__ для экономии памяти."""

    __slots__ = (
        "animation_id",
        "target",
        "property_setter",
        "start",
        "end",
        "duration_ms",
        "easing_func",
        "on_complete",
        "start_time",
    )

    def __init__(
        self,
        animation_id: str,
        target: Any,
        property_setter: Callable[[float], None],
        start: float,
        end: float,
        duration_ms: int,
        easing_func: Callable[[float], float],
        on_complete: Optional[Callable[[], None]] = None,
    ):
        self.animation_id = animation_id
        self.target = target
        self.property_setter = property_setter
        self.start = start
        self.end = end
        self.duration_ms = duration_ms
        self.easing_func = easing_func
        self.on_complete = on_complete
        self.start_time = time.monotonic()


# ═══════════════════════════════════════════════════════════════════
#  AnimationManager
# ═══════════════════════════════════════════════════════════════════


class AnimationManager:
    """Центральный менеджер анимаций. Ленивый синглтон.

    Потокобезопасность: все методы вызываются только из UI-потока (как и
    весь Tkinter). Тик-цикл работает через root.after().
    """

    _instance: Optional["AnimationManager"] = None

    # ── Инициализация ─────────────────────────────────────────────

    def __init__(self, root: Optional[tkinter.Misc] = None, fps: int = 60):
        """Создать менеджер. root=None → no-op режим (для CI/тестов)."""
        self._root: Optional[tkinter.Misc] = root
        self._fps: int = max(15, min(120, fps))
        self._active: dict[str, Animation] = {}
        self._tick_id: Optional[str] = None
        self._counter: int = 0
        self._running: bool = True
        self._frame_interval_ms: float = 1000.0 / self._fps
        self._last_tick_duration_ms: float = 0.0
        self._frame_count: int = 0
        self._dropped_frames: int = 0
        self._frame_times = deque(maxlen=240)
        self._slow_windows = 0
        self._good_windows = 0
        self._adaptive_degraded = False

        self._no_op: bool = root is None
        # Event-driven: an idle manager owns no after() callback. animate()
        # starts the loop when the first animation is registered.

    # ── Class-level API ────────────────────────────────────────────

    @classmethod
    def init(cls, root: Optional[tkinter.Misc] = None, fps: int = 60) -> "AnimationManager":
        """Привязать к root-окну. Вызывается однократно в create_main_window().

        Args:
            root: Tk-инстанс (или None для no-op).
            fps: Частота тиков (15–120).

        Returns:
            Экземпляр AnimationManager.
        """
        inst = cls._instance
        if inst is not None:
            # Уже инициализирован — обновляем root если нужно
            if root is not None and inst._root is None:
                inst._root = root
                inst._no_op = False
                inst._running = True
            return inst

        cls._instance = cls(root=root, fps=fps)
        return cls._instance

    @classmethod
    def get(cls) -> "AnimationManager":
        """Вернуть существующий экземпляр или no-op dummy.

        Безопасно для smoke-тестов (см. test_smoke_startup.py): если
        init() не был вызван, animate() сразу применит конечное значение.
        """
        if cls._instance is None:
            cls._instance = cls(root=None)
        return cls._instance

    # ── Публичный API ─────────────────────────────────────────────

    def animate(
        self,
        target: Any,
        property_setter: Callable[[float], None],
        start: float,
        end: float,
        duration_ms: int = 300,
        easing: str = "ease_in_out",
        on_complete: Optional[Callable[[], None]] = None,
        animation_id: Optional[str] = None,
    ) -> str:
        """Запланировать анимацию.

        Args:
            target: Объект (виджет), которому принадлежит анимация.
                    Используется для массовой отмены (cancel_target) и
                    проверки winfo_exists().
            property_setter: Callable(value) — применяет интерполированное
                             значение на каждом тике.
            start: Начальное значение.
            end: Конечное значение.
            duration_ms: Длительность в миллисекундах.
            easing: Имя easing-функции (ключ из EASING_MAP).
            on_complete: Callback после завершения (один раз).
            animation_id: Явный ID для отмены. Если не указан,
                          генерируется автоматически.

        Returns:
            animation_id (str) — можно передать в cancel().
        """
        # No-op режим: сразу применяем конечное значение
        if self._no_op:
            try:
                property_setter(end)
            except Exception:
                pass
            if on_complete is not None:
                try:
                    on_complete()
                except Exception:
                    pass
            return ""

        easing_func = _resolve_easing(easing)

        if animation_id is None:
            self._counter += 1
            animation_id = f"anim_{self._counter}"
            # Авто-ID → автоматически отменяем предыдущую анимацию для того же target
            self.cancel_target(target)
        else:
            # Явный ID → отменяем только конкретную
            self.cancel(animation_id)

        anim = Animation(
            animation_id=animation_id,
            target=target,
            property_setter=property_setter,
            start=float(start),
            end=float(end),
            duration_ms=max(1, int(duration_ms)),
            easing_func=easing_func,
            on_complete=on_complete,
        )
        self._active[animation_id] = anim

        # Убедимся, что тик-цикл запущен
        if self._tick_id is None:
            self._schedule_tick()

        return animation_id

    def cancel(self, animation_id: str) -> None:
        """Отменить анимацию по ID (без применения конечного значения)."""
        if animation_id in self._active:
            del self._active[animation_id]
        self._cancel_tick_if_idle()

    def cancel_target(self, target: Any) -> None:
        """Отменить все анимации для указанного виджета/объекта."""
        to_remove = [aid for aid, anim in self._active.items() if anim.target is target]
        for aid in to_remove:
            del self._active[aid]
        self._cancel_tick_if_idle()

    def is_running(self, animation_id: str) -> bool:
        """Проверить, активна ли анимация с данным ID."""
        return animation_id in self._active

    def stop_all(self) -> None:
        """Немедленно остановить все анимации."""
        self._active.clear()
        self._cancel_tick_if_idle()

    def _cancel_tick_if_idle(self) -> None:
        if self._active or self._tick_id is None or self._root is None:
            return
        try:
            self._root.after_cancel(self._tick_id)
        except Exception:
            pass
        self._tick_id = None

    def performance_snapshot(self) -> dict[str, float | int | bool]:
        """Rolling metrics used by diagnostics and the adaptive motion policy."""
        samples = sorted(self._frame_times)
        if samples:
            p95 = samples[min(len(samples) - 1, int((len(samples) - 1) * 0.95))]
            average = sum(samples) / len(samples)
        else:
            p95 = average = 0.0
        return {
            "fps_target": self._fps,
            "active": len(self._active),
            "last_tick_ms": round(self._last_tick_duration_ms, 3),
            "avg_tick_ms": round(average, 3),
            "p95_tick_ms": round(p95, 3),
            "sample_count": len(samples),
            "frames": self._frame_count,
            "dropped_frames": self._dropped_frames,
            "adaptive_degraded": self._adaptive_degraded,
        }

    def _update_adaptive_motion(self) -> None:
        if len(self._frame_times) < 60 or self._frame_count % 30:
            return
        snapshot = self.performance_snapshot()
        p95 = float(snapshot["p95_tick_ms"])
        slow = p95 > self._frame_interval_ms * 1.35
        if slow:
            self._slow_windows += 1
            self._good_windows = 0
        else:
            self._good_windows += 1
            self._slow_windows = 0

        changed = False
        if not self._adaptive_degraded and self._slow_windows >= 2:
            self._adaptive_degraded = True
            changed = True
        elif self._adaptive_degraded and self._good_windows >= 6:
            self._adaptive_degraded = False
            changed = True
        if changed:
            try:
                from engine.gui.motion_profile import set_adaptive_degraded

                set_adaptive_degraded(self._adaptive_degraded)
            except Exception:
                pass

    def destroy(self) -> None:
        """Полная остановка менеджера: отмена всех анимаций и тик-цикла.

        Вызывается из on_closing() главного окна.
        """
        self._running = False
        self._active.clear()
        if self._tick_id is not None and self._root is not None:
            try:
                self._root.after_cancel(self._tick_id)
            except Exception:
                pass
        self._tick_id = None

    # ── Внутренний тик-цикл ────────────────────────────────────────

    def _schedule_tick(self, delay_ms: Optional[int] = None) -> None:
        """Schedule one frame; never keep a timer alive while idle."""
        if self._no_op or not self._running or not self._active or self._tick_id is not None:
            return

        if self._root is None:
            return

        try:
            # Проверка жив ли root
            if not self._root.winfo_exists():
                self._running = False
                return
        except Exception:
            self._running = False
            return

        if delay_ms is None:
            delay_ms = round(self._frame_interval_ms)
        delay = max(1, min(100, int(delay_ms)))
        try:
            self._tick_id = self._root.after(delay, self._tick)
        except Exception:
            self._tick_id = None

    def _tick(self) -> None:
        """Process one frame and compensate for time spent rendering it."""
        frame_started = time.perf_counter()
        self._tick_id = None

        if not self._running:
            return

        if not self._active:
            # Нет активных анимаций — не планируем следующий тик.
            # Он будет запланирован при следующем вызове animate().
            return

        now: float = time.monotonic()
        finished: list[str] = []

        for anim_id, anim in list(self._active.items()):
            try:
                # Проверка: жив ли целевой виджет
                _widget_ok = True
                if hasattr(anim.target, "winfo_exists"):
                    try:
                        if not anim.target.winfo_exists():
                            _widget_ok = False
                    except tkinter.TclError:
                        _widget_ok = False

                if not _widget_ok:
                    finished.append(anim_id)
                    continue

                elapsed_ms: float = (now - anim.start_time) * 1000.0

                if elapsed_ms >= anim.duration_ms:
                    # Анимация завершена — применяем конечное значение
                    try:
                        anim.property_setter(anim.end)
                    except tkinter.TclError:
                        pass
                    finished.append(anim_id)
                    if anim.on_complete is not None:
                        try:
                            anim.on_complete()
                        except Exception:
                            pass
                else:
                    # Интерполяция
                    t: float = elapsed_ms / anim.duration_ms
                    eased: float = anim.easing_func(t)
                    value: float = anim.start + (anim.end - anim.start) * eased
                    try:
                        anim.property_setter(value)
                    except tkinter.TclError:
                        finished.append(anim_id)

            except Exception:
                # Безопасность: любое исключение снимает анимацию
                finished.append(anim_id)

        # Удаляем завершённые
        for fid in finished:
            self._active.pop(fid, None)

        self._frame_count += 1
        self._last_tick_duration_ms = (time.perf_counter() - frame_started) * 1000.0
        self._frame_times.append(self._last_tick_duration_ms)
        if self._last_tick_duration_ms > self._frame_interval_ms:
            self._dropped_frames += 1
        self._update_adaptive_motion()

        # Keep start-to-start cadence close to target FPS instead of adding a
        # fixed delay after expensive Tcl/Tk redraw work.
        remaining_ms = self._frame_interval_ms - self._last_tick_duration_ms
        self._schedule_tick(max(1, round(remaining_ms)))
