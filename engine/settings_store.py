# -*- coding: utf-8 -*-
"""engine/settings_store.py — чтение json/settings.json (перенесено из gui.py: SETTINGS_PATH, load_settings)."""

import json

from engine.paths import SETTINGS_PATH
from engine.atomic_write import atomic_write_json


def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(settings):
    try:
        atomic_write_json(SETTINGS_PATH, settings, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
