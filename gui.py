# -*- coding: utf-8 -*-
"""gui.py — точка входа XTTS Studio.

Только запуск интерфейса: подготовка окружения, импорт GUI-модулей,
создание главного окна и mainloop(). Вся логика вынесена в engine/
(техника) и engine/gui/ (интерфейс).
"""
import os
import sys

BASE_DIR = os.path.dirname(__file__)
SITE_PACKAGES = os.path.join(BASE_DIR, "python", "xtts_env", "Lib", "site-packages")
if os.path.exists(SITE_PACKAGES):
    sys.path.insert(0, SITE_PACKAGES)

import traceback


def _global_exception_handler(exc_type, exc_value, exc_tb):
    traceback.print_exception(exc_type, exc_value, exc_tb)
    input("Press Enter to exit...")


sys.excepthook = _global_exception_handler


OPEN_UPDATES_ON_STARTUP = False


def _show_startup_install_window(variant):
    """
    Отображает легковесное Tkinter окно установки PyTorch до того,
    как будут импортированы модули GUI и загружен PyTorch. Это гарантирует
    отсутствие блокировок DLL-файлов (PermissionError) со стороны работающего приложения.
    """
    import tkinter as tk
    from tkinter import ttk
    from tkinter import messagebox
    import threading
    import re
    
    from engine import env_setup
    import i18n
    
    win = tk.Tk()
    win.title(i18n.t("win_update_settings_title"))
    win.geometry("500x200")
    win.resizable(False, False)
    
    # Центрирование окна по центру экрана
    try:
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = (sw - 500) // 2
        y = (sh - 200) // 2
        win.geometry(f"500x200+{x}+{y}")
    except Exception:
        pass
        
    win.configure(bg="#2b2b2b")
    
    # Заголовок
    lbl_title = tk.Label(win, text=i18n.t("status_torch_setup", variant), fg="#ffffff", bg="#2b2b2b", font=("Segoe UI", 12, "bold"), justify="left")
    lbl_title.pack(padx=20, pady=(20, 5), anchor="w")
    
    # Текст статуса
    lbl_status = tk.Label(win, text="", fg="#aaaaaa", bg="#2b2b2b", font=("Segoe UI", 10), justify="left")
    lbl_status.pack(padx=20, pady=(0, 15), anchor="w")
    
    # Стилизация прогресс-бара
    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure("TProgressbar", thickness=12, troughcolor="#333333", background="#2e7d32")
    
    progress = ttk.Progressbar(win, orient="horizontal", length=460, mode="determinate", style="TProgressbar")
    progress.pack(padx=20, pady=(0, 20))
    
    # Регэкспы для парсинга вывода pip в реальном времени
    _torch_percent_re = re.compile(r"(\d{1,3})%")
    _torch_ratio_re = re.compile(r"([\d.]+)\s*/\s*([\d.]+)\s*MB")
    
    def progress_cb(line):
        line_str = line.replace("\r", "").strip()
        if not line_str:
            return
        print(f"[Torch Setup Startup] {line_str}")
        
        win.after(0, lambda: lbl_status.config(text=line_str[:80]))
        
        m_pct = _torch_percent_re.search(line_str)
        m_ratio = _torch_ratio_re.search(line_str)
        if m_pct:
            pct = int(m_pct.group(1))
            win.after(0, lambda: progress.config(value=pct))
        elif m_ratio:
            cur, total = float(m_ratio.group(1)), float(m_ratio.group(2))
            if total > 0:
                pct = int((cur / total) * 100)
                win.after(0, lambda: progress.config(value=pct))

    def _install_thread():
        try:
            status = env_setup.install_torch(progress_cb=progress_cb, resume=True, variant=variant)
            win.after(0, lambda: messagebox.showinfo(i18n.t("update_done_title"), i18n.t("torch_install_success", variant)))
        except Exception as e:
            win.after(0, lambda: messagebox.showerror(i18n.t("update_error_title"), i18n.t("torch_install_failed", str(e))))
        finally:
            win.after(0, win.destroy)
            
    threading.Thread(target=_install_thread, daemon=True).start()
    win.mainloop()


