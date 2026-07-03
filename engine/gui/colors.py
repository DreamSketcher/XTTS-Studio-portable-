# -*- coding: utf-8 -*-
"""engine/gui/colors.py — палитра приложения (перенесено из gui.py: class Colors).

Поддерживает две темы:
  • dark  — исходная тёмная (значения не изменены);
  • light — мягкая светлая («молочная», слегка книжная).

Все модули обращаются к атрибутам класса Colors, поэтому смена темы
выполняется мутацией этих атрибутов через apply_palette() ДО построения
окон (или перед открытием нового окна — динамические окна берут цвета
в момент создания и сразу получаются в актуальной теме).
"""

# ── Тёмная тема (исходные значения из gui.py) ──
DARK_PALETTE = {
    "BG_DARK": "#0d1117",
    "BG_CARD": "#161b22",
    "BG_INPUT": "#21262d",
    "BG_HOVER": "#30363d",
    "BG_ACTIVE": "#238636",
    "BG_DANGER": "#da3633",
    "TEXT_MAIN": "#f0f6fc",
    "TEXT_DIM": "#8b949e",
    "TEXT_SUCCESS": "#3fb950",
    "TEXT_WARNING": "#d29922",
    "TEXT_ERROR": "#f85149",
    "ACCENT": "#58a6ff",
    "BORDER": "#30363d",
    "PROGRESS_BG": "#21262d",
    "PROGRESS_FG": "#238636",
    "CHUNK_BG": "#2d5a8e",
    "CHUNK_FG": "#ffffff",
    "TOOLTIP_BG": "#30363d",
    "MENU_BG": "#1c2330",
    "MENU_HOVER": "#2a3142",
    "MENU_ACTIVE": "#1f6feb",
    # ── AI accent colour (muted purple-blue) ──
    "AI_ACCENT": "#7c3aed",
    "AI_ACCENT_HOVER": "#6d28d9",
    "AI_GROUP_BG": "#1a1730",
    # ── Toolbar group backgrounds ──
    "GROUP_BG": "#181d25",
    "GROUP_FILE_BG": "#161b22",
    "GROUP_OUTPUT_BG": "#161b22",
    "GROUP_ACTION_BG": "#161b22",
    # ── низ градиента главного окна ──
    "GRADIENT_BOTTOM": "#1a1f29",
}

# ── Светлая тема: мягкий молочно-книжный тон (не «вычурно белая») ──
LIGHT_PALETTE = {
    "BG_DARK": "#f4efe6",      # молочный фон
    "BG_CARD": "#faf6ee",      # карточки — чуть светлее, кремовые
    "BG_INPUT": "#fffdf7",     # поля ввода — тёплый почти-белый
    "BG_HOVER": "#e9e2d2",     # наведение — приглушённый бежевый
    "BG_ACTIVE": "#2da44e",
    "BG_DANGER": "#d1242f",
    "TEXT_MAIN": "#3a352d",    # тёмно-коричневатый «книжный» текст
    "TEXT_DIM": "#857d6e",
    "TEXT_SUCCESS": "#1a7f37",
    "TEXT_WARNING": "#9a6700",
    "TEXT_ERROR": "#cf222e",
    "ACCENT": "#0969da",
    "BORDER": "#d9d0bd",
    "PROGRESS_BG": "#e9e2d2",
    "PROGRESS_FG": "#2da44e",
    "CHUNK_BG": "#cfe3f7",     # мягкая подсветка чанка
    "CHUNK_FG": "#1f2328",
    "TOOLTIP_BG": "#efe8d8",
    "MENU_BG": "#f7f2e7",
    "MENU_HOVER": "#eae2cf",
    "MENU_ACTIVE": "#0969da",
    "AI_ACCENT": "#6639ba",
    "AI_ACCENT_HOVER": "#835bd6",
    "AI_GROUP_BG": "#f0ebf9",
    "GROUP_BG": "#f1ecdf",
    "GROUP_FILE_BG": "#faf6ee",
    "GROUP_OUTPUT_BG": "#faf6ee",
    "GROUP_ACTION_BG": "#faf6ee",
    "GRADIENT_BOTTOM": "#e9e1d0",
}

PALETTES = {"dark": DARK_PALETTE, "light": LIGHT_PALETTE}


class Colors:
    """Атрибуты заполняются apply_palette(); по умолчанию — тёмная тема."""
    pass


def apply_palette(theme: str = "dark") -> None:
    """Мутирует атрибуты Colors под выбранную тему ('dark' | 'light')."""
    palette = PALETTES.get(theme, DARK_PALETTE)
    for key, value in palette.items():
        setattr(Colors, key, value)


# Инициализация по умолчанию — тёмная (как в исходном gui.py)
apply_palette("dark")
