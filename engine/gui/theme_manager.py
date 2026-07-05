# -*- coding: utf-8 -*-
"""engine/gui/theme_manager.py — сохранение/загрузка кастомной темы в theme_settings.json"""

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

# --- Пресеты раскладки (Classic = текущая раскладка приложения) ---
# Значения для Classic взяты из engine/gui/layout.py build_layout():
# left_panel width=260, main_container padx=8, pady=14,
# left_panel padx=(0,2), toggle_strip width=22
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
    # ВНИМАНИЕ (важно для истории этого файла): секция "colors" ниже —
    # ЛЕГАСИ-СТРУКТУРА из самой первой версии Конструктора темы. Она
    # реально сохранялась в JSON, но НИКОГДА не применялась к настоящей
    # палитре приложения (engine/gui/colors.py Colors/DARK_PALETTE/
    # LIGHT_PALETTE) — это была "мёртвая" секция, отдельная от рабочей
    # системы тем (☀/🌙 в textbox.py -> theme.py -> colors.apply_palette()).
    # Из 11 ключей здесь только 5 случайно совпадали по ИМЕНИ с реальными
    # атрибутами Colors (BG_DARK, TEXT_MAIN, TEXT_DIM, ACCENT, BORDER), но
    # даже они не считывались обратно в Colors. Секция оставлена как есть
    # для обратной совместимости чтения старых theme_settings.json (чтобы
    # merge в load_theme() не падал), но для реальной покраски приложения
    # теперь используется НОВАЯ секция "custom_colors" ниже — см. её
    # комментарий и get_custom_colors()/set_custom_colors().
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
    # Поддержка и старого ключа "layout", и нового "layout_preset"
    "layout": "classic",
    "layout_preset": "classic",
    "presets": DEFAULT_LAYOUT_PRESETS,
    # ── НОВАЯ рабочая система кастомизации цветов ──
    # Структура: {"dark": {"BG_CARD": "#...", ...}, "light": {...}}.
    # Хранит ТОЛЬКО переопределения поверх встроенных DARK_PALETTE/
    # LIGHT_PALETTE из engine/gui/colors.py — пустой словарь для темы
    # означает "ничего не настраивалось, используется встроенная палитра
    # как есть" (100% совпадает с поведением ДО добавления кастомизации).
    # Применяется в colors.apply_palette() — см. комментарий там.
    "custom_colors": {
        "dark": {},
        "light": {},
    },
    # ── Базовый размер шрифта интерфейса (масштабируется через
    # colors.scaled_font_size(), см. подробный комментарий в colors.py).
    # НЕ относится к тексту в поле ввода/редакторе (engine/gui/textbox.py) —
    # там свой независимый механизм размера (слайдер "Aa"). 10 = дефолт,
    # соответствует поведению приложения ДО добавления этой фичи.
    "font_base_size": 10,
    # ── Именованные пользовательские пресеты темы ──
    # Каждый пресет — это "снимок" (color + font + layout) на момент
    # сохранения. Формат одного пресета:
    #   {
    #     "custom_colors": {"BG_CARD": "#...", ...},  # для темы, в которой сохранён
    #     "theme_name": "dark" | "light",              # какая тема была активна
    #     "font_base_size": 12,
    #     "layout_preset": "classic" | "compact" | "wide",
    #   }
    # Список пуст по умолчанию — ничего не создаётся автоматически.
    "saved_presets": {},
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
    """Загружает настройки темы из JSON. Если файла нет, возвращает значения по умолчанию."""
    data = _read_json()
    if not data:
        return json.loads(json.dumps(DEFAULT_THEME))  # deep copy

    # Слияние с дефолтной темой для гарантии наличия всех ключей
    merged = json.loads(json.dumps(DEFAULT_THEME))
    for section in DEFAULT_THEME:
        if section in data:
            if isinstance(data[section], dict) and isinstance(merged.get(section), dict):
                merged[section].update(data[section])
            else:
                merged[section] = data[section]
    # Обратная совместимость: layout -> layout_preset
    if "layout_preset" not in merged and "layout" in merged:
        merged["layout_preset"] = merged["layout"]
    return merged

def save_theme(theme_data: dict):
    """Сохраняет данные темы в JSON файл. Не затирает presets, если их нет во входных данных."""
    try:
        # Не ломаем существующие presets
        current = _read_json()
        out = current.copy()
        out.update(theme_data)
        # Гарантируем наличие presets
        if "presets" not in out:
            out["presets"] = DEFAULT_LAYOUT_PRESETS
        # Синхронизируем layout / layout_preset
        if "layout_preset" in out:
            out["layout"] = out["layout_preset"]
        elif "layout" in out:
            out["layout_preset"] = out["layout"]
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ThemeManager] Save error: {e}")

# --- Layout Presets API ---

def get_layout_presets() -> dict:
    data = load_theme()
    presets = data.get("presets", {})
    # Дополняем недостающие дефолтными (обратная совместимость)
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
    """Возвращает словарь геометрии для пресета. Fallback -> classic."""
    presets = get_layout_presets()
    if name is None:
        name = get_current_layout_preset_name()
    preset = presets.get(name)
    if preset is None:
        preset = presets.get("classic", DEFAULT_LAYOUT_PRESETS["classic"])
    return preset.copy()

