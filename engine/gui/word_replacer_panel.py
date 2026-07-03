# -*- coding: utf-8 -*-
"""engine/gui/word_replacer_panel.py — привязка окна «Словарь» (Word Replacer)
(перенесено из gui.py: word_replacer_window.init(...), open_word_replacer)."""
from engine.gui import word_replacer_window
from engine.gui.colors import Colors
from engine.gui.widgets import create_button


def setup(root, word_replacer_enabled, save_settings):
    word_replacer_window.init(
        root=root,
        colors=Colors,
        create_button_fn=create_button,
        word_replacer_enabled_var=word_replacer_enabled,
        save_settings_fn=save_settings,
    )


def open_word_replacer():
    word_replacer_window.open_word_replacer()
