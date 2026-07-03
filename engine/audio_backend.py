# -*- coding: utf-8 -*-
"""engine/audio_backend.py — инициализация аудио-бэкенда pygame (перенесено из gui.py, секция PYGAME)."""
import pygame

PYGAME_OK = False


def init_audio():
    """Инициализация pygame.mixer — вызывается один раз при старте GUI."""
    global PYGAME_OK
    try:
        pygame.mixer.init()
        PYGAME_OK = True
    except Exception as e:
        PYGAME_OK = False
        print(f"[GUI] pygame.mixer init failed: {e}")
