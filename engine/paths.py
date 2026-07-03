# -*- coding: utf-8 -*-
"""engine/paths.py — базовые директории проекта (перенесено из gui.py, секция BASE DIR & PATHS)."""
import os

# Корень проекта: C:\XTTS Studio (папка, где лежит gui.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
REF_DIR = os.path.join(BASE_DIR, "reference")
BACKUP_DIR = os.path.join(BASE_DIR, "library")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
ICON_PATH = os.path.join(BASE_DIR, "icon.ico")
for folder in (LOG_DIR, REF_DIR, BACKUP_DIR, OUTPUT_DIR):
    os.makedirs(folder, exist_ok=True)
