# ── Добавить в начало chat_settings.py, рядом с остальными импортами ──────────
# from engine import env_setup


# ── Вставить внутрь build_local_page(), ПЕРЕД строкой с кнопкой каталога
#    ("Catalog Button" / _open_local_catalog) — своя карточка, независимая от
#    списка установленных моделей ────────────────────────────────────────────

def _build_environment_section(container):
    """Карточка «Системное окружение»: проверка CPU-флагов и (пере)установка
    llama-cpp-python под конкретный процессор, со стилизованным консент-диалогом
    и логом установки в цветах текущей темы."""

    card_outer = tk.Frame(container, bg=_c("BORDER"))
    card_outer.pack(fill="x", pady=(0, 15))
    card = tk.Frame(card_outer, bg=_c("BG_CARD"))
    card.pack(fill="x", padx=1, pady=1)

    header = TkFrame(card, bg=_c("BG_CARD"))
    header.pack(fill="x", padx=14, pady=(12, 6))
    TkLabel(header, text="⚙ Системное окружение", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
            font=("Segoe UI", 12, "bold"), anchor="w").pack(side="left")

    body = TkFrame(card, bg=_c("BG_CARD"))
    body.pack(fill="x", padx=14, pady=(0, 14))

    status_lbl = TkLabel(body, text="Нажмите «Проверить», чтобы посмотреть состояние окружения.",
                          bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11),
                          anchor="w", wraplength=520, justify="left")
    status_lbl.pack(fill="x", pady=(4, 10))

    btn_row = TkFrame(body, bg=_c("BG_CARD"))
    btn_row.pack(fill="x")

    def _run_check():
        status_lbl.config(text="🔍 Проверяю CPU и текущую установку...", fg=_c("TEXT_DIM"))

        def worker():
            from engine import env_setup
            cpu = env_setup.detect_cpu()
            llama_status = env_setup.llama_cpp_status()

            flags_str = ", ".join(f for f in ("avx", "avx2", "fma", "f16c") if cpu.get(f)) or "базовый набор"
            if llama_status["installed"]:
                text = (
                    f"CPU: {cpu['name']}\n"
                    f"Поддерживаемые ускорения: {flags_str}\n"
                    f"llama-cpp-python: ✅ установлен и импортируется корректно"
                )
                color = _c("TEXT_SUCCESS")
            else:
                text = (
                    f"CPU: {cpu['name']}\n"
                    f"Поддерживаемые ускорения: {flags_str}\n"
                    f"llama-cpp-python: ❌ не установлен или несовместим "
                    f"({llama_status['error']})"
                )
                color = _c("TEXT_ERROR")

            _safe_after(0, lambda: status_lbl.config(text=text, fg=color))

        threading.Thread(target=worker, daemon=True).start()

    def _run_install():
        _open_env_install_dialog(win)

    _make_button(btn_row, "🔍 Проверить окружение", _run_check,
                 bg=_c("BG_INPUT"), font_size=10, height=1, padx=8, pady=3).pack(side="left", padx=(0, 6))
    _make_button(btn_row, "⚙ Установить/пересобрать под этот CPU", _run_install,
                 bg=_c("BG_ACTIVE"), font_size=10, height=1, padx=8, pady=3).pack(side="left")


def _open_env_install_dialog(parent):
    """Стилизованный консент-диалог + лог установки (не батник, не консоль —
    свой Toplevel в цветах текущей темы)."""
    from engine import env_setup

    dlg = tk.Toplevel(parent)
    _set_dark_titlebar(dlg)
    dlg.title("Установка зависимостей для локальных моделей")
    dlg.geometry("620x480")
    dlg.configure(bg=_c("BG_CARD"))
    dlg.transient(parent)
    dlg.grab_set()

    TkLabel(dlg, text="Установка/пересборка llama-cpp-python", bg=_c("BG_CARD"),
            fg=_c("TEXT_MAIN"), font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(16, 6))

    TkLabel(
        dlg,
        text=("Программа определит поддерживаемые процессором наборы инструкций "
              "(AVX/AVX2/FMA/F16C) и соберёт библиотеку под конкретно этот компьютер. "
              "Это может занять несколько минут и потребует подключения к интернету. "
              "Существующая установка (если есть) будет удалена и поставлена заново."),
        bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11),
        anchor="w", justify="left", wraplength=580,
    ).pack(anchor="w", padx=16, pady=(0, 12))

    # ── Консольного вида лог, но в цветах темы, не отдельное окно cmd ──────────
    log_outer = TkFrame(dlg, bg=_c("BORDER"), padx=1, pady=1)
    log_outer.pack(fill="both", expand=True, padx=16)
    log_inner = TkFrame(log_outer, bg=_c("BG_INPUT"))
    log_inner.pack(fill="both", expand=True)
    log_sc = tk.Scrollbar(log_inner)
    log_sc.pack(side="right", fill="y")
    log_txt = tk.Text(
        log_inner, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"),
        relief="flat", highlightthickness=0, font=("Consolas", 10), wrap="word",
        state="disabled", yscrollcommand=log_sc.set,
    )
    log_txt.pack(fill="both", expand=True, padx=6, pady=6)
    log_sc.config(command=log_txt.yview)
    _bind_text_hotkeys(log_txt)

    def _append_log(line):
        def _do():
            log_txt.config(state="normal")
            log_txt.insert("end", line + "\n")
            log_txt.see("end")
            log_txt.config(state="disabled")
        _safe_after(0, _do)

    btn_row = TkFrame(dlg, bg=_c("BG_CARD"))
    btn_row.pack(fill="x", padx=16, pady=(10, 16))

    consent_btn = _make_button(btn_row, "✅ Начать установку", lambda: _start(),
                                bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=8, pady=3)
    consent_btn.pack(side="right")
    _make_button(btn_row, "✕ Отмена", lambda: dlg.destroy(),
                 bg=_c("BG_INPUT"), font_size=11, height=1, padx=8, pady=3).pack(side="right", padx=(0, 6))

    def _start():
        consent_btn.config(state="disabled")
        _append_log("── Начинаю установку ──")

        def worker():
            try:
                env_setup.install_llama_cpp(progress_cb=_append_log)
                _safe_after(0, lambda: consent_btn.config(text="✅ Готово"))
            except Exception as e:
                _append_log(f"❌ Ошибка: {e}")
                _safe_after(0, lambda: consent_btn.config(text="⚠ Повторить", state="normal"))

        threading.Thread(target=worker, daemon=True).start()
