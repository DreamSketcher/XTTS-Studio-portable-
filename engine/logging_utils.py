# -*- coding: utf-8 -*-
"""engine/logging_utils.py — файловое логирование (перенесено из gui.py: write_log, _log)."""
import os
from datetime import datetime

from engine.paths import LOG_DIR

def write_log(text: str):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(LOG_DIR, f"xtts_gui_{ts}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(text + "\n\n")
def _log(msg):
    with open(r"C:\XTTS Studio\boot.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
