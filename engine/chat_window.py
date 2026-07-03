# -*- coding: utf-8 -*-
"""СОВМЕСТИМОСТЬ: старое расположение окна AI-чата.

Реальный модуль переехал в engine/gui/chat_window.py (там же подключён
перевод интерфейса через i18n). Этот файл-мост нужен на случай, если
где-то остался старый импорт `import engine.chat_window` или в папке
проекта лежит устаревшая копия: он полностью делегирует новой версии,
поэтому окно чата ВСЕГДА берётся из engine/gui/chat_window.py — уже
с переводом.


"""
from engine.gui.chat_window import *  # noqa: F401,F403
from engine.gui.chat_window import (  # noqa: F401
    init,
    open_chat_window,
    append_chat_message,
    set_chat_status,
    reapply_language,
    CHAT_WINDOW_I18N_VERSION,
)