def _ensure_torch_before_startup():
    """
    КРИТИЧНО: вызывается ДО импорта engine.gui.main_window.

    main_window тянет за собой (main_window -> task_manager -> tts_runner ->
    engine.tts -> engine.tts.device) `import torch` на уровне МОДУЛЯ — то
    есть ещё на этапе импорта, до создания какого-либо окна. Если это
    сделать позже (например, в фоновом потоке предзагрузки модели), то при
    отсутствующем/битом torch приложение падает сырым traceback прямо тут,
    и никакой более поздний try/except уже не отработает — до него дело
    просто не доходит.

    Логика:
      1. Проверяем, затребован ли автоматический перезапуск для чистой переустановки
         (ключ install_variant_on_startup). Если да — устанавливаем прямо сейчас,
         до импорта torch и блокировки DLL.
      2. Проверяем, импортируется ли текущий torch (env_setup.torch_status(),
         это безопасный subprocess-check, ничего не удаляет и не ставит).
      3. Если импортируется — тихо продолжаем запуск (никаких pip-вызовов).
      4. Если НЕ импортируется (реальный сломанный кейс) — не пытаемся
         чинить автоматически: показываем пользователю понятный диалог
         "PyTorch повреждён или отсутствует..." со ссылкой на новую панель,
         и даем закрыть приложение или продолжить.
    """
    global OPEN_UPDATES_ON_STARTUP
    try:
        from engine.settings_store import load_settings, save_settings
        st = load_settings()
        
        # Если затребована безопасная переустановка после рестарта
        auto_variant = st.get("install_variant_on_startup")
        if auto_variant:
            st["install_variant_on_startup"] = None
            st["open_updates_on_startup"] = False
            save_settings(st)
            
            # Отображаем окно установки ДО импорта каких-либо модулей приложения!
            _show_startup_install_window(auto_variant)
            OPEN_UPDATES_ON_STARTUP = True
            os.environ["OPEN_UPDATES_ON_STARTUP"] = "1"
            return
            
        if st.get("open_updates_on_startup"):
            OPEN_UPDATES_ON_STARTUP = True
            os.environ["OPEN_UPDATES_ON_STARTUP"] = "1"
            st["open_updates_on_startup"] = False
            save_settings(st)
    except Exception as e:
        print(f"[Torch] Ошибка загрузки настроек автозапуска обновлений: {e}")

    if OPEN_UPDATES_ON_STARTUP:
        os.environ["OPEN_UPDATES_ON_STARTUP"] = "1"
        print("[Torch] Запущено восстановление PyTorch. Пропускаю диалоги проверок и фоновую загрузку.")
        return

    try:
        from engine import env_setup
    except Exception as e:
        print(f"[Torch] env_setup недоступен ({e}) — пропускаю проверку torch.")
        return

    print("[Torch] Проверка работоспособности PyTorch...")
    status = env_setup.torch_status()
    if status.get("installed"):
        # Если импортируется — тихо продолжаем запуск (без вызовов pip)
        # Если маркер-вариант еще не сохранен, сохраним его на основе cuda_available
        if not env_setup.get_installed_torch_variant():
            variant = "cu118" if status.get("cuda_available") else "cpu"
            env_setup._save_installed_torch_variant(variant)
        print(f"[Torch] PyTorch успешно импортирован. Продолжаю запуск.")
        return

    # Если НЕ импортируется — реальный сломанный/отсутствующий кейс.
    # Показываем понятный диалог
    print(f"[Torch] PyTorch не импортируется: {status.get('error')}")
    try:
        import i18n
        import tkinter as tk
        from tkinter import messagebox
        
        root_temp = tk.Tk()
        root_temp.withdraw()
        
        title = i18n.t("torch_broken_error_title")
        msg = i18n.t("torch_broken_error_msg")
        
        res = messagebox.askyesnocancel(title, msg, parent=root_temp)
        if res is True:
            # Пользователь выбрал "Да" (открыть настройки)
            OPEN_UPDATES_ON_STARTUP = True
            os.environ["OPEN_UPDATES_ON_STARTUP"] = "1"
        elif res is None:
            # Пользователь выбрал "Отмена" или закрыл диалог
            print("[Torch] Отмена запуска пользователем.")
            root_temp.destroy()
            sys.exit(0)
        # При "Нет" просто продолжаем запуск
        root_temp.destroy()
    except SystemExit:
        sys.exit(0)
    except Exception as e:
        print(f"[Torch] Ошибка при показе диалога: {e}")


_ensure_torch_before_startup()

from engine import updater
from engine.gui.main_window import create_main_window


def main():
    # ВАЖНО: проверка обновления — самое первое, что делает приложение.
    # Если прошлый запуск (после apply_update) не дошёл до
    # updater.confirm_update_success() внутри create_main_window(), значит
    # обновление сломало старт — файлы уже автоматически откачены здесь.
    startup_status = updater.check_startup_health()

    root = create_main_window(startup_status=startup_status)
    
    # Если был выбран переход в настройки обновлений, открываем панель
    if OPEN_UPDATES_ON_STARTUP:
        try:
            from engine.gui import updates
            # Планируем открытие окна настроек через 500мс после создания главного окна
            root.after(500, lambda: updates.open_updates_settings_window())
        except Exception as e:
            print(f"[Torch] Ошибка автооткрытия настроек: {e}")
            
    root.mainloop()


if __name__ == "__main__":
    main()
