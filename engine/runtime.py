import os
import sys

def base_dir():
    """
    Корень приложения:
    - dev mode → C:\XTTS_PROJECT
    - exe mode → папка exe
    """

    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


BASE_DIR = base_dir()


def path(*args):
    return os.path.join(BASE_DIR, *args)
