# -*- coding: utf-8 -*-
"""engine/gui/updates.py — проверка и установка обновлений (GUI-обвязка)
(перенесено из gui.py: _do_update, check_and_update, _auto_check_update)."""
import os
import re
import json
import threading
import customtkinter as ctk
import tkinter as tk
import tkinter.messagebox as mb

from i18n import t

from engine import env_setup
from engine.gui.statusbar import set_status, set_progress, show_cancel_button, hide_cancel_button

# Внедряется из main_window: root
root = None

# Флаг отмены текущего обновления — тот же формат, что использует
# engine/local_llm_client.py и engine/updater.py (dict с ключом "cancelled").
_update_cancelled_flag = {"cancelled": False}

# Регэкспы парсинга прогресса pip для install_torch
_torch_collecting_re = re.compile(r"^Collecting\s+([A-Za-z0-9_.\-]+)")
_torch_downloading_re = re.compile(r"^Downloading\s+([A-Za-z0-9_.\-]+)")
_torch_installing_re = re.compile(r"^Installing collected packages")
_torch_percent_re = re.compile(r"(\d{1,3})%")
_torch_ratio_re = re.compile(r"([\d.]+)\s*/\s*([\d.]+)\s*MB")


def init(**deps):
    """Внедрение зависимостей из engine.gui.main_window (имена совпадают с
    именами глобальных переменных исходного gui.py)."""
    globals().update(deps)


def _cancel_current_update():
    """Вызывается по нажатию кнопки "Отмена" в статус-баре."""
    _update_cancelled_flag["cancelled"] = True


def _do_update(result):
    """Скачивает и устанавливает обновление."""
    from engine.updater import apply_update, restart
    import tkinter.messagebox as mb
    _update_cancelled_flag["cancelled"] = False
    set_status(t("status_update_download"))
    show_cancel_button(_cancel_current_update)
    def _apply():
        ok = apply_update(
            result["files"],
            sha256_map=result.get("sha256", {}),
            removed_files=result.get("removed_files", []),
            progress_callback=lambda i, t_val: set_progress(int(i / t_val * 100)),
            cancelled_flag=_update_cancelled_flag,
            commit_sha=result.get("commit_sha"),
        )
        hide_cancel_button()
        was_cancelled = _update_cancelled_flag["cancelled"]
        if ok:
            changelog = result.get("changelog", "").strip()
            msg = t("update_installed", result['remote'])
            if changelog:
                msg += t("update_changelog", changelog)
            msg += t("update_restart")
            def _notify_and_restart():
                mb.showinfo(t("update_done_title"), msg)
                restart()
            root.after(0, _notify_and_restart)
        elif was_cancelled:
            # Скачанные файлы уже удалены внутри apply_update (staging очищен),
            # рабочие файлы не тронуты — обновление отменено чисто.
            root.after(0, lambda: mb.showinfo(t("update_cancelled_title"), t("update_cancelled")))
            set_status(t("status_waiting"))
        else:
            # apply_update ничего не тронул на диске, если проверка SHA256
            # или скачивание не прошли — рабочие файлы остались как были.
            root.after(0, lambda: mb.showwarning(t("update_partial_title"), t("update_partial")))
            set_status(t("status_waiting"))
    threading.Thread(target=_apply, daemon=True).start()


