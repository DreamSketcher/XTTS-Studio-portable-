import os
import re
import sys
import json
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
import ntpath
from datetime import datetime
import pygame
import threading
from typing import Optional

from engine.voice_manager import VoiceManager
from engine.task_manager import TaskManager
from engine.task_models import Task

# =========================
# BASE DIR & PATHS
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
REF_DIR = os.path.join(BASE_DIR, "reference")
BACKUP_DIR = os.path.join(BASE_DIR, "library")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

for folder in (LOG_DIR, REF_DIR, BACKUP_DIR, OUTPUT_DIR):
    os.makedirs(folder, exist_ok=True)


def write_log(text: str):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = os.path.join(LOG_DIR, f"xtts_gui_{ts}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(text + "\n\n")

# =========================
# COLORS
# =========================
class Colors:
    BG_DARK = "#0d1117"
    BG_CARD = "#161b22"
    BG_INPUT = "#21262d"
    BG_HOVER = "#30363d"
    BG_ACTIVE = "#238636"
    BG_DANGER = "#da3633"
    TEXT_MAIN = "#f0f6fc"
    TEXT_DIM = "#8b949e"
    TEXT_SUCCESS = "#3fb950"
    TEXT_WARNING = "#d29922"
    TEXT_ERROR = "#f85149"
    ACCENT = "#58a6ff"
    BORDER = "#30363d"
    PROGRESS_BG = "#21262d"
    PROGRESS_FG = "#238636"
    CHUNK_BG = "#2d5a8e"
    CHUNK_FG = "#ffffff"
    TOOLTIP_BG = "#30363d"
    MENU_BG = "#1c2330"
    MENU_HOVER = "#2a3142"
    MENU_ACTIVE = "#1f6feb"

# =========================
# TOOLTIP
# =========================
class ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, event=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 15
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip,
            text=self.text() if callable(self.text) else self.text,
            bg=Colors.TOOLTIP_BG,
            fg=Colors.TEXT_MAIN,
            justify="left",
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=7,
            font=("Segoe UI", 9),
            wraplength=280
        ).pack()

    def hide(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None

# =========================
# ROOT
# =========================
from tkinter import PhotoImage
import os

root = TkinterDnD.Tk()

ICON_PATH = r"C:\XTTS Studio\icon.png"

try:
    if os.path.isfile(ICON_PATH):
        icon = PhotoImage(file=ICON_PATH)
        root.iconphoto(True, icon)
except Exception as e:
    print(f"[ICON ERROR] {e}")

root.title("XTTS Studio")
root.geometry("1000x820")
root.minsize(800, 680)
root.configure(bg=Colors.BG_DARK)

try:
    from ctypes import windll
    #windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI вместо system DPI
except Exception:
    pass

# =========================
# LAYOUT
# =========================
main_container = tk.Frame(root, bg=Colors.BG_DARK)
main_container.pack(fill="both", expand=True, padx=8, pady=14)

left_panel = tk.Frame(main_container, bg=Colors.BG_DARK, width=260)
left_panel.pack(side="left", fill="y", padx=(0, 14))
left_panel.pack_propagate(False)

right_panel = tk.Frame(main_container, bg=Colors.BG_DARK)
right_panel.pack(side="left", fill="both", expand=True)

# =========================
# CONSOLE REDIRECT
# =========================
class ConsoleRedirect:
    def __init__(self):
        self.widget = None
        self._buffer = []

    def attach(self, widget):
        self.widget = widget
        for line in self._buffer:
            try:
                widget.after(0, self._write_to_widget, line)
            except Exception:
                pass
        self._buffer.clear()

    def _write_to_widget(self, text):
        if self.widget is None:
            return
        low = text.lower()
        if "error" in low or "ошибка" in low:
            tag = "error"
        elif "warn" in low or "warning" in low:
            tag = "warn"
        elif "done" in low or "готово" in low or "✔" in text:
            tag = "ok"
        else:
            tag = "info"
        self.widget.insert(tk.END, text, tag)
        self.widget.see(tk.END)

    def write(self, text):
        if self.widget is None:
            self._buffer.append(text)
        else:
            try:
                self.widget.after(0, self._write_to_widget, text)
            except Exception:
                pass

    def flush(self):
        pass

console_redirect = ConsoleRedirect()
sys.stdout = console_redirect
sys.stderr = console_redirect

# =========================
# PYGAME
# =========================
PYGAME_OK = False
try:
    pygame.mixer.init()
    PYGAME_OK = True
except Exception as e:
    PYGAME_OK = False
    print(f"[GUI] pygame.mixer init failed: {e}")

# =========================
# STATE
# =========================
current_pos = 0
play_btn = None

ref_var = tk.StringVar()
status_var = tk.StringVar(value="🔄 Инициализация модели...")
stage_var = tk.StringVar(value="STARTUP")
progress_value = tk.IntVar(value=0)
console_visible = tk.BooleanVar(value=True)

lang_var = tk.StringVar(value="auto")
quality_var = tk.StringVar(value="Высокое качество")

current_task: Optional[Task] = None
voice_map = {}
current_text_snapshot = ""
model_ready = False

voice_manager = VoiceManager(BACKUP_DIR)
voice_manager.scan_voices()

# =========================
# WIDGETS
# =========================
def create_card(parent, title="", bg=Colors.BG_CARD, padx=10, pady=10):
    card = tk.Frame(parent, bg=bg, highlightthickness=0)
    if title:
        tk.Label(
            card,
            text=title,
            bg=bg,
            fg=Colors.TEXT_MAIN,
            font=("Segoe UI", 11, "bold"),
            anchor="w"
        ).pack(fill="x", padx=padx, pady=(pady, 5))
    return card

def create_button(parent, text, command, bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
                  active_bg=Colors.BG_HOVER, width=None, height=1, font_size=10):
    is_bold = "ГЕНЕРИРОВАТЬ" in text or "ОТМЕНА" in text
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg, fg=fg,
        activebackground=active_bg, activeforeground=fg,
        relief="flat", borderwidth=0,
        font=("Segoe UI", font_size, "bold" if is_bold else "normal"),
        cursor="hand2",
        padx=4, pady=2
    )
    if width:
        btn.config(width=width)
    if height:
        btn.config(height=height)

    def on_enter(e):
        btn.config(bg=active_bg)
    def on_leave(e):
        btn.config(bg=bg)
    btn.bind("<Enter>", on_enter, add="+")
    btn.bind("<Leave>", on_leave, add="+")
    return btn

def create_entry(parent, textvariable, bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN):
    return tk.Entry(
        parent,
        textvariable=textvariable,
        bg=bg, fg=fg,
        insertbackground=Colors.TEXT_MAIN,
        relief="flat", borderwidth=0,
        font=("Segoe UI", 10),
        highlightthickness=1,
        highlightbackground=Colors.BORDER,
        highlightcolor=Colors.ACCENT
    )

# =========================
# SAFE UI UPDATE
# =========================
def set_status(text):
    root.after(0, lambda: status_var.set(text))

def set_stage(text):
    root.after(0, lambda: stage_var.set(text))

def set_progress(value):
    try:
        value = max(0, min(100, int(value)))
    except Exception:
        return
    root.after(0, lambda: progress_value.set(value))