def set_layout_preset(name: str) -> bool:
    """Сохраняет выбор пресета в theme_settings.json"""
    presets = get_layout_presets()
    if name not in presets:
        return False
    data = _read_json()
    data["layout_preset"] = name
    data["layout"] = name  # для совместимости со старым ключом
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
    """Публичная функция для main_window.py"""
    return get_layout_preset(name)

# --- Разовая подсказка про Double-Click на кнопке темы (☀/🌙) ---
# Флаг хранится прямо в theme_settings.json (без завязки на load_theme()/
# save_theme(), т.к. они мержат только ключи из DEFAULT_THEME — читаем и
# пишем "сырой" json напрямую, по аналогии с set_layout_preset() выше).

def is_layout_hint_shown() -> bool:
    """True, если подсказка «Двойной клик открывает настройки темы и
    раскладки интерфейса» уже была показана пользователю ранее."""
    data = _read_json()
    return bool(data.get("layout_hint_shown", False))

def mark_layout_hint_shown() -> None:
    """Отмечает, что подсказка уже была показана (больше не показывать)."""
    try:
        data = _read_json()
        data["layout_hint_shown"] = True
        with open(THEME_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ThemeManager] mark_layout_hint_shown error: {e}")


# --- Кастомные цвета поверх встроенных палитр (dark/light) ---
# Это НОВАЯ, реально работающая замена легаси-секции "colors" выше (см.
# комментарий в DEFAULT_THEME). Ключевое отличие: значения тут ПРИМЕНЯЮТСЯ
# к настоящей палитре через engine/gui/colors.py apply_palette(), а не
# просто сохраняются "в стол". Хранится отдельно на dark/light, потому что
# у тем разные базовые палитры (см. DARK_PALETTE/LIGHT_PALETTE) — цвет,
# который хорошо смотрится на тёмном фоне, может быть нечитаем на светлом.

def get_custom_colors(theme_name: str) -> dict:
    """Возвращает словарь переопределений цвета для темы ('dark'|'light').
    Пустой словарь = пользователь ничего не настраивал, используется
    встроенная DARK_PALETTE/LIGHT_PALETTE как есть (поведение по
    умолчанию, ничего не сломано для тех, кто не открывал конструктор)."""
    data = load_theme()
    custom = data.get("custom_colors", {})
    if not isinstance(custom, dict):
        return {}
    theme_colors = custom.get(theme_name, {})
    return theme_colors.copy() if isinstance(theme_colors, dict) else {}


def set_custom_colors(theme_name: str, colors: dict) -> bool:
    """Сохраняет переопределения цвета для конкретной темы ('dark'|'light'),
    НЕ затрагивая переопределения другой темы (важно: пользователь может
    настроить только dark, а light должна остаться нетронутой)."""
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
    """Сбрасывает переопределения цвета для темы обратно к встроенной
    палитре (используется кнопкой 'Сбросить к стандартной' в конструкторе)."""
    return set_custom_colors(theme_name, {})


# --- Базовый размер шрифта интерфейса (не относится к textbox-редактору) ---

def get_font_base_size() -> int:
    """Возвращает сохранённый базовый размер шрифта (pt). Fallback -> 10
    (дефолт, соответствует поведению приложения до этой фичи)."""
    data = load_theme()
    try:
        return int(data.get("font_base_size", 10))
    except Exception:
        return 10


def set_font_base_size(base_size: int) -> bool:
    """Сохраняет новый базовый размер шрифта в theme_settings.json."""
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


# --- Именованные пользовательские пресеты (цвета + шрифт + раскладка) ---
# См. структуру одного пресета в комментарии у "saved_presets" внутри
# DEFAULT_THEME выше. Пресет — это "снимок" полного визуального состояния
# на момент сохранения; применение пресета полностью заменяет текущие
# custom_colors (для темы, с которой пресет был сохранён), font_base_size
# и layout_preset одним действием.

def get_saved_presets() -> dict:
    """Возвращает словарь {имя_пресета: данные_пресета}."""
    data = load_theme()
    presets = data.get("saved_presets", {})
    return presets if isinstance(presets, dict) else {}


def save_named_preset(preset_name: str, snapshot: dict) -> bool:
    """Сохраняет новый именованный пресет (или перезаписывает существующий
    с тем же именем — пользователь явно предупреждается об этом в UI).
    snapshot должен содержать: custom_colors, theme_name, font_base_size,
    layout_preset (см. структуру в DEFAULT_THEME)."""
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
    """Удаляет именованный пресет по имени. Возвращает False, если
    пресета с таким именем не было (ничего не сломано, просто нечего
    удалять)."""
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
    """Применяет сохранённый пресет: пишет его custom_colors/font_base_size/
    layout_preset в theme_settings.json как ТЕКУЩЕЕ активное состояние.
    Возвращает словарь пресета при успехе (чтобы вызывающий код —
    theme_settings.py — мог сразу применить его к живому Colors/шрифтам
    без перезапуска), либо None, если пресет с таким именем не найден.

    ВАЖНО: НЕ переключает саму тему (dark/light) — пресет применяется
    к теме, которая была активна в момент его создания (snapshot["theme_name"]),
    поэтому вызывающий код должен переключить тему сам, если она отличается
    от текущей (или предупредить пользователя)."""
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

