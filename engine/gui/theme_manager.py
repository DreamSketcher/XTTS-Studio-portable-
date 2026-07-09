# -*- coding: utf-8 -*-
"""engine/gui/theme_manager.py — сохранение/загрузка кастомной темы в theme_settings.json

Добавлено в патче 2026-07-09:
- сохранение состояния кнопки повтора аудио-окна (audio_repeat_one)
"""

import json
import os

# ВАЖНОЕ ПРАВИЛО ПРОЕКТА: любое обращение к путям — ТОЛЬКО через BASE_DIR из engine.paths
try:
    from engine.paths import BASE_DIR
    THEME_FILE = os.path.join(str(BASE_DIR), "theme_settings.json")
except Exception:
    # Fallback для обратной совместимости, если engine.paths ещё не подключен
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    THEME_FILE = os.path.join(_BASE_DIR, "theme_settings.json")

DEFAULT_LAYOUT_PRESETS = {
    "classic": {
        "left_panel_width": 260,
        "padding_main_x": 8,
        "padding_main_y": 14,
        "panel_spacing": 2,
        "toggle_strip_width": 22,
        "right_panel_left_pad": 8,
        "textbox_padx": 10,
        "textbox_pady": 7,
        "toolbar_rows": 2,
        "toolbar_button_size": 32,
        "console_height": 140,
        "statusbar_height": 24,
        "item_spacing": 8,
        "padding_inner": 5
    },
    "compact": {
        "left_panel_width": 220,
        "padding_main_x": 4,
        "padding_main_y": 8,
        "panel_spacing": 2,
        "toggle_strip_width": 18,
        "right_panel_left_pad": 4,
        "textbox_padx": 6,
        "textbox_pady": 4,
        "toolbar_rows": 1,
        "toolbar_button_size": 26,
        "console_height": 100,
        "statusbar_height": 20,
        "item_spacing": 4,
        "padding_inner": 3
    },
    "wide": {
        "left_panel_width": 380,
        "padding_main_x": 12,
        "padding_main_y": 18,
        "panel_spacing": 4,
        "toggle_strip_width": 24,
        "right_panel_left_pad": 10,
        "textbox_padx": 14,
        "textbox_pady": 10,
        "toolbar_rows": 2,
        "toolbar_button_size": 36,
        "console_height": 180,
        "statusbar_height": 28,
        "item_spacing": 10,
        "padding_inner": 8
    }
}

DEFAULT_THEME = {
    "colors": {
        "BG_MAIN": "#1a1b26",
        "BG_SEC": "#24283b",
        "BG_DARK": "#16161e",
        "TEXT_MAIN": "#c0caf5",
        "TEXT_DIM": "#565f89",
        "ACCENT": "#7aa2f7",
        "ACCENT_HOVER": "#8caaee",
        "ACCENT_DARK": "#3d59a1",
        "BORDER": "#414868",
        "SUCCESS": "#9ece6a",
        "ERROR": "#f7768e",
    },
    "fonts": {
        "main": "Segoe UI",
        "mono": "Consolas",
        "size_main": 10,
        "size_header": 14,
        "size_small": 9,
    },
    "geometry": {
        "padding_main": 10,
        "padding_inner": 5,
        "item_spacing": 8,
    },
    "layout": "classic",
    "layout_preset": "classic",
    "presets": DEFAULT_LAYOUT_PRESETS,
    "custom_colors": {
        "dark": {},
        "light": {},
    },
    "font_base_size": 10,
    "saved_presets": {},
    # NEW: состояние кнопки повтора аудио-окна
    "audio_repeat_one": False,
}


def _read_json() -> dict:
    if not os.path.exists(THEME_FILE):
        return {}
    try:
        with open(THEME_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ThemeManager] Load error: {e}")
        return {}


def load_theme() -> dict:
    data = _read_json()
    if not data:
        return json.loads(json.dumps(DEFAULT_THEME))
    merged = json.loads(json.dumps(DEFAULT_THEME))
    for section in DEFAULT_THEME:
        if section in data:
            if isinstance(data[section], dict) and isinstance(merged.get(section), dict):
                merged[section].update(data[section])
            else:
                merged[section] = data[section]
    if "layout_preset" not in merged and "layout" in merged:
        merged["layout_preset"] = merged["layout"]
    return merged


def save_theme(theme_data: dict):
    try:
        current = _read_json()
        out = current.copy()
        out.update(theme_data)
        if "presets" not in out:
            out["presets"] = DEFAULT_LAYOUT_PRESETS
        if "layout_preset" in out:
            out["layout"] = out["layout_preset"]
        elif "layout" in out:
            out["layout_preset"] = out["layout"]
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ThemeManager] Save error: {e}")


def get_layout_presets() -> dict:
    data = load_theme()
    presets = data.get("presets", {})
    merged = DEFAULT_LAYOUT_PRESETS.copy()
    merged.update(presets)
    return merged