def lock_textbox():
    try:
        text_box.config(state="disabled")
    except Exception:
        pass

def unlock_textbox():
    try:
        text_box.config(state="normal")
    except Exception:
        pass

# =========================
# HELPERS
# =========================
def clean_path(p: str) -> str:
    p = (p or "").strip()
    try:
        if p.startswith("{") or "} {" in p:
            parts = root.tk.splitlist(p)
            if parts:
                p = parts[0]
    except Exception:
        pass
    p = p.strip("{}")
    p = p.replace("/", "\\")
    return ntpath.normpath(p)

def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)

    text = text.replace("—", ". ")

    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r",{2,}", ",", text)

    # запятая между аббревиатурами → точка
    text = re.sub(r"([A-ZА-Я]{2,}),\s*([A-ZА-Я]{2,})", r"\1. \2", text)

    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{2,}", "\n", text)

    text = re.sub(r"(\.)([A-ZА-ЯЁ])", r"\1 \2", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text

def set_textbox_content(content: str):
    unlock_textbox()
    text_box.delete("1.0", tk.END)
    if content:
        text_box.insert("1.0", content)
        text_box.config(fg=Colors.TEXT_MAIN)
    else:
        show_placeholder()

def clear_chunk_highlight():
    try:
        text_box.tag_remove("chunk_highlight", "1.0", tk.END)
    except Exception:
        pass

def open_outputs_folder():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    try:
        os.startfile(OUTPUT_DIR)
    except Exception:
        messagebox.showinfo("Папка", OUTPUT_DIR)

# =========================
# QUEUE
# =========================
def update_queue_view():
    try:
        queue_listbox.delete(0, tk.END)
        status_icons = {
            "queued": "⏳", "running": "▶", "done": "✔",
            "error": "❌", "cancelled": "⛔",
        }
        for task in task_manager.get_queue():
            icon = status_icons.get(task.status, "•")
            name = task.text[:30].replace("\n", " ")
            queue_listbox.insert(tk.END, f"{icon} {name} | {task.progress}%")
    except Exception:
        pass

def queue_autorefresh():
    update_queue_view()
    root.after(500, queue_autorefresh)

# =========================
# UI CALLBACK
# =========================
def on_task_update(data):
    if data is None:
        return

    if isinstance(data, dict) and data.get("stage") == "queue_update":
        root.after(0, update_queue_view)
        return

    if isinstance(data, dict) and data.get("stage") == "chunk":
        start = data.get("chunk_start", 0)
        end = data.get("chunk_end", 0)
        root.after_idle(lambda s=start, e=end: _highlight_chunk(s, e))
        return

    if isinstance(data, dict):
        return

    task = data
    set_progress(task.progress)

    if task.status == "queued":
        set_status("⏳ В очереди...")
        set_stage("QUEUED")
    elif task.status in ("running", "generate", "reference", "normalize", "chunking", "merge"):
        set_status(f"🔄 Генерация... {task.progress}%")
        set_stage("RUNNING")
    elif task.status == "done":
        set_stage("DONE")
        unlock_textbox()
        if task.stats:
            t = task.stats.get("time_sec", 0)
            mins, secs = divmod(t, 60)
            time_str = f"{mins}м {secs}с" if mins else f"{secs}с"
            set_status(
                f"✅ Готово | {time_str} | "
                f"Чанков: {task.stats.get('chunks', '?')} | "
                f"Голос: {task.stats.get('voice', '?')}"
            )
        else:
            set_status("✅ Готово")
        root.after(0, lambda: _on_task_done(task))
    elif task.status == "error":
        set_stage("ERROR")
        unlock_textbox()
        set_status("❌ Ошибка")
        root.after(0, lambda: _on_task_error(task))
    elif task.status == "cancelled":
        global current_task
        if current_task and current_task.id == task.id:
            current_task = None
        clear_chunk_highlight()
        unlock_textbox()
        set_stage("IDLE")
        set_status("⛔ Отменено")
        set_progress(0)
    else:
        set_stage(task.status.upper())
        set_status(f"{task.status}... {task.progress}%")

def _highlight_chunk(start, end):
    try:
        clear_chunk_highlight()
        if start is None or end is None:
            return
        start = int(start)
        end = int(end)
        visible_text = text_box.get("1.0", "end-1c")
        text_len = len(visible_text)
        start = max(0, min(start, text_len))
        end = max(0, min(end, text_len))
        if end <= start:
            return
        start_idx = f"1.0+{start} chars"
        end_idx = f"1.0+{end} chars"
        text_box.tag_add("chunk_highlight", start_idx, end_idx)
        text_box.tag_configure("chunk_highlight",
                               background=Colors.CHUNK_BG,
                               foreground=Colors.CHUNK_FG)
        text_box.tag_raise("chunk_highlight")
        text_box.see(start_idx)
    except Exception as e:
        print(f"[Highlight error]: {e}")

def _on_task_done(task: Task):
    global current_task
    if current_task and current_task.id == task.id:
        current_task = None
    clear_chunk_highlight()
    unlock_textbox()
    refresh_voice_list()
    messagebox.showinfo("✅ Готово", f"Файл сохранён:\n{task.output_path}")

def _on_task_error(task: Task):
    global current_task
    if current_task and current_task.id == task.id:
        current_task = None
    clear_chunk_highlight()
    unlock_textbox()
    write_log(task.error or "Unknown error")
    messagebox.showerror("❌ XTTS Error", task.error or "Неизвестная ошибка")

# =========================
# TASK MANAGER
# =========================
task_manager = TaskManager(ui_callback=on_task_update)
task_manager.start()

# =========================
# MODEL PRELOAD
# =========================
def _preload_model():
    global model_ready
    try:
        from engine.tts_runner import get_tts
        set_stage("STARTUP")
        set_status("🔄 Инициализация модели...")
        get_tts()
        model_ready = True
        set_stage("READY")
        set_status("✅ Модель готова")
    except Exception as e:
        print(f"[Preload] Модель будет загружена при генерации. ({e})")
        model_ready = False
        set_stage("IDLE")
        set_status("⏳ Ожидание...")

def start_preload_thread():
    threading.Thread(target=_preload_model, daemon=True).start()

# =========================
# REFERENCE
# =========================
def pick_reference():
    path = filedialog.askopenfilename(
        initialdir=REF_DIR,
        title="Выбор reference",
        filetypes=[("Audio", "*.wav *.mp3")]
    )
    if path:
        ref_var.set(path)

def pick_backup_reference():
    path = filedialog.askopenfilename(
        initialdir=BACKUP_DIR,
        title="Выбор reference из библиотеки",
        filetypes=[("Audio", "*.wav *.mp3")]
    )
    if path:
        ref_var.set(path)

def play_reference():
    global play_btn, current_pos
    if not PYGAME_OK:
        messagebox.showwarning("⚠️ Аудио", "Аудио-устройство недоступно")
        return
    ref = clean_path(ref_var.get().strip())
    if not ref or not os.path.isfile(ref):
        messagebox.showwarning("⚠️ Референс", "Сначала выберите референс")
        return
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()
        play_btn.config(text="▶")
        current_pos = 0
        return
    try:
        pygame.mixer.music.load(ref)
        pygame.mixer.music.play(start=current_pos)
        play_btn.config(text="⏸")
        _check_playback()
    except Exception as e:
        play_btn.config(text="▶")
        messagebox.showerror("❌ Ошибка", f"Не удалось воспроизвести: {e}")

def _check_playback():
    global current_pos
    if not PYGAME_OK:
        return
    try:
        if pygame.mixer.music.get_busy():
            current_pos += 0.2
            root.after(200, _check_playback)
        else:
            play_btn.config(text="▶")
            current_pos = 0
    except Exception:
        play_btn.config(text="▶")
        current_pos = 0

def seek_forward():
    global current_pos
    if not PYGAME_OK:
        return
    ref = clean_path(ref_var.get().strip())
    if not ref or not os.path.isfile(ref):
        return
    try:
        current_pos += 5
        pygame.mixer.music.stop()
        pygame.mixer.music.load(ref)
        pygame.mixer.music.play(start=current_pos)
        play_btn.config(text="⏸")
        _check_playback()
    except Exception as e:
        messagebox.showerror("❌ Ошибка", f"Не удалось перемотать: {e}")

def seek_back():
    global current_pos
    if not PYGAME_OK:
        return
    ref = clean_path(ref_var.get().strip())
    if not ref or not os.path.isfile(ref):
        return
    try:
        current_pos = max(0, current_pos - 5)
        pygame.mixer.music.stop()
        pygame.mixer.music.load(ref)
        pygame.mixer.music.play(start=current_pos)
        play_btn.config(text="⏸")
        _check_playback()
    except Exception as e:
        messagebox.showerror("❌ Ошибка", f"Не удалось перемотать: {e}")

# =========================
# VOICES
# =========================
def refresh_voice_list():
    voice_manager.scan_voices()
    voice_listbox.delete(0, tk.END)
    voice_map.clear()
    for voice in voice_manager.list_voices():
        voice_map[voice.name] = voice
        voice_listbox.insert(tk.END, f"🎤 {voice.name}")

def on_voice_select(event):
    selection = voice_listbox.curselection()
    if not selection:
        return
    raw_name = voice_listbox.get(selection[0])
    voice_name = raw_name.replace("🎤 ", "").strip()
    voice = voice_map.get(voice_name) or voice_manager.get_voice(voice_name)
    if not voice:
        return
    try:
        voice_manager.set_active(voice_name)
    except Exception:
        pass
    normalized_file = getattr(voice, "normalized", None)
    voice_path = getattr(voice, "path", None)
    if normalized_file and voice_path:
        normalized_path = os.path.join(voice_path, normalized_file)
        if os.path.isfile(normalized_path):
            ref_var.set(normalized_path)
            if PYGAME_OK and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            if PYGAME_OK:
                root.after(100, play_reference)
    set_status(f"🎤 Активный голос: {voice_name}")

# =========================
# PLACEHOLDER
# =========================
PLACEHOLDER = "Перетащите текстовый файл или введите текст..."

def show_placeholder():
    unlock_textbox()
    if not text_box.get("1.0", "end-1c"):
        text_box.insert("1.0", PLACEHOLDER)
        text_box.config(fg=Colors.TEXT_DIM)

def hide_placeholder(event=None):
    if text_box.get("1.0", "end-1c") == PLACEHOLDER:
        text_box.delete("1.0", tk.END)
        text_box.config(fg=Colors.TEXT_MAIN)

# =========================
# TEXT HELPERS
# =========================
def paste_safe(event=None):
    hide_placeholder()
    try:
        text_box.insert(tk.INSERT, normalize_text(root.clipboard_get()))
        text_box.config(fg=Colors.TEXT_MAIN)
    except Exception:
        pass
    return "break"

def load_txt():
    hide_placeholder()
    path = filedialog.askopenfilename(filetypes=[("TXT", "*.txt")])
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = normalize_text(f.read())
            set_textbox_content(content)
        except Exception:
            write_log(traceback.format_exc())
            messagebox.showerror("❌ Ошибка", "Не удалось открыть файл")

def show_text_context_menu(event):
    hide_placeholder()
    menu = tk.Menu(
        root, tearoff=0,
        bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
        activebackground=Colors.BG_HOVER, activeforeground=Colors.TEXT_MAIN,
        relief="flat", borderwidth=1
    )
    menu.add_command(label="Копировать", command=lambda: (
        root.clipboard_clear(),
        root.clipboard_append(text_box.get(tk.SEL_FIRST, tk.SEL_LAST))
    ) if text_box.tag_ranges(tk.SEL) else None)
    menu.add_command(label="Вставить", command=paste_safe)
    menu.add_command(label="Вырезать", command=lambda: (
        root.clipboard_clear(),
        root.clipboard_append(text_box.get(tk.SEL_FIRST, tk.SEL_LAST)),
        text_box.delete(tk.SEL_FIRST, tk.SEL_LAST)
    ) if text_box.tag_ranges(tk.SEL) else None)
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=lambda: text_box.tag_add(tk.SEL, "1.0", tk.END))
    menu.add_command(label="Очистить", command=lambda: (
        text_box.delete("1.0", tk.END),
        text_box.config(fg=Colors.TEXT_MAIN)
    ))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()

