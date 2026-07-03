# -*- coding: utf-8 -*-
"""engine/gui/word_replacer_window.py — окно «Словарь произношений» (Word Replacer).

Это GUI-модуль, и его место — в engine/gui/. Исходный файл проекта
engine/word_replacer_window.py следует перенести сюда БЕЗ ИЗМЕНЕНИЙ:
просто скопируйте его содержимое вместо этого файла — его код не зависит
от расположения (все зависимости приходят через init()).

Пока файл физически не перенесён, модуль прозрачно делегирует вызовы
старому расположению engine/word_replacer_window.py, поэтому программа
работает идентично в обоих вариантах.
"""

_impl = None
_pending_init = None


def _load_impl():
    """Ленивая загрузка реализации окна со старого расположения."""
    global _impl
    if _impl is None:
        import importlib
        _impl = importlib.import_module("engine.word_replacer_window")
    return _impl


def init(**kwargs):
    """Сохраняет зависимости и передаёт их реализации окна."""
    global _pending_init
    _pending_init = kwargs
    try:
        _load_impl().init(**kwargs)
    except ImportError:
        # Реализация появится позже (файл ещё не перенесён/не создан) —
        # зависимости будут переданы при первом открытии окна.
        pass


def open_word_replacer():
    """Открывает окно «Словарь произношений»."""
    impl = _load_impl()
    if _pending_init is not None and getattr(impl, "_root", True) is None:
        impl.init(**_pending_init)
    return impl.open_word_replacer()