def get_current_layout_preset_name() -> str:
    data = load_theme()
    name = data.get("layout_preset") or data.get("layout") or "classic"
    if name not in get_layout_presets():
        return "classic"
    return name


def get_layout_preset(name: str | None = None) -> dict:
    presets = get_layout_presets()
    if name is None:
        name = get_current_layout_preset_name()
    preset = presets.get(name)
    if preset is None:
        preset = presets.get("classic", DEFAULT_LAYOUT_PRESETS["classic"])
    return preset.copy()


def set_layout_preset(name: str) -> bool:
    presets = get_layout_presets()
    if name not in presets:
        return False
    data = _read_json()
    data["layout_preset"] = name
    data["layout"] = name
    if "presets" not in data:
        data["presets"] = DEFAULT_LAYOUT_PRESETS
    try:
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ThemeManager] set_layout_preset error: {e}")
        return False


def load_layout_preset(name: str | None = None) -> dict:
    return get_layout_preset(name)


def is_layout_hint_shown() -> bool:
    data = _read_json()
    return bool(data.get("layout_hint_shown", False))


def mark_layout_hint_shown() -> None:
    try:
        data = _read_json()
        data["layout_hint_shown"] = True
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ThemeManager] mark_layout_hint_shown error: {e}")


# ── NEW: сохранение состояния кнопки повтора аудио-окна ──
def get_audio_repeat() -> bool:
    """Возвращает сохраненное состояние повтора (True = повтор одного трека)."""
    data = _read_json()
    return bool(data.get("audio_repeat_one", False))


# Алиасы для совместимости
def get_audio_repeat_state() -> bool:
    return get_audio_repeat()


def is_audio_repeat() -> bool:
    return get_audio_repeat()


def set_audio_repeat(value: bool) -> bool:
    """Сохраняет состояние повтора в theme_settings.json, не затирая остальные ключи."""
    try:
        data = _read_json()
        data["audio_repeat_one"] = bool(value)
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ThemeManager] set_audio_repeat error: {e}")
        return False


def set_audio_repeat_state(value: bool) -> bool:
    return set_audio_repeat(value)


def get_custom_colors(theme_name: str) -> dict:
    data = load_theme()
    custom = data.get("custom_colors", {})
    if not isinstance(custom, dict):
        return {}
    theme_colors = custom.get(theme_name, {})
    return theme_colors.copy() if isinstance(theme_colors, dict) else {}


def set_custom_colors(theme_name: str, colors: dict) -> bool:
    if theme_name not in ("dark", "light"):
        return False
    try:
        data = _read_json()
        if "custom_colors" not in data or not isinstance(data["custom_colors"], dict):
            data["custom_colors"] = {"dark": {}, "light": {}}
        data["custom_colors"][theme_name] = dict(colors)
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ThemeManager] set_custom_colors error: {e}")
        return False


def reset_custom_colors(theme_name: str) -> bool:
    return set_custom_colors(theme_name, {})


def get_font_base_size() -> int:
    data = load_theme()
    try:
        return int(data.get("font_base_size", 10))
    except Exception:
        return 10


def set_font_base_size(base_size: int) -> bool:
    try:
        base_size = max(6, min(24, int(base_size)))
    except Exception:
        return False
    try:
        data = _read_json()
        data["font_base_size"] = base_size
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ThemeManager] set_font_base_size error: {e}")
        return False


def get_saved_presets() -> dict:
    data = load_theme()
    presets = data.get("saved_presets", {})
    return presets if isinstance(presets, dict) else {}


def save_named_preset(preset_name: str, snapshot: dict) -> bool:
    preset_name = (preset_name or "").strip()
    if not preset_name:
        return False
    try:
        data = _read_json()
        if "saved_presets" not in data or not isinstance(data["saved_presets"], dict):
            data["saved_presets"] = {}
        data["saved_presets"][preset_name] = dict(snapshot)
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ThemeManager] save_named_preset error: {e}")
        return False


def delete_named_preset(preset_name: str) -> bool:
    try:
        data = _read_json()
        presets = data.get("saved_presets", {})
        if not isinstance(presets, dict) or preset_name not in presets:
            return False
        del presets[preset_name]
        data["saved_presets"] = presets
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[ThemeManager] delete_named_preset error: {e}")
        return False


def apply_named_preset(preset_name: str) -> dict | None:
    presets = get_saved_presets()
    snapshot = presets.get(preset_name)
    if not isinstance(snapshot, dict):
        return None
    theme_name = snapshot.get("theme_name", "dark")
    custom_colors = snapshot.get("custom_colors", {})
    font_base_size = snapshot.get("font_base_size", 10)
    layout_preset_name = snapshot.get("layout_preset", "classic")

    set_custom_colors(theme_name, custom_colors)
    set_font_base_size(font_base_size)
    set_layout_preset(layout_preset_name)

    return snapshot.copy()