def paste_clipboard():
    hide_placeholder()
    try:
        text_box.insert("insert", normalize_text(root.clipboard_get()))
        text_box.config(fg=Colors.TEXT_MAIN)
    except Exception:
        messagebox.showwarning("⚠️ Буфер", "Нет текста")

def drop_handler(event):
    hide_placeholder()
    path = clean_path(event.data)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = normalize_text(f.read())
            set_textbox_content(content)
        except Exception:
            write_log(traceback.format_exc())
            messagebox.showerror("❌ Ошибка", "Не удалось открыть файл")

# =========================
# WORD REPLACER
# =========================
def open_word_replacer():
    from engine.tts_runner import word_replacer
    win = tk.Toplevel(root)
    win.title("📖 Словарь произношений")
    win.geometry("550x450")
    win.resizable(False, False)
    win.configure(bg=Colors.BG_CARD)
    win.grab_set()

    list_frame = tk.Frame(win, bg=Colors.BG_CARD)
    list_frame.pack(fill="both", expand=True, padx=15, pady=(15, 5))
    scrollbar = tk.Scrollbar(list_frame, bg=Colors.BG_INPUT, troughcolor=Colors.BG_DARK)
    scrollbar.pack(side="right", fill="y")
    listbox = tk.Listbox(
        list_frame, yscrollcommand=scrollbar.set,
        font=("Consolas", 10), selectmode="single",
        bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
        selectbackground=Colors.ACCENT, selectforeground=Colors.TEXT_MAIN,
        relief="flat", highlightthickness=0
    )
    listbox.pack(fill="both", expand=True)
    scrollbar.config(command=listbox.yview)

    def refresh():
        listbox.delete(0, tk.END)
        for word, replacement in word_replacer.rules.items():
            listbox.insert(tk.END, f"{word}  →  {replacement}")
    refresh()

    input_frame = tk.Frame(win, bg=Colors.BG_CARD)
    input_frame.pack(fill="x", padx=15, pady=10)
    tk.Label(input_frame, text="Слово:", bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
             font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=(0, 10))
    entry_word = tk.Entry(
        input_frame, width=20, font=("Segoe UI", 10),
        bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
        insertbackground=Colors.TEXT_MAIN, relief="flat",
        highlightthickness=1, highlightbackground=Colors.BORDER
    )
    entry_word.grid(row=0, column=1, padx=5)
    tk.Label(input_frame, text="Замена:", bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
             font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=(10, 10))
    entry_replacement = tk.Entry(
        input_frame, width=20, font=("Segoe UI", 10),
        bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
        insertbackground=Colors.TEXT_MAIN, relief="flat",
        highlightthickness=1, highlightbackground=Colors.BORDER
    )
    entry_replacement.grid(row=0, column=3, padx=5)

    btn_frame_wr = tk.Frame(win, bg=Colors.BG_CARD)
    btn_frame_wr.pack(fill="x", padx=15, pady=(0, 15))

    def add_rule():
        word = entry_word.get().strip()
        replacement = entry_replacement.get().strip()
        if word and replacement:
            word_replacer.add_rule(word, replacement)
            entry_word.delete(0, tk.END)
            entry_replacement.delete(0, tk.END)
            refresh()

    def remove_rule():
        sel = listbox.curselection()
        if sel:
            item = listbox.get(sel[0])
            word = item.split("  →  ")[0].strip()
            word_replacer.remove_rule(word)
            refresh()

    create_button(btn_frame_wr, "➕ Добавить", add_rule, bg=Colors.BG_INPUT).pack(side="left", padx=(0, 10))
    create_button(btn_frame_wr, "🗑️ Удалить", remove_rule, bg=Colors.BG_DANGER, fg=Colors.TEXT_MAIN).pack(side="left")