def check_and_update(actual_check=False):
    """Ручная проверка (по кнопке).
    По умолчанию (при клике из внешнего UI без параметров) открывает окно настроек.
    При вызове с actual_check=True выполняет реальную проверку обновлений.
    """
    if not actual_check:
        open_updates_settings_window()
        return

    from engine.updater import check_update, REPO
    import tkinter.messagebox as mb
    set_status(t("status_update_check"))
    def _run():
        result = check_update()
        if result.get("error"):
            root.after(0, lambda: mb.showerror(t("update_error_title"), result["error"]))
            set_status(t("status_waiting"))
            return
        if result.get("needs_manual_reinstall"):
            def notify_manual():
                mb.showwarning(
                    t("update_manual_required_title"),
                    t("update_manual_required",
                      result.get("min_app_version", "?"), result['local'],
                      f"https://github.com/{REPO}/releases"),
                )
                set_status(t("status_waiting"))
            root.after(0, notify_manual)
            return
        if not result["available"]:
            root.after(0, lambda: mb.showinfo(t("update_no_title"),
                                               t("update_no_updates", result['local'])))
            set_status(t("status_waiting"))
            return
        def ask():
            changelog = result.get("changelog", "").strip()
            text = t("update_available", result['remote'], result['local'])
            if changelog:
                text += t("update_whats_new", changelog)
            text += t("update_confirm")
            confirmed = mb.askyesno(t("update_title"), text)
            if confirmed:
                _do_update(result)
            else:
                set_status(t("status_waiting"))
        root.after(0, ask)
    threading.Thread(target=_run, daemon=True).start()


def _auto_check_update():
    from engine.settings_store import load_settings
    settings = load_settings()
    if not settings.get("auto_check_updates", True):
        print("[Updater] Автоматическая проверка обновлений отключена в настройках.")
        return

    from engine.updater import check_update
    result = check_update()
    if result.get("error"):
        return
    if result.get("needs_manual_reinstall"):
        # Не дёргаем пользователя всплывающим окном при каждом автозапуске —
        # ручная переустановка не срочная, покажем только по кнопке "Проверить обновления".
        print(f"[Updater] Требуется ручная переустановка: локальная версия {result['local']} "
              f"старее минимально поддерживаемой {result.get('min_app_version')}")
        return
    if result.get("available"):
        def _notify():
            import tkinter.messagebox as mb
            changelog = result.get("changelog", "").strip()
            text = t("update_available", result['remote'], result['local'])
            if changelog:
                text += t("update_whats_new", changelog)
            text += t("update_confirm")
            if mb.askyesno(t("update_title"), text):
                _do_update(result)
        root.after(0, _notify)


class UpdateSettingsWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title(t("win_update_settings_title"))
        self.geometry("580x680")
        self.resizable(False, False)
        
        # Размещение окна по центру относительно главного окна
        if master:
            self.transient(master)
            try:
                master.update_idletasks()
                master_x = master.winfo_rootx()
                master_y = master.winfo_rooty()
                master_w = master.winfo_width()
                master_h = master.winfo_height()
                x = master_x + (master_w - 580) // 2
                y = master_y + (master_h - 680) // 2
                self.geometry(f"580x680+{x}+{y}")
            except Exception:
                pass
                
        self.grab_set()
        self.focus()
        
        # Применяем тему заголовка окна (Windows) для интеграции с Конструктором Тем
        try:
            from engine.gui import theme
            theme.set_dark_titlebar(self)
        except Exception:
            pass
        
        # Стилизация на основе темы приложения
        try:
            from engine.gui.colors import Colors
            bg_card = Colors.BG_CARD or "#2b2b2b"
            bg_input = Colors.BG_INPUT or "#333333"
            bg_hover = Colors.BG_HOVER or "#444444"
            text_main = Colors.TEXT_MAIN or "#ffffff"
            text_dim = Colors.TEXT_DIM or "#aaaaaa"
            border_color = Colors.BORDER or "#3f3f3f"
            ai_accent = Colors.AI_ACCENT or "#1f6aa5"
            bg_active = Colors.BG_ACTIVE or "#2e7d32"
        except Exception:
            bg_card = "#2b2b2b"
            bg_input = "#333333"
            bg_hover = "#444444"
            text_main = "#ffffff"
            text_dim = "#aaaaaa"
            border_color = "#3f3f3f"
            ai_accent = "#1f6aa5"
            bg_active = "#2e7d32"
            
        self.configure(fg_color=bg_card)
        
        # Настройка приятного приглушенного синего/стального оттенка для некритичных кнопок действий
        btn_color = "#2e5b82"
        
        outer_frame = ctk.CTkFrame(self, fg_color=bg_card, corner_radius=0)
        outer_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # --- СЕКЦИЯ 1: Обновления ---
        sec_updates = ctk.CTkFrame(outer_frame, fg_color=bg_input, border_width=1, border_color=border_color)
        sec_updates.pack(fill="x", pady=(0, 15), padx=5)
        
        lbl_updates_title = ctk.CTkLabel(sec_updates, text=t("section_updates"), font=ctk.CTkFont(weight="bold", size=14), text_color=text_main)
        lbl_updates_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        from engine.settings_store import load_settings, save_settings
        self.settings = load_settings()
        self.chk_var = tk.BooleanVar(value=self.settings.get("auto_check_updates", True))
        
        def on_chk_toggle():
            self.settings["auto_check_updates"] = self.chk_var.get()
            save_settings(self.settings)
            
        self.chk_auto = ctk.CTkCheckBox(sec_updates, text=t("chk_auto_check"), variable=self.chk_var, command=on_chk_toggle, text_color=text_main)
        self.chk_auto.pack(anchor="w", padx=15, pady=5)
        
        def run_manual_check():
            self.destroy() # Закрываем настройки перед началом проверки, чтобы не мешать всплывающим окнам
            check_and_update(actual_check=True)
            
        self.btn_check = ctk.CTkButton(sec_updates, text=t("btn_check_now"), command=run_manual_check, fg_color=btn_color, hover_color=bg_hover, text_color=text_main)
        self.btn_check.pack(anchor="w", padx=15, pady=(5, 15))
        
        # --- СЕКЦИЯ 2: Ускорение (CPU/GPU) ---
        sec_accel = ctk.CTkFrame(outer_frame, fg_color=bg_input, border_width=1, border_color=border_color)
        sec_accel.pack(fill="x", pady=(0, 15), padx=5)
        
        lbl_accel_title = ctk.CTkLabel(sec_accel, text=t("section_accel"), font=ctk.CTkFont(weight="bold", size=14), text_color=text_main)
        lbl_accel_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Обнаружение GPU
        gpu_info = env_setup.detect_gpu()
        gpu_vendor = gpu_info.get("vendor", "unknown").upper()
        gpu_name = gpu_info.get("name", "не определено")
        gpu_text = f"{gpu_vendor}: {gpu_name}"
        if gpu_info.get("cuda_version"):
            gpu_text += f" (CUDA: {gpu_info['cuda_version']})"
            
        lbl_gpu = ctk.CTkLabel(sec_accel, text=f"{t('lbl_detected_gpu')} {gpu_text}", text_color=text_dim, font=ctk.CTkFont(size=12))
        lbl_gpu.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_torch_var = ctk.CTkLabel(sec_accel, text="", text_color=text_dim, font=ctk.CTkFont(size=12))
        self.lbl_torch_var.pack(anchor="w", padx=15, pady=(2, 10))
        
        def update_variant_label():
            variant = env_setup.get_installed_torch_variant()
            if variant is None:
                lbl_text = t("torch_variant_not_defined")
            else:
                lbl_text = {"cu118": "NVIDIA CUDA 11.8 (GPU)", "cpu": "CPU"}.get(variant, variant)
            self.lbl_torch_var.configure(text=f"{t('lbl_current_torch')} {lbl_text}")
            
        update_variant_label()

        # Выбор предпочитаемого режима (CPU/GPU) с сохранением в settings.json
        lbl_pref = ctk.CTkLabel(sec_accel, text=t("lbl_device_preference"), text_color=text_main, font=ctk.CTkFont(size=12, weight="bold"))
        lbl_pref.pack(anchor="w", padx=15, pady=(5, 2))
        
        pref_val = self.settings.get("torch_device_preference", "gpu")
        
        # Защитная блокировка: если GPU-ускорение физически не доступно в установленной сборке,
        # предпочитаемый режим принудительно переключается на CPU.
        torch_stat = env_setup.torch_status()
        if pref_val == "gpu" and not torch_stat.get("cuda_available"):
            pref_val = "cpu"
            self.settings["torch_device_preference"] = "cpu"
            save_settings(self.settings)

        def on_pref_changed(value):
            if value == t("opt_pref_gpu"):
                status = env_setup.torch_status()
                # Разрешаем включать GPU только если библиотеки CUDA успешно импортированы и работают!
                if not status.get("cuda_available"):
                    gpu = env_setup.detect_gpu()
                    if gpu.get("vendor") != "nvidia":
                        mb.showerror(t("update_error_title"), t("msg_cuda_requires_nvidia"), parent=self)
                    else:
                        mb.showwarning(
                            t("update_title"),
                            "Для включения GPU-ускорения (CUDA) необходимо сначала установить совместимые библиотеки CUDA.\n\nПожалуйста, нажмите кнопку «Проверить и установить GPU-ускорение (CUDA)» ниже, чтобы запустить установку.",
                            parent=self
                        )
                    # Возвращаем переключатель в положение CPU
                    self.seg_pref.set(t("opt_pref_cpu"))
                    return
            
            pref = "gpu" if value == t("opt_pref_gpu") else "cpu"
            self.settings["torch_device_preference"] = pref
            save_settings(self.settings)
            print(f"[Torch Setup UI] Сохранен предпочитаемый режим: {pref}")

        self.seg_pref = ctk.CTkSegmentedButton(sec_accel, values=[t("opt_pref_gpu"), t("opt_pref_cpu")], command=on_pref_changed)
        self.seg_pref.pack(anchor="w", padx=15, pady=(2, 10), fill="x")
        self.seg_pref.set(t("opt_pref_gpu") if pref_val == "gpu" else t("opt_pref_cpu"))
        
        # Кнопки установки stacked вертикально во избежание обрезки текста!
        self.btn_gpu = ctk.CTkButton(sec_accel, text=t("btn_install_gpu"), command=lambda: start_install("cu118"), fg_color=bg_active, hover_color=bg_hover, text_color=text_main)
        self.btn_gpu.pack(anchor="w", fill="x", padx=15, pady=(0, 5))
        
        # Блокируем кнопку установки CUDA на аппаратном уровне, если в системе нет карты NVIDIA
        if gpu_info.get("vendor") == "nvidia":
            self.btn_gpu.configure(state="normal")
        else:
            self.btn_gpu.configure(state="disabled")
        
        self.btn_cpu = ctk.CTkButton(sec_accel, text=t("btn_install_cpu"), command=lambda: start_install("cpu"), fg_color=bg_hover, hover_color=bg_card, text_color=text_main)
        self.btn_cpu.pack(anchor="w", fill="x", padx=15, pady=(0, 10))

        # --- СЕКЦИЯ 3: Диагностика ---
        sec_diag = ctk.CTkFrame(outer_frame, fg_color=bg_input, border_width=1, border_color=border_color)
        sec_diag.pack(fill="both", expand=True, pady=0, padx=5)

        lbl_diag_title = ctk.CTkLabel(sec_diag, text=t("section_diag"), font=ctk.CTkFont(weight="bold", size=14), text_color=text_main)
        lbl_diag_title.pack(anchor="w", padx=15, pady=(10, 5))

        # Сетка сервисных кнопок внутри новой секции Диагностика
        util_frame = ctk.CTkFrame(sec_diag, fg_color="transparent")
        util_frame.pack(fill="x", padx=15, pady=(5, 5))
        util_frame.grid_columnconfigure(0, weight=1)
        util_frame.grid_columnconfigure(1, weight=1)

        def run_stop():
            self.install_was_stopped = True
            env_setup.cancel_install_torch()
            self.btn_stop.configure(state="disabled")

        def run_resume():
            checkpoint = env_setup._load_torch_checkpoint()
            variant = checkpoint.get("meta", {}).get("variant") or "cpu"
            start_install(variant, resume=True)

        def run_scan_flow():
            """Запускает полный цикл: Безопасное сканирование мусора -> Диагностика -> Подтверждение и удаление."""
            def _scan_thread():
                self.after(0, disable_buttons)
                self.after(0, lambda: self.progress_bar.set(0.01))
                self.after(0, lambda: self.lbl_progress_status.configure(text="🧹 Сканирование и перенос файлов в карантин..."))
                set_status("Сканирование мусора...")
                set_progress(10)
                try:
                    def progress_cb(line):
                        self.after(0, lambda l=line: self.lbl_progress_status.configure(text=l))
                        set_status(line)
                        
                    res = env_setup.scan_for_garbage(mode="deep", progress_cb=progress_cb)
                    
                    def after_scan():
                        enable_buttons()
                        self.progress_bar.set(1.0)
                        set_progress(100)
                        set_status("Ожидание...")
                        
                        q_count = res["quarantined_count"]
                        size_mb = res["size_mb"]
                        restored_count = res["restored_count"]
                        
                        if restored_count > 0:
                            mb.showwarning(t("msg_diagnostics_title"), t("msg_scan_and_diag_restored"), parent=self)
                        elif q_count > 0:
                            # Запрашиваем финальное подтверждение на основе Диагностики
                            confirmed = mb.askyesno(
                                t("msg_diagnostics_title"),
                                t("msg_confirm_deletion_with_size", q_count, size_mb),
                                parent=self
                            )
                            if confirmed:
                                self.lbl_progress_status.configure(text="🧹 Навсегда стираю файлы из карантина...")
                                set_status("Стирание файлов...")
                                
                                def _delete_thread():
                                    deleted = env_setup.finalize_deletion(res["quarantined_list"])
                                    self.after(0, lambda d=deleted: self.lbl_progress_status.configure(text=f"✅ Успешно очищено: {d} файлов."))
                                    self.after(0, lambda d=deleted: mb.showinfo(t("update_done_title"), f"✅ Очистка успешно завершена!\nУдалено навсегда: {d} файлов.", parent=self))
                                    set_status("Ожидание...")
                                    
                                threading.Thread(target=_delete_thread, daemon=True).start()
                            else:
                                self.lbl_progress_status.configure(text="📁 Файлы сохранены в карантине.")
                        else:
                            mb.showinfo(t("update_done_title"), "Мусорные файлы не обнаружены.", parent=self)
                            self.lbl_progress_status.configure(text="")
                            
                    self.after(0, after_scan)
                except Exception as e:
                    def failed_done(err_msg=str(e)):
                        enable_buttons()
                        self.progress_bar.set(0.0)
                        set_progress(0)
                        set_status("Ожидание...")
                        self.lbl_progress_status.configure(text=f"❌ Ошибка: {err_msg}")
                        mb.showerror(t("update_error_title"), f"Не удалось выполнить сканирование:\n{err_msg}", parent=self)
                    self.after(0, failed_done)
                    
            threading.Thread(target=_scan_thread, daemon=True).start()

        def run_diagnostics():
            self.lbl_progress_status.configure(text="🔍 Выполняю диагностику...")
            self.update_idletasks()
            status = env_setup.run_full_diagnostics()
            
            # Проверяем успешность
            if "error" in status:
                msg = f"Ошибка выполнения диагностики:\n{status['error']}\n\nХотите запустить процесс «Устранение ошибок», чтобы переустановить ключевые компоненты?"
                confirmed = mb.askyesno(t("msg_diagnostics_title"), msg, parent=self)
                if confirmed:
                    run_recovery_flow()
                self.lbl_progress_status.configure(text="")
                return
                
            failed = [k for k, v in status.items() if v is not True]
            if not failed:
                # Все тесты успешно пройдены! Показываем красивый общий отчет
                torch_stat = env_setup.torch_status()
                cuda_str = "Да" if torch_stat.get("cuda_available") else "Нет"
                msg = t("msg_diagnostics_success", torch_stat.get("version", "2.2.2"), cuda_str)
                mb.showinfo(t("msg_diagnostics_title"), msg, parent=self)
            else:
                # Обнаружены сбои в компонентах! Предлагаем исправить через Устранение ошибок
                msg = f"❌ Неисправные компоненты: {', '.join(failed)}.\n\nЗапустить автоматическое «Устранение ошибок» для восстановления этих пакетов?"
                confirmed = mb.askyesno(t("msg_diagnostics_title"), msg, parent=self)
                if confirmed:
                    run_recovery_flow()
                
            update_variant_label()
            update_controls_visibility()
            self.lbl_progress_status.configure(text="")

        def run_recovery_flow():
            cache = env_setup.load_safe_files_cache()
            deleted = cache.get("deleted_files", [])
            if not deleted:
                mb.showinfo(t("btn_error_recovery"), t("msg_recovery_no_files"), parent=self)
                return
                
            package_mapping = {
                "torch": "torch==2.2.2",
                "torchaudio": "torchaudio==2.2.2",
                "torchvision": "torchvision==0.17.2",
                "tts": "coqui-tts",
                "numpy": "numpy==1.26.4",
                "pygame": "pygame",
                "customtkinter": "customtkinter",
                "num2words": "num2words",
                "llama_cpp": "llama-cpp-python",
                "soundfile": "soundfile"
            }
            
            packages_to_restore = set()
            for f in deleted:
                pkg_folder = f.get("package", "unknown").lower()
                for key, pip_spec in package_mapping.items():
                    if key in pkg_folder:
                        packages_to_restore.add(pip_spec)
                        
            if not packages_to_restore:
                mb.showinfo(t("btn_error_recovery"), "В истории удалений нет зарегистрированных ключевых пакетов.", parent=self)
                return
                
            confirmed = mb.askyesno(
                t("btn_error_recovery"),
                t("msg_recovery_confirm", ", ".join(packages_to_restore)),
                parent=self
            )
            if not confirmed:
                return
                
            def _recovery_thread():
                self.after(0, disable_buttons)
                self.after(0, lambda: self.progress_bar.set(0.01))
                self.after(0, lambda: self.lbl_progress_status.configure(text="🛠️ Восстановление пакетов..."))
                set_status("Восстановление пакетов...")
                set_progress(10)
                try:
                    def progress_cb(line):
                        self.after(0, lambda l=line: self.lbl_progress_status.configure(text=l))
                        set_status(line)
                        
                    restored = env_setup.run_error_recovery(progress_cb=progress_cb)
                    
                    def success_done():
                        enable_buttons()
                        self.progress_bar.set(1.0)
                        set_progress(100)
                        set_status("Ожидание...")
                        if restored:
                            self.lbl_progress_status.configure(text=t("msg_recovery_success", ", ".join(restored)))
                            mb.showinfo(t("update_done_title"), t("msg_recovery_success", ", ".join(restored)), parent=self)
                        else:
                            self.lbl_progress_status.configure(text="Не удалось восстановить пакеты.")
                            mb.showwarning(t("update_error_title"), "Не удалось восстановить пакеты. Проверьте соединение с интернетом.", parent=self)
                            
                    self.after(0, success_done)
                except Exception as e:
                    def failed_done(err_msg=str(e)):
                        enable_buttons()
                        self.progress_bar.set(0.0)
                        set_progress(0)
                        set_status("Ожидание...")
                        self.lbl_progress_status.configure(text=f"❌ Ошибка: {err_msg}")
                        mb.showerror(t("update_error_title"), f"Не удалось выполнить восстановление:\n{err_msg}", parent=self)
                    self.after(0, failed_done)
                    
            threading.Thread(target=_recovery_thread, daemon=True).start()

        # Кнопка очистки кэша и сканирования мусора объединена
        self.btn_clean = ctk.CTkButton(util_frame, text=t("btn_clean_cache"), command=run_scan_flow, fg_color=bg_active, hover_color=bg_hover, text_color=text_main)
        self.btn_clean.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")

        self.btn_diag = ctk.CTkButton(util_frame, text=t("btn_run_diagnostics"), command=run_diagnostics, fg_color=btn_color, hover_color=bg_hover, text_color=text_main)
        self.btn_diag.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="ew")

        self.btn_recovery = ctk.CTkButton(util_frame, text=t("btn_error_recovery"), command=run_recovery_flow, fg_color=btn_color, hover_color=bg_hover, text_color=text_main)
        self.btn_recovery.grid(row=1, column=0, columnspan=2, padx=0, pady=5, sticky="ew")
        
        # Индикаторы прогресса установки PyTorch
        self.lbl_progress_status = ctk.CTkLabel(sec_diag, text="", text_color=text_dim, font=ctk.CTkFont(size=11), justify="left", anchor="w")
        self.lbl_progress_status.pack(fill="x", padx=15, pady=(5, 2))
        
        self.progress_bar = ctk.CTkProgressBar(sec_diag, height=10)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 10))
        self.progress_bar.set(0.0)

        # Контейнер для кнопок «Прервать» и «Продолжить» — помещается строго под статус-бар/прогресс-бар
        self.active_controls_frame = ctk.CTkFrame(sec_diag, fg_color="transparent")
        # По умолчанию не упаковывается (появится только при загрузке)

        self.btn_stop = ctk.CTkButton(self.active_controls_frame, text=t("btn_cancel_install"), command=run_stop, fg_color="#b22222", hover_color=bg_hover, text_color=text_main)
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.btn_resume = ctk.CTkButton(self.active_controls_frame, text=t("btn_resume_install"), command=run_resume, fg_color="#2e8b57", hover_color=bg_hover, text_color=text_main)
        self.btn_resume.pack(side="left", expand=True, fill="x", padx=(5, 0))
        
        self.install_state = {"current_pkg": "torch"}
        
        def disable_buttons():
            self.btn_gpu.configure(state="disabled")
            self.btn_cpu.configure(state="disabled")
            self.chk_auto.configure(state="disabled")
            self.btn_check.configure(state="disabled")
            self.btn_clean.configure(state="disabled")
            self.btn_diag.configure(state="disabled")
            self.btn_recovery.configure(state="disabled")
            self.seg_pref.configure(state="disabled")
            self.install_running = True
            update_controls_visibility()
            
        def enable_buttons():
            # Разрешаем включать кнопку GPU-установки только если видеокарта NVIDIA действительно есть в системе!
            if gpu_info.get("vendor") == "nvidia":
                self.btn_gpu.configure(state="normal")
            else:
                self.btn_gpu.configure(state="disabled")
                
            self.btn_cpu.configure(state="normal")
            self.chk_auto.configure(state="normal")
            self.btn_check.configure(state="normal")
            self.btn_clean.configure(state="normal")
            self.btn_diag.configure(state="normal")
            self.btn_recovery.configure(state="normal")
            self.seg_pref.configure(state="normal")
            self.install_running = False
            update_controls_visibility()

        def update_controls_visibility():
            # Если установка сейчас запущена в фоне
            if getattr(self, "install_running", False):
                self.active_controls_frame.pack(fill="x", padx=15, pady=(5, 10))
                self.btn_stop.pack(side="left", expand=True, fill="x")
                self.btn_resume.pack_forget()
            else:
                # Если установка не идет, но есть прерванный/зависший чекпоинт
                checkpoint = env_setup._load_torch_checkpoint()
                has_checkpoint = checkpoint.get("stage") in ("downloading", "cleaned", "verifying")
                if has_checkpoint:
                    self.active_controls_frame.pack(fill="x", padx=15, pady=(5, 10))
                    self.btn_stop.pack_forget()
                    self.btn_resume.pack(side="left", expand=True, fill="x")
                else:
                    self.active_controls_frame.pack_forget()

        # Первичная установка видимости кнопок
        update_controls_visibility()
            
        def progress_cb(line):
            line_str = line.replace("\r", "").strip()
            if not line_str:
                return
            print(f"[Torch Setup UI] {line_str}")
            
            # Выводим ВСЮ текущую информацию (байты, скорость, ETA) в реальном времени!
            self.after(0, lambda l=line_str: self.lbl_progress_status.configure(text=l))
            # Дополнительно дублируем прогресс в статус-бар главного окна!
            set_status(f"Torch: {line_str}")

            m_coll = _torch_collecting_re.search(line_str)
            m_dl = _torch_downloading_re.search(line_str)
            m_inst = _torch_installing_re.search(line_str)
            
            if m_coll:
                pkg = m_coll.group(1)
                self.install_state["current_pkg"] = pkg
            elif m_dl:
                pkg = m_dl.group(1)
                self.install_state["current_pkg"] = pkg
            elif m_inst:
                self.after(0, lambda: self.progress_bar.set(0.95))
                set_progress(95)
                
            m_pct = _torch_percent_re.search(line_str)
            m_ratio = _torch_ratio_re.search(line_str)
            
            if m_pct:
                pct = int(m_pct.group(1))
                self.after(0, lambda: self.progress_bar.set(pct / 100.0))
                set_progress(pct)
            elif m_ratio:
                cur, total = float(m_ratio.group(1)), float(m_ratio.group(2))
                if total > 0:
                    pct = int((cur / total) * 100)
                    self.after(0, lambda: self.progress_bar.set(cur / total))
                    set_progress(pct)
                    
        def start_install(variant, resume=False):
            if variant == "cu118":
                gpu = env_setup.detect_gpu()
                if gpu.get("vendor") != "nvidia":
                    mb.showerror(t("update_error_title"), t("msg_cuda_requires_nvidia"), parent=self)
                    return

            import sys
            if "torch" in sys.modules:
                confirmed = mb.askyesno(
                    t("update_title"),
                    t("msg_torch_already_loaded_restart_confirm"),
                    parent=self
                )
                if confirmed:
                    from engine.settings_store import load_settings, save_settings
                    settings = load_settings()
                    settings["open_updates_on_startup"] = True
                    settings["install_variant_on_startup"] = variant
                    save_settings(settings)
                    
                    from engine.updater import restart
                    restart()
                return

            if not resume:
                warning_msg = t("torch_install_warning", {"cu118": "GPU (CUDA)", "cpu": "CPU"}.get(variant, variant))
                confirmed = mb.askyesno(t("update_title"), warning_msg, parent=self)
                if not confirmed:
                    return
            
            self.install_was_stopped = False
            
            def _install_thread():
                self.after(0, disable_buttons)
                self.after(0, lambda: self.progress_bar.set(0.01))
                set_progress(1)
                self.after(0, lambda: self.lbl_progress_status.configure(text=t("status_torch_setup", variant)))
                set_status(t("status_torch_setup", variant))
                try:
                    status = env_setup.install_torch(progress_cb=progress_cb, resume=resume, variant=variant)
                    def success_done():
                        enable_buttons()
                        self.progress_bar.set(1.0)
                        set_progress(100)
                        self.lbl_progress_status.configure(text=t("torch_install_success_label"))
                        set_status(t("status_ready"))
                        update_variant_label()
                        mb.showinfo(t("update_done_title"), t("torch_install_success", variant), parent=self)
                    self.after(0, success_done)
                except Exception as e:
                    def failed_done(err_msg=str(e)):
                        enable_buttons()
                        self.progress_bar.set(0.0)
                        set_progress(0)
                        set_status(t("status_waiting"))
                        if getattr(self, "install_was_stopped", False):
                            self.lbl_progress_status.configure(text=t("msg_install_stopped"))
                            mb.showinfo(t("update_title"), t("msg_install_stopped"), parent=self)
                        else:
                            self.lbl_progress_status.configure(text=t("torch_install_failed_label"))
                            mb.showerror(t("update_error_title"), t("torch_install_failed", err_msg), parent=self)
                    self.after(0, failed_done)
                    
            threading.Thread(target=_install_thread, daemon=True).start()

        # Автоматический запуск/продолжение установки после перезапуска в безопасном режиме
        auto_install_variant = self.settings.get("install_variant_on_startup")
        if auto_install_variant:
            self.settings["install_variant_on_startup"] = None
            save_settings(self.settings)
            self.after(300, lambda: start_install(auto_install_variant, resume=True))


_settings_window = None

def open_updates_settings_window():
    global _settings_window
    if _settings_window is not None and _settings_window.winfo_exists():
        _settings_window.focus()
        return
    _settings_window = UpdateSettingsWindow(root)
