# -*- coding: utf-8 -*-
"""engine/gui/queue_panel.py — карточка «Очередь задач» и её обновление
(перенесено из gui.py: update_queue_view, queue_autorefresh, секция Queue)."""
import tkinter as tk

from i18n import t

from engine.gui.colors import Colors
from engine.gui.widgets import create_card, create_button
from engine.gui.batch_panel import open_batch_window

# Внедряются из main_window: root, task_manager
root = None
task_manager = None

# Виджеты (создаются в build_queue_card)
queue_card = None
queue_listbox = None
batch_btn_row = None


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def update_queue_view():
    try:
        queue_listbox.delete(0, tk.END)
        status_icons = {
            "queued": "⏳", "running": "▶ ", "done": "✔",
            "error": "❌", "cancelled": "⛔",
        }
        queue = task_manager.get_queue()
        active_set = False
        for i, task in enumerate(queue):
            name = task.text[:30].replace("\n", " ")
            if not active_set and task.status in ("queued", "running"):
                icon = "▶ "
                active_set = True
            else:
                icon = status_icons.get(task.status, "•")
            queue_listbox.insert(tk.END, f"{icon} {name} | {task.progress}%")
            if icon == "▶ ":
                queue_listbox.itemconfig(i, fg=Colors.TEXT_SUCCESS)
            elif task.status == "done":
                queue_listbox.itemconfig(i, fg=Colors.TEXT_DIM)
            elif task.status == "error":
                queue_listbox.itemconfig(i, fg=Colors.TEXT_ERROR)
    except Exception:
        pass
def queue_autorefresh():
    update_queue_view()
    root.after(500, queue_autorefresh)


def build_queue_card(left_panel):
    global queue_card, queue_listbox, batch_btn_row
    queue_card = create_card(left_panel, "")
    queue_card.pack(fill="x", pady=(0, 8))
    tk.Label(
        queue_card,
        text=t("card_queue"),
        bg=Colors.BG_CARD,
        fg=Colors.TEXT_MAIN,
        font=("Segoe UI", 9, "bold"),
        anchor="w"
    ).pack(fill="x", padx=10, pady=(7, 3))
    queue_listbox = tk.Listbox(
        queue_card, height=7,
        bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
        selectbackground=Colors.ACCENT, selectforeground=Colors.TEXT_MAIN,
        relief="flat", highlightthickness=0, font=("Consolas", 8),
        activestyle="none", exportselection=False
    )
    queue_listbox.pack(fill="x", padx=10, pady=(0, 4))
    batch_btn_row = tk.Frame(queue_card, bg=Colors.BG_CARD)
    batch_btn_row.pack(fill="x", padx=10, pady=(0, 7))
    create_button(batch_btn_row, t("btn_batch"), open_batch_window,
                  bg=Colors.BG_INPUT).pack(fill="x")