# =========================
# CANCEL / GENERATE
# =========================
def cancel_task():
    global current_task
    if current_task is None:
        return
    task_manager.cancel_task(current_task.id)
    clear_chunk_highlight()
    unlock_textbox()
    set_status("⛔ Отмена задачи...")
    set_stage("CANCELLING")
    set_progress(0)

def generate():
    global current_task, current_text_snapshot
    hide_placeholder()

    try:
        if PYGAME_OK and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        if PYGAME_OK:
            pygame.mixer.music.unload()
    except Exception:
        pass

    raw_text = text_box.get("1.0", "end-1c")
    text = normalize_text(raw_text)
    ref = clean_path(ref_var.get().strip())

    if not text:
        messagebox.showerror("❌ Ошибка", "Текст пустой")
        return
    if not ref or not os.path.isfile(ref):
        messagebox.showerror("❌ Ошибка", "Выберите reference audio")
        return

    current_text_snapshot = text
    set_textbox_content(text)
    clear_chunk_highlight()
    lock_textbox()
    text_box.update_idletasks()

    quality_name = quality_var.get()
    if quality_name not in quality_params:
        quality_name = "Высокое качество"
        quality_var.set(quality_name)
    params = quality_params[quality_name]

    current_task = Task(
        text=text,
        raw_text=raw_text.strip(),
        voice=ref,
        speed=params["speed"].get(),
        language=lang_var.get(),
        quality=quality_name,
        quality_params={k: v.get() for k, v in params.items()}
    )

    set_status("📥 Добавлено в очередь...")
    set_stage("QUEUED")
    set_progress(0)
    task_manager.add_task(current_task)
    save_settings()

# =========================
# CONSOLE
# =========================
def toggle_console():
    if console_visible.get():
        console_inner.pack_forget()
        console_visible.set(False)
        toggle_btn.config(text="📋 Console ▲")
    else:
        console_inner.pack(fill="x", padx=8, pady=(0, 7))
        console_visible.set(True)
        toggle_btn.config(text="📋 Console ▼")

def show_context_menu(event):
    menu = tk.Menu(
        root, tearoff=0, bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
        activebackground=Colors.BG_HOVER, activeforeground=Colors.TEXT_MAIN,
        relief="flat", borderwidth=1
    )
    menu.add_command(
        label="Копировать",
        command=lambda: (
            root.clipboard_clear(),
            root.clipboard_append(console_text.get(tk.SEL_FIRST, tk.SEL_LAST))
        ) if console_text.tag_ranges(tk.SEL) else None
    )
    menu.add_separator()
    menu.add_command(label="🗑️ Очистить", command=clear_console)
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()

def clear_console():
    console_text.delete("1.0", tk.END)

