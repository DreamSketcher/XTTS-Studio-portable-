# -*- coding: utf-8 -*-
"""engine/settings_store.py — чтение settings.json (перенесено из gui.py: SETTINGS_PATH, load_settings)."""
import json
import os

from engine.paths import BASE_DIR

SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
