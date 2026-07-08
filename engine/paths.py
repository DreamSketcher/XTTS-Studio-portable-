"""Общие пути приложения XTTS Studio."""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Основные рабочие папки
BACKUP_DIR = os.path.join(BASE_DIR, "library")   # используется VoiceManager и player.py как библиотека голосов
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
LOG_DIR = os.path.join(BASE_DIR, "logs")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
REF_DIR = os.path.join(BASE_DIR, "reference")

# Иконка окна: сначала ищем в assets, затем в корне
if os.path.isfile(os.path.join(ASSETS_DIR, "icon.ico")):
    ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")
elif os.path.isfile(os.path.join(BASE_DIR, "icon.ico")):
    ICON_PATH = os.path.join(BASE_DIR, "icon.ico")
else:
    ICON_PATH = ""

# Создаём папки при импорте, если их нет
for _d in (BACKUP_DIR, OUTPUT_DIR, LOG_DIR, REF_DIR):
    os.makedirs(_d, exist_ok=True)


def __getattr__(name: str):
    """
    Автоматически создаём путь для любой неизвестной константы вида:
    XXX_DIR -> BASE_DIR/xxx, XXX_PATH -> BASE_DIR/xxx
    """
    if name.endswith("_DIR"):
        folder = name[:-4].lower()
        path = os.path.join(BASE_DIR, folder)
        os.makedirs(path, exist_ok=True)
        globals()[name] = path
        return path
    if name.endswith("_PATH"):
        base = name[:-5].lower()
        path = os.path.join(BASE_DIR, base)
        globals()[name] = path
        return path
    raise AttributeError(f"module 'engine.paths' has no attribute '{name}'")