# =========================
# LANGUAGE PICKER
# =========================
def pick_language():
    win = tk.Toplevel(root)
    win.title("🌐 Язык модели")
    win.resizable(False, False)
    win.configure(bg=Colors.BG_CARD)
    win.grab_set()

    langs = [
        ("Авто", "auto"), ("RU", "ru"), ("EN", "en"),
        ("ES", "es"), ("FR", "fr"), ("DE", "de"),
        ("IT", "it"), ("PT", "pt"), ("PL", "pl"),
        ("TR", "tr"), ("NL", "nl"), ("CS", "cs"),
        ("AR", "ar"), ("ZH", "zh-cn"), ("HU", "hu"),
        ("KO", "ko"), ("JA", "ja"), ("HI", "hi"),
    ]

    tk.Label(win, text="Выберите язык модели", bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN,
             font=("Segoe UI", 12, "bold")).pack(pady=(15, 10))
    grid = tk.Frame(win, bg=Colors.BG_CARD)
    grid.pack(padx=15, pady=(0, 15))

    for i, (label, value) in enumerate(langs):
        tk.Radiobutton(
            grid, text=label, variable=lang_var, value=value,
            indicatoron=False, width=6,
            bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
            selectcolor=Colors.ACCENT, activebackground=Colors.BG_HOVER,
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2"
        ).grid(row=i // 6, column=i % 6, padx=3, pady=3)

    tk.Button(
        win, text="✓ Закрыть", command=lambda: [win.destroy(), save_settings()],
        bg=Colors.BG_ACTIVE, fg=Colors.TEXT_MAIN, relief="flat",
        font=("Segoe UI", 10, "bold"), cursor="hand2", padx=20, pady=5
    ).pack(pady=(0, 15))

# =========================
# HELP
# =========================
def show_help():
    win = tk.Toplevel(root)
    win.title("❓ Справка")
    win.geometry("650x550")
    win.resizable(True, True)
    win.configure(bg=Colors.BG_CARD)
    win.grab_set()

    frame = tk.Frame(win, bg=Colors.BG_CARD)
    frame.pack(fill="both", expand=True, padx=15, pady=15)
    scrollbar = tk.Scrollbar(frame, bg=Colors.BG_INPUT, troughcolor=Colors.BG_DARK)
    scrollbar.pack(side="right", fill="y")
    text = tk.Text(
        frame, wrap="word", yscrollcommand=scrollbar.set,
        font=("Consolas", 12), bg=Colors.BG_DARK, fg=Colors.TEXT_MAIN,
        padx=15, pady=15, state="normal", relief="flat", highlightthickness=0
    )
    text.pack(fill="both", expand=True)
    scrollbar.config(command=text.yview)

    text.tag_configure("header", foreground=Colors.ACCENT, font=("Consolas", 11))
    text.tag_configure("symbol", foreground="#ffd600", font=("Consolas", 9))
    text.tag_configure("good", foreground=Colors.TEXT_SUCCESS)
    text.tag_configure("bad", foreground=Colors.TEXT_ERROR)
    text.tag_configure("normal", foreground=Colors.TEXT_MAIN)
    text.tag_configure("comment", foreground=Colors.TEXT_DIM)

    content = [
        ("header", "🎯 АВТОМАТИЧЕСКАЯ ОБРАБОТКА\n"),

        ("good", "Числа → слова (авто)\n"),
        ("good", "Аббревиатуры → словарь произношений\n"),
        ("good", "Пунктуационные паузы → автоматически\n"),
        ("good", "Семантические паузы → по контексту\n"),
        ("good", "Нормализация текста → автоматически\n"),
        ("good", "Удаление артефактов → автоматически\n"),

        ("header", "\n⏸️ ПАУЗЫ\n"),

        ("symbol", ". "), ("normal", " стандартная пауза\n"),
        ("symbol", ", "), ("normal", " короткая пауза\n"),
        ("symbol", "? "), ("normal", " вопросительная интонация\n"),
        ("symbol", "! "), ("normal", " восклицательная интонация\n"),
        ("symbol", "- "), ("normal", " заменяется на запятую\n"),
        ("symbol", "— "), ("normal", " нормализуется в запятую (XTTS)\n"),
        ("symbol", ": "), ("normal", " пауза перед пояснением\n"),

        ("header", "\n💬 СМЫСЛОВЫЕ ПАУЗЫ\n"),

        ("normal", "Перед: но / однако / хотя → короткая пауза\n"),
        ("normal", "После: поэтому / итак → пауза вывода\n"),
        ("normal", "Перед: важно / главное → выделение\n"),
        ("normal", "Перед: например / к примеру → пояснение\n"),
        ("comment", "Автоматическая обработка по контексту\n"),

        ("header", "\n📋 СПИСКИ\n"),

        ("good", "1. читается как первый элемент\n"),
        ("good", "2. читается как второй элемент\n"),
        ("comment", "До 20 пунктов, далее числа\n"),

        ("header", "\n🎤 РЕФЕРЕНС\n"),

        ("good", "12–15 сек, тихо, без музыки\n"),
        ("good", "нейтральная эмоция\n"),
        ("good", "автоматическое сглаживание громкости\n"),
    ]
    for tag, content_text in content:
        text.insert("end", content_text, tag)
    text.config(state="disabled")

    def close_window():
        save_settings()
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", close_window)

# =========================
# QUALITY PARAMS
# =========================
quality_params = {
    "Высокое качество": {
        "temperature": tk.DoubleVar(value=0.70),
        "top_p": tk.DoubleVar(value=0.30),
        "top_k": tk.IntVar(value=80),
        "repetition_penalty": tk.DoubleVar(value=13.0),
        "prosody_intensity": tk.DoubleVar(value=0.0),
        "trim_ms": tk.IntVar(value=100),
        "speed": tk.DoubleVar(value=1.0),
        "trim_mode": tk.StringVar(value="auto"),
    },
    "Нарратив": {
        "temperature": tk.DoubleVar(value=0.75),
        "top_p": tk.DoubleVar(value=0.25),
        "top_k": tk.IntVar(value=85),
        "repetition_penalty": tk.DoubleVar(value=18.0),
        "prosody_intensity": tk.DoubleVar(value=0.5),
        "trim_ms": tk.IntVar(value=80),
        "speed": tk.DoubleVar(value=0.9),
        "trim_mode": tk.StringVar(value="auto"),
    },
    "Динамика": {
        "temperature": tk.DoubleVar(value=0.82),
        "top_p": tk.DoubleVar(value=0.20),
        "top_k": tk.IntVar(value=100),
        "repetition_penalty": tk.DoubleVar(value=16.0),
        "prosody_intensity": tk.DoubleVar(value=1.1),
        "trim_ms": tk.IntVar(value=60),
        "speed": tk.DoubleVar(value=1.1),
        "trim_mode": tk.StringVar(value="auto"),
    },
    "Экспрессия": {
        "temperature": tk.DoubleVar(value=0.88),
        "top_p": tk.DoubleVar(value=0.30),
        "top_k": tk.IntVar(value=90),
        "repetition_penalty": tk.DoubleVar(value=14.0),
        "prosody_intensity": tk.DoubleVar(value=1.3),
        "trim_ms": tk.IntVar(value=100),
        "speed": tk.DoubleVar(value=1.0),
        "trim_mode": tk.StringVar(value="auto"),
    },
}

# =========================
# PRESET DESCRIPTIONS (для меню "Стили")
# =========================
PRESET_DESCRIPTIONS = {
    "Нарратив": "📖 Нарратив\nСпокойное, плавное чтение.\nМедленный темп, ровная интонация.\nИдеально для книг и озвучки текста\nНажмите чтобы открыть настройки.",
    "Динамика": "⚡ Динамика\nБодрый, энергичный голос.\nУскоренный темп, живые интонации.\nПодходит для рекламы и роликов\nНажмите чтобы открыть настройки.",
    "Экспрессия": "🎭 Экспрессия\nМаксимально эмоциональная подача.\nЯркие интонации и выразительность.\nДля драматичных сцен и эмоций\nНажмите чтобы открыть настройки.",
}

def open_quality_settings(preset_name):
    if preset_name not in quality_params:
        preset_name = "Высокое качество"
    win = tk.Toplevel(root)
    win.title(f"⚙ Настройки — {preset_name}")
    win.resizable(False, False)
    win.configure(bg=Colors.BG_CARD)
    win.grab_set()
    params = quality_params[preset_name]

    fields = [
        ("temperature", "Temperature", 0.1, 1.0, 0.05,
        "Случайность голоса.\n\nНизко — стабильно и ровно.\nВысоко — более живо, но менее предсказуемо."),

        ("top_p", "Top P", 0.1, 1.0, 0.05,
        "Ограничивает выбор вариантов.\n\nМеньше — стабильнее.\nБольше — естественнее."),

        ("top_k", "Top K", 10, 100, 5,
        "Сколько вариантов модель рассматривает.\n\nМеньше — чище.\nБольше — разнообразнее."),

        ("repetition_penalty", "Repetition Penalty", 1.0, 20.0, 0.5,
        "Убирает повторы.\n\nВыше — меньше артефактов.\nНиже — естественнее но рискованнее"),

        ("speed", "Скорость речи", 0.75, 2.25, 0.05,
        "Скорость озвучки.\n\nМедленно\Быстрее"),

        ("prosody_intensity", "Просодия", 0.0, 2.0, 0.1,
        "Выразительность речи.\n\n0 — ровно.\n1 — естественно.\n2 — очень эмоционально."),

        ("trim_ms", "Trim конца (мс)", 0, 300, 10,
        "Обрезка хвоста аудио.\n\nУбирает шум и затухание в конце чанка."),
    ]

    trim_scale = None
    for key, label, from_, to, res, hint in fields:
        row = tk.Frame(win, bg=Colors.BG_CARD)
        row.pack(fill="x", padx=15, pady=5)
        lbl = tk.Label(row, text=label, width=20, anchor="w",
                       bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, font=("Segoe UI", 10))
        lbl.pack(side="left")
        ToolTip(lbl, hint)

        scale = tk.Scale(
            row, variable=params[key], from_=from_, to=to, resolution=res,
            orient="horizontal", length=240,
            bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, troughcolor=Colors.BG_INPUT,
            highlightthickness=0, sliderrelief="flat", sliderlength=20, font=("Segoe UI", 9)
        )
        scale.pack(side="left", padx=(10, 5))

        tk.Label(row, textvariable=params[key], width=6,
                 bg=Colors.BG_CARD, fg=Colors.ACCENT, font=("Consolas", 9)).pack(side="left")
        if key == "trim_ms":
            trim_scale = scale

    mode_row = tk.Frame(win, bg=Colors.BG_CARD)
    mode_row.pack(fill="x", padx=15, pady=5)
    trim_lbl = tk.Label(mode_row, text="Режим Trim:", width=20, anchor="w",
                        bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, font=("Segoe UI", 10))
    trim_lbl.pack(side="left")
    ToolTip(trim_lbl, "Авто / Ручной / Выкл")

    tk.Radiobutton(mode_row, text="Авто", variable=params["trim_mode"], value="auto",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_CARD,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", 9)).pack(side="left", padx=5)
    tk.Radiobutton(mode_row, text="Ручной", variable=params["trim_mode"], value="manual",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_CARD,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", 9)).pack(side="left", padx=5)
    tk.Radiobutton(mode_row, text="Выкл", variable=params["trim_mode"], value="off",
                   bg=Colors.BG_CARD, fg=Colors.TEXT_MAIN, selectcolor=Colors.BG_CARD,
                   activebackground=Colors.BG_CARD, font=("Segoe UI", 9)).pack(side="left")

    def update_trim_state(*args):
        if trim_scale:
            try:
                if params["trim_mode"].get() == "manual":
                    trim_scale.config(state="normal", fg=Colors.TEXT_MAIN, troughcolor=Colors.BG_INPUT)
                else:
                    trim_scale.config(state="disabled", fg=Colors.TEXT_DIM, troughcolor=Colors.BG_DARK)
            except Exception:
                pass

    params["trim_mode"].trace_add("write", update_trim_state)
    update_trim_state()

    def reset():
        defaults = {
            "Высокое качество": (0.70, 0.30, 80, 13.0, 1.0, 100, "auto", 0.0),
            "Нарратив":         (0.75, 0.25, 85,  18.0, 0.9, 80, "auto", 0.5),
            "Динамика":         (0.82, 0.20, 100, 16.0, 1.1, 60, "auto", 1.1),
            "Экспрессия":       (0.88, 0.30, 90,  14.0, 1.0, 100, "auto", 1.3),
        }
        d = defaults.get(preset_name, (0.70, 0.30, 80, 13.0, 1.0, 80, "auto", 0.8))
        params["temperature"].set(d[0])
        params["top_p"].set(d[1])
        params["top_k"].set(d[2])
        params["repetition_penalty"].set(d[3])
        params["speed"].set(d[4])
        params["trim_ms"].set(d[5])
        params["trim_mode"].set(d[6])
        params["prosody_intensity"].set(d[7])

    btn_frame = tk.Frame(win, bg=Colors.BG_CARD)
    btn_frame.pack(fill="x", padx=15, pady=(10, 15))
    create_button(btn_frame, "🔄 Сбросить", reset, bg=Colors.BG_INPUT).pack(side="left", padx=(0, 10))
    create_button(btn_frame, "✓ Закрыть", lambda: [win.destroy(), save_settings()], bg=Colors.BG_ACTIVE).pack(side="left")

# =========================
# SETTINGS
# =========================
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings():
    data = {
        "language": lang_var.get(),
        "quality": quality_var.get(),
        "ref_path": ref_var.get(),
        "quality_params": {
            preset: {k: v.get() for k, v in params.items()}
            for preset, params in quality_params.items()
        }
    }
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def apply_settings(data):
    if not isinstance(data, dict):
        return
    if "language" in data:
        lang_var.set(data["language"])
    if "quality" in data:
        q = data["quality"]
        quality_var.set(q if q in quality_params else "Высокое качество")
    if "ref_path" in data:
        path = data["ref_path"]
        if path and os.path.isfile(path):
            ref_var.set(path)
    if "quality_params" in data:
        for preset, params in data["quality_params"].items():
            if preset in quality_params:
                for key, value in params.items():
                    if key in quality_params[preset]:
                        try:
                            quality_params[preset][key].set(value)
                        except Exception:
                            pass

# =========================
# LEFT PANEL
# =========================
header_frame = tk.Frame(left_panel, bg=Colors.BG_DARK)
header_frame.pack(fill="x", pady=(0, 8))

title_row = tk.Frame(header_frame, bg=Colors.BG_DARK)
title_row.pack(anchor="w")

tk.Label(
    title_row,
    text="XTTS Studio",
    bg=Colors.BG_DARK,
    fg=Colors.TEXT_MAIN,
    font=("Segoe UI", 16, "bold")
).pack(side="left", padx=(4, 0))

tk.Label(
    header_frame,
    text=" by EXIZ10TION",
    bg=Colors.BG_DARK,
    fg=Colors.TEXT_DIM,
    font=("Segoe UI", 9)
).pack(anchor="w")
left_panel.update_idletasks()


# Reference
ref_card = create_card(left_panel, "🎤 Голос-референс")
ref_card.pack(fill="x", pady=(0, 8))
create_entry(ref_card, ref_var).pack(fill="x", padx=10, pady=(3, 7))
ref_btn_row = tk.Frame(ref_card, bg=Colors.BG_CARD)
ref_btn_row.pack(fill="x", padx=10, pady=(0, 7))
create_button(ref_btn_row, "📁 Выбрать", pick_reference, bg=Colors.BG_INPUT).pack(side="left")
tk.Label(ref_card, text="✅ Конвертирован в WAV\n✅ Обрезан\n✅ Нормализован\n✅ Сохранён в библиотеку",
         bg=Colors.BG_CARD, fg=Colors.TEXT_DIM, font=("Consolas", 8), justify="left", anchor="w"
         ).pack(fill="x", padx=10, pady=(3, 7))

# Voice library
voice_card = create_card(left_panel, "📚 Библиотека голосов")
voice_card.pack(fill="x", pady=(0, 8))

voice_listbox = tk.Listbox(
    voice_card, height=6,
    bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
    selectbackground=Colors.ACCENT, selectforeground=Colors.TEXT_MAIN,
    relief="flat", highlightthickness=0, font=("Segoe UI", 10),
    activestyle="none", exportselection=False
)
voice_listbox.pack(fill="both", padx=10, pady=3)
voice_listbox.bind("<<ListboxSelect>>", on_voice_select)

voice_btn_row = tk.Frame(voice_card, bg=Colors.BG_CARD)
voice_btn_row.pack(fill="x", padx=10, pady=(0, 7))
lib_btn = create_button(voice_btn_row, "📂", pick_backup_reference, bg=Colors.BG_INPUT, width=3)
lib_btn.pack(side="left", padx=(0, 3))
ToolTip(lib_btn, "Выбрать голос из библиотеки")
create_button(voice_btn_row, "⏪", seek_back, bg=Colors.BG_INPUT, width=3).pack(side="left", padx=(0, 3))
play_btn = create_button(voice_btn_row, "▶", play_reference, bg=Colors.BG_ACTIVE, width=3)
play_btn.pack(side="left", padx=(0, 3))
create_button(voice_btn_row, "⏩", seek_forward, bg=Colors.BG_INPUT, width=3).pack(side="left")

# Queue
queue_card = create_card(left_panel, "📋 Очередь задач")
queue_card.pack(fill="x", pady=(0, 8))

queue_listbox = tk.Listbox(
    queue_card, height=5,
    bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN,
    selectbackground=Colors.ACCENT, selectforeground=Colors.TEXT_MAIN,
    relief="flat", highlightthickness=0, font=("Consolas", 8),
    activestyle="none", exportselection=False
)
queue_listbox.pack(fill="x", padx=10, pady=(3, 7))

# =========================
# CONSOLE (MOVED TO LEFT PANEL UNDER QUEUE)
# =========================
console_card = create_card(left_panel, "")
console_card.pack(fill="x", pady=(0, 8), after=queue_card)

console_header = tk.Frame(console_card, bg=Colors.BG_CARD)
console_header.pack(fill="x", padx=8, pady=(7, 3))
toggle_btn = create_button(console_header, "📋 Console ▼", toggle_console, bg=Colors.BG_INPUT)
toggle_btn.pack(side="left")
create_button(console_header, "🗑️ Очистить", clear_console, bg=Colors.BG_INPUT).pack(side="right")

console_inner = tk.Frame(console_card, bg=Colors.BG_CARD)
console_inner.pack(fill="x", padx=8, pady=(0, 7))

console_text = tk.Text(
    console_inner, height=9,
    bg=Colors.BG_DARK, fg=Colors.TEXT_MAIN,
    font=("Consolas", 9,), state="normal", wrap="word", cursor="arrow",
    relief="flat", highlightthickness=1, highlightbackground=Colors.BORDER,
    padx=10, pady=10
)
console_text.bind("<Control-c>", lambda e: (
    root.clipboard_clear(),
    root.clipboard_append(console_text.get(tk.SEL_FIRST, tk.SEL_LAST)),
    "break"
)[-1] if console_text.tag_ranges(tk.SEL) else "break")
console_text.bind("<Control-C>", lambda e: (
    root.clipboard_clear(),
    root.clipboard_append(console_text.get(tk.SEL_FIRST, tk.SEL_LAST)),
    "break"
)[-1] if console_text.tag_ranges(tk.SEL) else "break")

console_scroll = tk.Scrollbar(console_inner, command=console_text.yview,
                              bg=Colors.BG_INPUT, troughcolor=Colors.BG_DARK)
console_text.configure(yscrollcommand=console_scroll.set)
console_scroll.pack(side="right", fill="y")
console_text.pack(fill="both", expand=True)
console_text.tag_configure("error", foreground=Colors.TEXT_ERROR)
console_text.tag_configure("warn", foreground=Colors.TEXT_WARNING)
console_text.tag_configure("ok", foreground=Colors.TEXT_SUCCESS)
console_text.tag_configure("info", foreground=Colors.TEXT_MAIN)
console_redirect.attach(console_text)
console_text.bind("<Button-3>", show_context_menu)

# Spacer
tk.Frame(left_panel, bg=Colors.BG_DARK).pack(fill="both", expand=True)

# =========================
# RIGHT PANEL
# =========================

# =========================
# STATUS BAR (MOVED TO TOP, REPLACES SYSTEM STATE)
# =========================
status_frame = tk.Frame(right_panel, bg=Colors.BG_CARD)
status_frame.pack(fill="x", pady=(0, 10))

style = ttk.Style()
style.theme_use("clam")
style.configure("Horizontal.TProgressbar",
                background=Colors.PROGRESS_FG, troughcolor=Colors.PROGRESS_BG,
                borderwidth=0, thickness=8)
ttk.Progressbar(
    status_frame, orient="horizontal", mode="determinate", maximum=100,
    variable=progress_value, style="Horizontal.TProgressbar"
).pack(fill="x", padx=10, pady=(10, 5))

tk.Label(status_frame, textvariable=status_var, anchor="w", bg=Colors.BG_CARD,
         fg=Colors.TEXT_MAIN, font=("Segoe UI", 10)).pack(fill="x", padx=10, pady=(0, 10))


# Text
text_card = create_card(right_panel, "📝 Текст")
text_card.pack(fill="both", expand=True, pady=(0, 10))
text_box = tk.Text(
    text_card,
    bg=Colors.BG_INPUT, fg=Colors.TEXT_MAIN, insertbackground=Colors.TEXT_MAIN,
    relief="flat", highlightthickness=0, font=("Consolas", 11),
    padx=10, pady=10, wrap="word", undo=True
)
text_box.pack(fill="both", expand=True, padx=10, pady=7)
text_box.bind("<FocusIn>", hide_placeholder)
text_box.bind("<FocusOut>", lambda e: show_placeholder())
text_box.drop_target_register(DND_FILES)
text_box.dnd_bind("<<Drop>>", drop_handler)
text_box.bind("<Button-3>", show_text_context_menu)
text_box.bind("<Control-v>", paste_safe, add=False)
text_box.bind("<Control-V>", paste_safe, add=False)
text_box.tag_configure("chunk_highlight", background=Colors.CHUNK_BG, foreground=Colors.CHUNK_FG)
show_placeholder()

# 1-я строка действий
text_btn_frame = tk.Frame(text_card, bg=Colors.BG_CARD)
text_btn_frame.pack(fill="x", padx=10, pady=(0, 4))
create_button(text_btn_frame, "📁 Загрузить", load_txt, bg=Colors.BG_INPUT).pack(side="left", padx=(0, 5))
create_button(text_btn_frame, "📋 Вставить", paste_clipboard, bg=Colors.BG_INPUT).pack(side="left", padx=(0, 5))
create_button(text_btn_frame, "🗑️ Очистить", lambda: [set_textbox_content("")], bg=Colors.BG_INPUT).pack(side="left", padx=(0, 5))
create_button(text_btn_frame, "📖 Словарь", open_word_replacer, bg=Colors.BG_INPUT).pack(side="left", padx=(0, 5))
create_button(text_btn_frame, "🎵 Аудио", open_outputs_folder, bg=Colors.BG_INPUT).pack(side="left")

# =========================
# 2-я строка действий: Язык/Справка слева, Стили/Высокое качество справа
# =========================
options_frame = tk.Frame(text_card, bg=Colors.BG_CARD)
options_frame.pack(fill="x", padx=10, pady=(0, 7))

# Левая часть (язык / справка)
left_opts = tk.Frame(options_frame, bg=Colors.BG_CARD)
left_opts.pack(side="left")
lang_btn = create_button(left_opts, "🌐 Язык", pick_language, bg=Colors.BG_INPUT)
lang_btn.pack(side="left", padx=(0, 5))
ToolTip(lang_btn, lambda: f"Текущий язык: {lang_var.get()}\nМожно менять акцент")
create_button(left_opts, "❓ Справка", show_help, bg=Colors.BG_INPUT).pack(side="left")

# Правая часть (стили / высокое качество)
right_opts = tk.Frame(options_frame, bg=Colors.BG_CARD)
right_opts.pack(side="right")

PRESET_HINT = "Режим по умолчанию.\nДвойной клик — открыть доп. параметры."
STYLES_HINT = "Открыть список стилей:\nНарратив / Динамика / Экспрессия.\nМногое зависит от референса"

# --- Кнопка "Стили" — открывает popup-меню с пресетами (ОТКРЫВАЕТСЯ ВВЕРХ) ---
def open_styles_menu(event=None):
    # Создаём кастомное popup
    menu = tk.Toplevel(root)
    menu.wm_overrideredirect(True)
    menu.configure(bg=Colors.MENU_BG, padx=4, pady=4)

    presets = [
        ("📖 Нарратив", "Нарратив"),
        ("⚡ Динамика", "Динамика"),
        ("🎭 Экспрессия", "Экспрессия"),
    ]

    default_desc = "Наведите на пресет —\nздесь появится его описание."

    def close_menu():
        try:
            menu.destroy()
        except Exception:
            pass

    def select_preset(name):
        quality_var.set(name)
        save_settings()
        # НЕ закрываем меню при одинарном клике, чтобы работал двойной

    def select_and_open(name):
        quality_var.set(name)
        save_settings()
        close_menu()
        open_quality_settings(name)

    # Создаём пункты пресетов
    for label, value in presets:
        is_active = (quality_var.get() == value)
        item_bg = Colors.MENU_ACTIVE if is_active else Colors.MENU_BG
        item = tk.Label(
            menu,
            text=label,
            bg=item_bg,
            fg=Colors.TEXT_MAIN,
            font=("Segoe UI", 10, "bold" if is_active else "normal"),
            padx=10, pady=5,
            anchor="w",
            cursor="hand2"
        )
        item.pack(fill="x", pady=1)

        def on_enter(e, w=item, active=is_active, name=value):
            if not active:
                w.config(bg=Colors.MENU_HOVER)
            desc_label.config(text=PRESET_DESCRIPTIONS.get(name, default_desc))
        def on_leave(e, w=item, active=is_active):
            if not active:
                w.config(bg=Colors.MENU_BG)

        item.bind("<Enter>", on_enter)
        item.bind("<Leave>", on_leave)
        # Одинарный клик - выбор
        item.bind("<Button-1>", lambda e, n=value: select_preset(n))
        # Двойной клик - выбор + открытие настроек
        item.bind("<Double-Button-1>", lambda e, n=value: select_and_open(n))

    # Разделитель
    sep = tk.Frame(menu, bg=Colors.BORDER, height=1)
    sep.pack(fill="x", padx=4, pady=(4, 4))

    # Описание пресета (внизу самого меню)
    desc_label = tk.Label(
        menu,
        text=default_desc,
        bg=Colors.MENU_BG,
        fg=Colors.TEXT_DIM,
        font=("Segoe UI", 8),
        justify="left",
        anchor="w",
        wraplength=200,
        padx=12, pady=6
    )
    desc_label.pack(fill="x")

    # Сбрасываем описание, когда курсор уходит с области описания
    def desc_leave(e):
        desc_label.config(text=default_desc)
    desc_label.bind("<Enter>", lambda e: None)
    desc_label.bind("<Leave>", desc_leave)

    # Позиционируем меню ВВЕРХ от кнопки
    menu.update_idletasks()
    menu_w = menu.winfo_reqwidth()
    menu_h = menu.winfo_reqheight()
    x = styles_btn.winfo_rootx()
    y = styles_btn.winfo_rooty() - menu_h - 4
    if y < 0:
        # если не помещается вверху — открываем вниз
        y = styles_btn.winfo_rooty() + styles_btn.winfo_height() + 4
    menu.wm_geometry(f"+{x}+{y}")

    # Закрытие при клике вне меню
    def click_outside(e):
        try:
            wx, wy = menu.winfo_rootx(), menu.winfo_rooty()
            ww, wh = menu.winfo_width(), menu.winfo_height()
            if not (wx <= e.x_root <= wx + ww and wy <= e.y_root <= wy + wh):
                close_menu()
                root.unbind_all("<Button-1>")
        except Exception:
            close_menu()

    # Привязываем глобальный обработчик с задержкой
    root.after(50, lambda: root.bind_all("<Button-1>", click_outside, add="+"))
    menu.bind("<FocusOut>", lambda e: close_menu())

styles_btn = create_button(right_opts, "🎨 Стили ▾", open_styles_menu, bg=Colors.BG_INPUT)
styles_btn.pack(side="left", padx=(0, 5))
ToolTip(styles_btn, STYLES_HINT)

# Кнопка "Высокое качество"
def studio_click():
    quality_var.set("Высокое качество")
    save_settings()

def studio_double(e):
    quality_var.set("Высокое качество")
    save_settings()
    open_quality_settings("Высокое качество")

studio_btn = tk.Button(
    right_opts,
    text="⭐ Высокое качество",
    command=studio_click,
    bg=Colors.BG_ACTIVE,
    fg=Colors.TEXT_MAIN,
    activebackground=Colors.BG_HOVER,
    activeforeground=Colors.TEXT_MAIN,
    relief="flat",
    borderwidth=0,
    font=("Segoe UI", 10, "bold"),
    cursor="hand2",
    padx=8, pady=5
)
studio_btn.pack(side="left")
studio_btn.bind("<Double-Button-1>", studio_double)
ToolTip(studio_btn, PRESET_HINT)

def update_quality_buttons(*args):
    q = quality_var.get()
    if q == "Высокое качество":
        studio_btn.config(bg=Colors.BG_ACTIVE)
        styles_btn.config(bg=Colors.BG_INPUT)
        styles_btn.config(text="🎨 Стили ▾")
    else:
        studio_btn.config(bg=Colors.BG_INPUT)
        emoji = {"Нарратив": "📖", "Динамика": "⚡", "Экспрессия": "🎭"}.get(q, "🎨")
        styles_btn.config(bg=Colors.BG_ACTIVE, text=f"{emoji} {q} ▾")

quality_var.trace_add("write", update_quality_buttons)
update_quality_buttons()

# Action buttons
action_frame = tk.Frame(right_panel, bg=Colors.BG_DARK)
action_frame.pack(fill="x", pady=(0, 10))
create_button(action_frame, "🚀 ГЕНЕРИРОВАТЬ", generate,
              bg=Colors.BG_ACTIVE, fg=Colors.TEXT_MAIN, height=2
              ).pack(side="left", fill="x", expand=True, padx=(0, 5))
create_button(action_frame, "⛔ ОТМЕНА", cancel_task,
              bg=Colors.BG_DANGER, fg=Colors.TEXT_MAIN, height=2
              ).pack(side="left", fill="x", expand=True)

# =========================
# LAUNCH
# =========================
apply_settings(load_settings())
refresh_voice_list()
queue_autorefresh()

root.update_idletasks()
sw = root.winfo_screenwidth()
sh = root.winfo_screenheight()
x = max(0, (sw - 1000) // 2)
y = max(0, (sh - 820) // 2)
root.geometry(f"1000x820+{x}+{y}")

root.after(150, start_preload_thread)
root.mainloop()