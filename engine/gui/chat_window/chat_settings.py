from __future__ import annotations
import json
import os
import threading
import uuid
from datetime import datetime
from tkinter import filedialog, messagebox
import tkinter as tk
import webbrowser

import engine.gui.chat_window.state as state
from engine.gui.chat_window.custom_widgets import CTK_AVAILABLE, CTkFrame, CTkLabel, CTkButton, TkFrame, TkLabel, TkButton, TkRawFrame
from i18n import t

# Убеждаемся, что папка site-packages bundled-окружения доступна для импортов
try:
    import sys
    from engine import env_setup
    if env_setup.SITE_PACKAGES not in sys.path:
        sys.path.insert(0, env_setup.SITE_PACKAGES)
except Exception:
    pass

def open_gpt_settings(event=None):
    try:
        from engine import gpt_client
        from engine import local_llm_client
    except Exception as e:
        messagebox.showerror(t("chat_settings_title"), t("chat_err_load_gpt", e), parent=_get_app_parent() or state._root)
        return "break"

    if _widget_exists(state._settings_window):
        _show_window(state._settings_window)
        return "break"

    win = tk.Toplevel(_get_app_parent() or state._root)
    _set_dark_titlebar(win)
    
    # Remove default feather icon
    try:
        win.iconbitmap('blank_icon.ico')
    except Exception:
        pass
        
    state._settings_window = win

    def _win_report_callback_exception(exc, val, tb):
        """Без этого переопределения Tkinter молча печатает traceback в stderr,
        который в portable-сборке без консоли (pythonw) никуда не попадает —
        кнопка визуально просто "не работает". Пишем в файл + показываем."""
        import traceback as _tb
        full_trace = "".join(_tb.format_exception(exc, val, tb))
        try:
            from engine.paths import BASE_DIR
            log_path = os.path.join(BASE_DIR, "env_error_log.txt")
        except Exception:
            log_path = "env_error_log.txt"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"── {datetime.now().isoformat()} — {t('chat_settings_title')} (необработанное) ──\n{full_trace}\n\n")
        except Exception:
            pass
        try:
            messagebox.showerror(t("settings_win_error_title"), str(val), parent=win)
        except Exception:
            pass

    win.report_callback_exception = _win_report_callback_exception

    win.title(t("chat_settings_win_title"))
    win.geometry("960x700")
    win.minsize(750, 550)
    win.resizable(True, True)
    win.configure(bg=_c("BG_DARK"))
    win.transient(_get_app_parent() or state._root)

    # ── Layout: Sidebar + Content ──────────────────────────────────────────────
    main_container = TkFrame(win, bg=_c("BG_DARK"))
    main_container.pack(fill="both", expand=True)

    # Sidebar (Menu)
    sidebar = TkFrame(main_container, bg=_c("BG_CARD"), width=220)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    TkLabel(
        sidebar, text=t("chat_settings_title"),
        bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
        font=("Segoe UI", 15, "bold"),
    ).pack(fill="x", padx=16, pady=(20, 20))

    # Content Area (with scroll)
    content_outer = TkFrame(main_container, bg=_c("BG_DARK"))
    content_outer.pack(side="left", fill="both", expand=True)

    canvas = tk.Canvas(content_outer, bg=_c("BG_CARD"), highlightthickness=0, bd=0)
    scrollbar = tk.Scrollbar(content_outer, orient="vertical", command=canvas.yview)
    
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    canvas_frame = TkFrame(canvas, bg=_c("BG_CARD"))
    canvas_window = canvas.create_window((0, 0), window=canvas_frame, anchor="nw")

    def update_scroll_region(event=None):
        canvas.update_idletasks()
        bbox = canvas.bbox("all")
        if bbox:
            # Не даём скроллить ниже реального контента
            h = max(bbox[3], canvas.winfo_height())
            canvas.configure(scrollregion=(bbox[0], bbox[1], bbox[2], h))

    def on_canvas_configure(event):
        canvas.itemconfig(canvas_window, width=event.width)
        update_scroll_region()

    canvas_frame.bind("<Configure>", update_scroll_region)
    canvas.bind("<Configure>", on_canvas_configure)

    def _on_mousewheel(event):
        try:
            if getattr(event, "num", None) == 4: units = -3
            elif getattr(event, "num", None) == 5: units = 3
            else:
                delta = int(getattr(event, "delta", 0) or 0)
                if delta == 0: return None
                units = -3 if delta > 0 else 3
            canvas.yview_scroll(units, "units")
            return "break"
        except Exception: return None

    for target in (win, canvas, canvas_frame):
        try:
            target.bind("<MouseWheel>", _on_mousewheel, add="+")
            target.bind("<Button-4>", _on_mousewheel, add="+")
            target.bind("<Button-5>", _on_mousewheel, add="+")
        except Exception: pass

    # ── Page Management ───────────────────────────────────────────────────────
    current_page = [None]
    _page_cache = {}

    def _invalidate_page(page_id):
        """Уничтожает закэшированный фрейм страницы, чтобы при следующем show_page()
        она была построена заново со свежими данными (например, после установки/
        удаления локальной модели список должен обновиться, а не остаться старым)."""
        frame = _page_cache.pop(page_id, None)
        if frame is not None:
            try:
                frame.destroy()
            except Exception:
                pass

    def show_page(page_id):
        # Скрываем все закэшированные страницы
        for pid, frame in list(_page_cache.items()):
            if frame is None or not frame.winfo_exists():
                del _page_cache[pid]
            else:
                frame.pack_forget()

        if page_id not in _page_cache or _page_cache[page_id] is None:
            if page_id == "api":
                frame = build_api_page()
            elif page_id == "local":
                frame = build_local_page()
            elif page_id == "general":
                frame = build_general_page()
            else:
                return
            if frame is None:
                return
            _page_cache[page_id] = frame
        else:
            frame = _page_cache[page_id]
            if frame is None:
                return

        frame.pack(fill="both", expand=True)
        update_scroll_region()
        current_page[0] = page_id

    # ── API Page implementation ───────────────────────────────────────────────
    def build_api_page():
        container = TkFrame(canvas_frame, bg=_c("BG_CARD"))
        container.pack(fill="both", expand=True, padx=20, pady=20)

        TkLabel(
            container, text=t("chat_providers_header"),
            bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", pady=(0, 15))

        accordion_state = {"expanded": gpt_client.get_ui_state().get("expanded_provider")}
        accordion_container = TkFrame(container, bg=_c("BG_CARD"))
        accordion_container.pack(fill="x")

        def _all_provider_entries():
            entries = []
            hidden = gpt_client.get_hidden_providers()
            for pid, info in gpt_client.PROVIDERS.items():
                if pid == "local" or pid in hidden: continue
                entries.append((pid, info, False))
            for p in gpt_client.list_custom_providers():
                entries.append((p.get("id"), p, True))
            return entries

        def _toggle_card(pid):
            accordion_state["expanded"] = None if accordion_state["expanded"] == pid else pid
            gpt_client.set_ui_state(expanded_provider=accordion_state["expanded"])
            _rebuild_accordion()

        def _rebuild_accordion():
            for child in accordion_container.winfo_children():
                child.destroy()
            
            active_pid = gpt_client.get_provider()
            for pid, info, is_custom in _all_provider_entries():
                is_expanded = accordion_state["expanded"] == pid
                is_active = pid == active_pid
                
                card_outer = tk.Frame(accordion_container, bg=_c("BORDER"))
                card_outer.pack(fill="x", pady=(0, 6))
                
                card = tk.Frame(card_outer, bg=_c("BG_CARD"))
                card.pack(fill="x", padx=1, pady=1)
                
                header = tk.Frame(card, bg=_c("BG_CARD"), cursor="hand2")
                header.pack(fill="x", padx=12, pady=10)
                
                arrow = "▾" if is_expanded else "▸"
                dot = "🟢" if is_active else ("🔧" if is_custom else "⚪")
                
                tk.Label(header, text=arrow, bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12), width=2).pack(side="left")
                tk.Label(header, text=dot, bg=_c("BG_CARD"), font=("Segoe UI", 13)).pack(side="left", padx=(0, 4))
                
                title_box = tk.Frame(header, bg=_c("BG_CARD"))
                title_box.pack(side="left", fill="x", expand=True)
                
                tk.Label(title_box, text=info.get("label", pid), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 13), anchor="w").pack(anchor="w")
                
                cur_model = gpt_client.get_model(pid)
                has_key = bool(gpt_client.get_api_key(pid))
                sub = f"{t('chat_key_set') if has_key else t('chat_key_none')} · {cur_model or '—'}"
                tk.Label(title_box, text=sub, bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), anchor="w").pack(anchor="w")
                
                if is_active:
                    tk.Label(header, text=t("chat_active_label"), bg=_c("BG_CARD"), fg=_c("TEXT_SUCCESS"), font=("Segoe UI", 11, "bold")).pack(side="right")
                
                header.bind("<Button-1>", lambda e, p=pid: _toggle_card(p))
                for w in title_box.winfo_children():
                    w.bind("<Button-1>", lambda e, p=pid: _toggle_card(p))

                if not is_expanded: continue
                
                body = tk.Frame(card, bg=_c("BG_CARD"))
                body.pack(fill="x", padx=12, pady=(0, 12))
                tk.Frame(body, bg=_c("BORDER"), height=1).pack(fill="x", pady=(0, 10))
                
                TkLabel(body, text=t("chat_field_api_key"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12), anchor="w").pack(fill="x", pady=(0, 4))
                card_key_var = tk.StringVar(value=gpt_client.get_api_key(pid))
                key_row = tk.Frame(body, bg=_c("BG_CARD"))
                key_row.pack(fill="x")
                ke = tk.Entry(key_row, textvariable=card_key_var, show="•", bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=1, highlightbackground=_c("BORDER"), highlightcolor=_c("ACCENT"), font=("Consolas", 12))
                ke.pack(side="left", fill="x", expand=True, ipady=5)
                _bind_text_hotkeys(ke)
                
                show_v = tk.BooleanVar(value=False)
                tk.Checkbutton(key_row, text="👁", variable=show_v, command=lambda e=ke, v=show_v: e.config(show="" if v.get() else "•"), bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), selectcolor=_c("BG_INPUT"), activebackground=_c("BG_CARD"), relief="flat", font=("Segoe UI", 11)).pack(side="left", padx=(4, 0))
                
                hint = info.get("key_hint", "")
                if hint:
                    url = hint if hint.startswith("http") else f"https://{hint}"
                    link_lbl = tk.Label(body, text=hint, bg=_c("BG_CARD"), fg=_c("ACCENT"), font=("Segoe UI", 12), cursor="hand2", anchor="w")
                    link_lbl.pack(fill="x", pady=(3, 8))
                    link_lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

                TkLabel(body, text=t("chat_model_label"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12), anchor="w").pack(fill="x", pady=(4, 4))
                models = list(info.get("models", []) or [])
                card_model_var = tk.StringVar(value=cur_model or (models[0] if models else ""))
                if models:
                    for m in models:
                        tk.Radiobutton(body, text=m, variable=card_model_var, value=m, bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), selectcolor=_c("BG_INPUT"), activebackground=_c("BG_CARD"), font=("Segoe UI", 12), anchor="w", cursor="hand2").pack(fill="x", anchor="w")
                else:
                    TkLabel(body, text=t("chat_models_empty"), bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12)).pack(anchor="w")
                
                card_status = TkLabel(body, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), anchor="w")
                card_status.pack(fill="x", pady=(8, 4))
                
                def _save_card(p=pid, kv=card_key_var, mv=card_model_var, st=card_status):
                    try:
                        gpt_client.set_api_key(kv.get().strip(), p)
                        if mv.get(): gpt_client.set_model(mv.get(), p)
                        st.config(text=t("chat_saved"), fg=_c("TEXT_SUCCESS"))
                        _rebuild_accordion()
                    except Exception as e: st.config(text=str(e), fg=_c("TEXT_ERROR"))
                
                def _test_card(p=pid, kv=card_key_var, st=card_status):
                    st.config(text=t("chat_checking_key"), fg=_c("TEXT_DIM"))
                    def worker():
                        try:
                            ok, msg = gpt_client.validate_key(kv.get().strip(), p)
                            _safe_after(0, lambda: st.config(text=str(msg), fg=_c("TEXT_SUCCESS") if ok else _c("TEXT_ERROR")))
                        except Exception as e:
                            _safe_after(0, lambda err=e: st.config(text=str(err), fg=_c("TEXT_ERROR")))
                    threading.Thread(target=worker, daemon=True).start()

                def _activate_card(p=pid):
                    try:
                        gpt_client.set_provider(p)
                        _rebuild_accordion()
                    except Exception as e: print(e)

                btn_row = TkFrame(body, bg=_c("BG_CARD"))
                btn_row.pack(fill="x", pady=(2, 0))
                _make_button(btn_row, t("chat_btn_check"), _test_card, bg=_c("BG_INPUT"), font_size=10, height=1, padx=6, pady=2).pack(side="left", fill="x", expand=True, padx=(0, 4))
                _make_button(btn_row, t("chat_btn_save"), _save_card, bg=_c("BG_INPUT"), font_size=10, height=1, padx=6, pady=2).pack(side="left", fill="x", expand=True, padx=(0, 4))
                if not is_active:
                    _make_button(btn_row, t("chat_btn_activate"), _activate_card, bg=_c("BG_ACTIVE"), font_size=10, height=1, padx=6, pady=2).pack(side="left", fill="x", expand=True, padx=(0, 4))
                
                if is_custom:
                    def _edit_this(p=pid): _open_provider_form(edit_pid=p)
                    def _delete_this(p=pid, lbl=info.get("label", pid)):
                        if messagebox.askyesno(t("chat_provider_delete_title"), t("chat_provider_delete_msg", lbl), parent=win):
                            gpt_client.delete_custom_provider(p)
                            _rebuild_accordion()
                    _make_button(btn_row, "✎", _edit_this, bg=_c("BG_INPUT"), font_size=10, height=1, width=3, padx=4, pady=2).pack(side="left", padx=(0, 4))
                    _make_button(btn_row, "🗑", _delete_this, bg=_c("BG_INPUT"), font_size=10, height=1, width=3, padx=4, pady=2).pack(side="left")
                else:
                    def _hide_this(p=pid, lbl=info.get("label", pid)):
                        if messagebox.askyesno(t("chat_provider_hide_title"), t("chat_provider_hide_msg", lbl), parent=win):
                            gpt_client.hide_provider(p)
                            _rebuild_accordion()
                    _make_button(btn_row, t("chat_btn_hide"), _hide_this, bg=_c("BG_INPUT"), font_size=10, height=1, padx=6, pady=2).pack(side="left", fill="x", expand=True)

        _rebuild_accordion()

        btn_row_f = TkFrame(container, bg=_c("BG_CARD"))
        btn_row_f.pack(fill="x", pady=(15, 0))

        def _open_provider_form(edit_pid=None):
            is_edit = edit_pid is not None
            existing = {}
            if is_edit:
                for p in gpt_client.list_custom_providers():
                    if p.get("id") == edit_pid: existing = p; break

            form = tk.Toplevel(win)
            _set_dark_titlebar(form)
            form.title(t("chat_provider_edit") if is_edit else t("chat_provider_add"))
            form.geometry("480x540")
            form.configure(bg=_c("BG_CARD"))
            form.transient(win)
            form.grab_set()

            def _f(p, l, i="", h=1):
                TkLabel(p, text=l, bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12), anchor="w").pack(fill="x", padx=16, pady=(10, 3))
                if h == 1:
                    v = tk.StringVar(value=i); e = tk.Entry(p, textvariable=v, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=1, highlightbackground=_c("BORDER"), highlightcolor=_c("ACCENT"), font=("Segoe UI", 12))
                    e.pack(fill="x", padx=16, ipady=5); _bind_text_hotkeys(e); return v, e
                else:
                    fr = TkFrame(p, bg=_c("BORDER"), padx=1, pady=1); fr.pack(fill="x", padx=16)
                    in_ = TkFrame(fr, bg=_c("BG_INPUT")); in_.pack(fill="x")
                    t_ = tk.Text(in_, height=h, wrap="word", bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=0, font=("Segoe UI", 12), padx=6, pady=6)
                    t_.insert("1.0", i); t_.pack(fill="x"); _bind_text_hotkeys(t_); return t_, t_

            l_v, _ = _f(form, t("chat_field_label"), existing.get("label", ""))
            u_v, _ = _f(form, t("chat_field_url"), existing.get("url", ""))
            m_i = "\n".join(existing.get("models", []))
            m_t, _ = _f(form, t("chat_field_models"), m_i, h=4)
            f_v, _ = _f(form, t("chat_field_fallback"), existing.get("fallback_model", ""))
            h_i = "\n".join(f"{k}: {v}" for k, v in (existing.get("extra_headers") or {}).items())
            h_t, _ = _f(form, t("chat_field_headers"), h_i, h=3)

            st = TkLabel(form, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12), anchor="w")
            st.pack(fill="x", padx=16, pady=(8, 0))

            def save():
                lbl = (l_v.get() if isinstance(l_v, tk.StringVar) else l_v).strip()
                url = (u_v.get() if isinstance(u_v, tk.StringVar) else u_v).strip()
                raw_m = m_t.get("1.0", "end-1c") if isinstance(m_t, tk.Text) else ""
                mods = [m.strip() for m in raw_m.splitlines() if m.strip()]
                fb = (f_v.get() if isinstance(f_v, tk.StringVar) else f_v).strip()
                raw_h = h_t.get("1.0", "end-1c") if isinstance(h_t, tk.Text) else ""
                ext_h = {k.strip(): v.strip() for line in raw_h.splitlines() if ":" in line for k, _, v in [line.partition(":")]}

                if not url: st.config(text=t("chat_url_empty"), fg=_c("TEXT_ERROR")); return
                if not mods: st.config(text=t("chat_need_model"), fg=_c("TEXT_ERROR")); return

                try:
                    if is_edit: gpt_client.update_custom_provider(edit_pid, label=lbl, url=url, models=mods, fallback_model=fb, extra_headers=ext_h)
                    else: 
                        pid = lbl.lower().replace(" ", "_")
                        import re; pid = re.sub(r"[^a-z0-9_]", "", pid) or "custom"
                        gpt_client.add_custom_provider(pid, lbl, url, mods, fb or mods[0], ext_h)
                    form.destroy(); build_api_page()
                except Exception as e: st.config(text=str(e), fg=_c("TEXT_ERROR"))

            br = TkFrame(form, bg=_c("BG_CARD"))
            br.pack(fill="x", padx=16, pady=(6, 16))
            _make_button(br, t("chat_btn_cancel_x"), lambda: form.destroy(), bg=_c("BG_INPUT"), font_size=11, height=1, padx=6, pady=3).pack(side="right", padx=(4, 0))
            _make_button(br, t("chat_btn_save"), save, bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=6, pady=3).pack(side="right")

        return container

    # ── Local Page implementation (установленные модели + каталог, одна вкладка) ──
    def build_local_page():
        container = TkFrame(canvas_frame, bg=_c("BG_CARD"))
        container.pack(fill="both", expand=True, padx=20, pady=20)

        local_view = container
        catalog_view = container

        # ═══════════════════════════════════════════════════════════════════════
        #  Установленные модели
        # ═══════════════════════════════════════════════════════════════════════
        TkLabel(
            local_view, text=t("local_models_header"),
            bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        TkLabel(
            local_view, text=t("local_models_desc"),
            bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12),
            anchor="w", wraplength=500,
        ).pack(anchor="w", pady=(0, 20))

        # Installed models list
        list_frame = TkFrame(local_view, bg=_c("BG_CARD"))
        list_frame.pack(fill="x", pady=(0, 15))
        TkLabel(list_frame, text=t("local_model_active"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12), anchor="w").pack(fill="x", pady=(0, 6))

        installed = local_llm_client.list_installed_models()
        active_id = local_llm_client.get_active_model_id()

        status_lbl = TkLabel(local_view, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12), anchor="w")

        if not installed:
            TkLabel(list_frame, text=t("local_no_installed_models"), bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12), anchor="w").pack(fill="x")
        else:
            for m in installed:
                row = TkFrame(list_frame, bg=_c("BG_CARD"))
                row.pack(fill="x", pady=2)
                is_active = m.get("id") == active_id
                dot = "🟢" if is_active else "⚪"
                TkLabel(row, text=f"{dot} {m.get('label', m.get('filename', '?'))}", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12), anchor="w").pack(side="left", fill="x", expand=True)

                def _activate(mid=m.get("id")):
                    local_llm_client.set_active_model_id(mid)
                    gpt_client.set_model(mid, "local")
                    gpt_client.set_provider("local")
                    _invalidate_page("local")
                    show_page_with_style("local")

                def _remove(mid=m.get("id"), lbl=m.get("label", "")):
                    if messagebox.askyesno(t("local_model_delete_title"), t("local_model_delete_msg", lbl), parent=win):
                        local_llm_client.remove_model(mid)
                        _invalidate_page("local")
                        show_page_with_style("local")
                if not is_active:
                    _make_button(row, t("local_model_activate_btn"), _activate, bg=_c("BG_ACTIVE"), font_size=10, height=1, padx=6, pady=2).pack(side="right", padx=(4, 0))
                _make_button(row, "🗑", _remove, bg=_c("BG_INPUT"), font_size=10, height=1, width=3, padx=4, pady=2).pack(side="right")

        status_lbl.pack(fill="x", pady=(10, 0))

        # Системное окружение — карточка проверки/установки llama-cpp-python
        _build_environment_section(local_view)

        tk.Frame(container, bg=_c("BORDER"), height=1).pack(fill="x", pady=(20, 20))

        # ═══════════════════════════════════════════════════════════════════════
        #  Каталог моделей
        # ═══════════════════════════════════════════════════════════════════════
        TkLabel(
            catalog_view, text=t("local_catalog_header"),
            bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        # Загружаем каталог с оценкой совместимости
        from engine import env_setup
        resolved = env_setup.resolve_backend()
        catalog_items = local_llm_client.get_compatible_models(vram_gb=resolved["gpu"].get("vram_gb"))

        list_outer = TkFrame(catalog_view, bg=_c("BORDER"), padx=1, pady=1)
        list_outer.pack(fill="both", expand=True, pady=(0, 15))
        sc = tk.Scrollbar(list_outer)
        sc.pack(side="right", fill="y")
        lb = tk.Listbox(list_outer, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), selectbackground=_c("ACCENT"), selectforeground="#ffffff", activestyle="none", relief="flat", highlightthickness=0, font=("Segoe UI", 12), yscrollcommand=sc.set)
        lb.pack(fill="both", expand=True)
        sc.config(command=lb.yview)

        for m in catalog_items:
            prefix = "✅ " if m.get("installed") else ("✓ " if m.get("compatible") else "❌ ")
            lb.insert(tk.END, f"{prefix}{m['label']}")

        info_box = TkFrame(catalog_view, bg=_c("BG_CARD"), pady=10)
        info_box.pack(fill="x")
        desc_lbl = TkLabel(info_box, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12), anchor="w", wraplength=480)
        desc_lbl.pack(anchor="w")
        mem_lbl = TkLabel(info_box, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), anchor="w")
        mem_lbl.pack(anchor="w")
        status_cat_lbl = TkLabel(info_box, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11, "bold"), anchor="w")
        status_cat_lbl.pack(anchor="w")
        link_lbl = TkLabel(info_box, text="", bg=_c("BG_CARD"), fg=_c("ACCENT"), font=("Segoe UI", 12), cursor="hand2", anchor="w")
        link_lbl.pack(anchor="w")
        action_status_lbl = TkLabel(info_box, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), anchor="w")
        action_status_lbl.pack(anchor="w")

        selected_model = [None]
        download_thread = [None]
        download_cancelled = [False]
        download_in_progress = [False]

        def _has_incomplete_download(filename: str) -> bool:
            chk = local_llm_client._load_download_checkpoint(filename)
            return bool(chk and chk.get("offset", 0) > 0 and chk.get("url"))

        def _update_catalog_info(e=None):
            sel = lb.curselection()
            if not sel:
                return
            m = catalog_items[sel[0]]
            selected_model[0] = m
            desc_lbl.config(text=t("local_model_meta_desc").format(m.get('description', '')))
            mem_lbl.config(text=t("local_catalog_memory").format(m.get('memory_gb', 0)))

            if m.get("installed"):
                status_cat_lbl.config(text=t("local_catalog_installed"), fg=_c("TEXT_SUCCESS"))
                action_btn.config(text=t("local_catalog_activate_btn"), state="normal", bg=_c("BG_ACTIVE"))
                discard_btn.pack_forget()
            elif not m.get("compatible"):
                status_cat_lbl.config(text=t("local_catalog_too_large"), fg=_c("TEXT_ERROR"))
                action_btn.config(text=t("local_model_install_btn"), state="disabled", bg=_c("BG_INPUT"))
                discard_btn.pack_forget()
            elif _has_incomplete_download(m.get("filename", "")):
                status_cat_lbl.config(text=t("local_catalog_downloading"), fg=_c("TEXT_DIM"))
                action_btn.config(text=t("local_catalog_resume_btn"), state="normal", bg=_c("BG_ACTIVE"))
                if not download_in_progress[0]:
                    discard_btn.pack(side="right", padx=(0, 4))
                else:
                    discard_btn.pack_forget()
            else:
                status_cat_lbl.config(text=t("local_catalog_compatible"), fg=_c("TEXT_SUCCESS"))
                action_btn.config(text=t("local_catalog_download_btn"), state="normal", bg=_c("BG_ACTIVE"))
                discard_btn.pack_forget()

            link_lbl.config(text=t("local_model_meta_link"))
            link_lbl.bind("<Button-1>", lambda e, u=m.get('download_link', ''): webbrowser.open(u) if u else None)
            if not download_in_progress[0]:
                action_status_lbl.config(text="")

        lb.bind("<<ListboxSelect>>", _update_catalog_info)

        def _finish_download(entry, m):
            sel = lb.curselection()
            if sel:
                lb.delete(sel[0])
                lb.insert(sel[0], f"✅ {m['label']}")
            action_status_lbl.config(text=t("local_model_added_msg", entry['label']), fg=_c("TEXT_SUCCESS"))
            action_btn.config(text=t("local_catalog_activate_btn"), state="normal", bg=_c("BG_ACTIVE"))
            local_llm_client.set_active_model_id(entry["id"])
            gpt_client.set_model(entry["id"], "local")
            gpt_client.set_provider("local")
            download_in_progress[0] = False
            download_cancelled[0] = False
            _invalidate_page("local")
            _safe_after(900, lambda: show_page_with_style("local"))

        def _action_model():
            m = selected_model[0]
            if not m:
                return
            if m.get("installed"):
                # Активировать уже скачанную модель
                path = local_llm_client.get_model_file_path(m["filename"])
                entry = next((x for x in local_llm_client.list_installed_models() if x.get("path") == path), None)
                if not entry:
                    entry = local_llm_client.register_model(path, label=m.get("label"))
                local_llm_client.set_active_model_id(entry["id"])
                gpt_client.set_model(entry["id"], "local")
                gpt_client.set_provider("local")
                action_status_lbl.config(text=t("local_model_activated_status"), fg=_c("TEXT_SUCCESS"))
                _invalidate_page("local")
                _safe_after(900, lambda: show_page_with_style("local"))
                return

            if not m.get("compatible"):
                return

            # Если скачивание уже идёт — кнопка работает как "Отменить"
            if download_in_progress[0]:
                if messagebox.askyesno(t("local_catalog_cancel_confirm_title"), t("local_catalog_cancel_confirm_msg"), parent=win):
                    download_cancelled[0] = True
                    action_btn.config(state="disabled")
                    action_status_lbl.config(text="Отмена...", fg=_c("TEXT_DIM"))
                return

            resume = _has_incomplete_download(m.get("filename", ""))
            download_cancelled[0] = False
            download_in_progress[0] = True
            action_btn.config(text=t("local_catalog_cancel_btn"), state="normal", bg=_c("BG_INPUT"))
            action_status_lbl.config(text=t("local_catalog_downloading") if not resume else "Продолжаю скачивание...", fg=_c("TEXT_DIM"))

            def worker():
                try:
                    entry = local_llm_client.install_catalog_model(
                        m["id"],
                        progress_cb=lambda line: _safe_after(0, lambda: action_status_lbl.config(text=line, fg=_c("TEXT_DIM"))),
                        cancelled_flag=download_cancelled,
                        resume=resume,
                    )
                    _safe_after(0, lambda: _finish_download(entry, m))
                except InterruptedError:
                    _safe_after(0, lambda: (
                        action_status_lbl.config(text="⏸ Скачивание приостановлено. Нажмите ▶ Продолжить.", fg=_c("TEXT_DIM")),
                        action_btn.config(text=t("local_catalog_resume_btn"), state="normal", bg=_c("BG_ACTIVE")),
                        download_in_progress.__setitem__(0, False),
                    ))
                except Exception as e:
                    err_msg = str(e)
                    _safe_after(0, lambda msg=err_msg: (
                        action_status_lbl.config(text=msg, fg=_c("TEXT_ERROR")),
                        action_btn.config(text=t("local_catalog_download_btn") if not _has_incomplete_download(m.get("filename", "")) else t("local_catalog_resume_btn"), state="normal", bg=_c("BG_ACTIVE")),
                        download_in_progress.__setitem__(0, False),
                    ))

            download_thread[0] = threading.Thread(target=worker, daemon=True)
            download_thread[0].start()

        def _select_from_folder():
            last_dir = local_llm_client.get_last_model_dir()
            file_path = filedialog.askopenfilename(
                title=t("local_select_model_file_title"),
                filetypes=[("Model files", "*.gguf *.bin *.pt *.safetensors"), ("All files", "*.*")],
                initialdir=last_dir or None,
            )
            if file_path:
                local_llm_client.set_last_model_dir(file_path)
                if messagebox.askyesno(t("local_move_model_title"), t("local_move_model_msg"), parent=win):
                    try:
                        entry = local_llm_client.move_model_file(file_path)
                        local_llm_client.set_active_model_id(entry["id"])
                        gpt_client.set_model(entry["id"], "local")
                        gpt_client.set_provider("local")
                        messagebox.showinfo(t("local_model_added_title"), t("local_model_added_msg", entry['label']), parent=win)
                        _invalidate_page("local")
                        show_page_with_style("local")
                    except Exception as e:
                        messagebox.showerror(t("chat_err_title"), str(e), parent=win)

        def _discard_cached_download():
            m = selected_model[0]
            if not m:
                return
            filename = m.get("filename", "")
            if not filename or not _has_incomplete_download(filename):
                return
            if not messagebox.askyesno(
                t("local_catalog_discard_confirm_title"),
                t("local_catalog_discard_confirm_msg", m.get("label", filename)),
                parent=win,
            ):
                return
            local_llm_client.discard_incomplete_download(filename)
            _update_catalog_info()
            action_status_lbl.config(text=t("local_catalog_discard_done"), fg=_c("TEXT_DIM"))

        br = TkFrame(catalog_view, bg=_c("BG_CARD"))
        br.pack(fill="x", pady=(0, 15))
        _make_button(br, t("chat_btn_from_folder"), _select_from_folder, bg=_c("BG_INPUT"), font_size=11, height=1, padx=6, pady=3).pack(side="right", padx=(0, 4))
        action_btn = _make_button(br, t("local_model_install_btn"), _action_model, bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=6, pady=3)
        action_btn.pack(side="right")
        discard_btn = _make_button(br, "🗑 " + t("local_catalog_discard_btn"), _discard_cached_download, bg=_c("BG_INPUT"), font_size=11, height=1, padx=6, pady=3)
        # discard_btn изначально скрыта — показывается через _update_catalog_info только
        # когда у выбранной модели есть незавершённая (кэшированная) закачка
        lb.bind("<Double-Button-1>", _action_model)

        return container

    def build_general_page():
        container = TkFrame(canvas_frame, bg=_c("BG_CARD"))
        container.pack(fill="both", expand=True, padx=20, pady=20)
        TkLabel(
            container, text=t("settings_general_title"),
            bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w", pady=(0, 15))
        TkLabel(
            container, text=t("settings_general_placeholder"),
            bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12),
            anchor="w",
        ).pack(anchor="w")

        return container

    # ── Helpers for API Page ────────────────────────────────────────────────────
    def _open_provider_form_internal(parent, edit_pid=None):
        is_edit = edit_pid is not None
        existing = {}
        if is_edit:
            for p in gpt_client.list_custom_providers():
                if p.get("id") == edit_pid: existing = p; break

        form = tk.Toplevel(parent)
        _set_dark_titlebar(form)
        form.title(t("chat_provider_edit") if is_edit else t("chat_provider_add"))
        form.geometry("480x540")
        form.configure(bg=_c("BG_CARD"))
        form.transient(parent)
        form.grab_set()

        def _f(p, l, i="", h=1):
            TkLabel(p, text=l, bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12), anchor="w").pack(fill="x", padx=16, pady=(10, 3))
            if h == 1:
                v = tk.StringVar(value=i); e = tk.Entry(p, textvariable=v, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=1, highlightbackground=_c("BORDER"), highlightcolor=_c("ACCENT"), font=("Segoe UI", 12))
                e.pack(fill="x", padx=16, ipady=5); _bind_text_hotkeys(e); return v, e
            else:
                fr = TkFrame(p, bg=_c("BORDER"), padx=1, pady=1); fr.pack(fill="x", padx=16)
                in_ = TkFrame(fr, bg=_c("BG_INPUT")); in_.pack(fill="x")
                t_ = tk.Text(in_, height=h, wrap="word", bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=0, font=("Segoe UI", 12), padx=6, pady=6)
                t_.insert("1.0", i); t_.pack(fill="x"); _bind_text_hotkeys(t_); return t_, t_

        l_v, _ = _f(form, t("chat_field_label"), existing.get("label", ""))
        u_v, _ = _f(form, t("chat_field_url"), existing.get("url", ""))
        m_i = "\n".join(existing.get("models", []))
        m_t, _ = _f(form, t("chat_field_models"), m_i, h=4)
        f_v, _ = _f(form, t("chat_field_fallback"), existing.get("fallback_model", ""))
        h_i = "\n".join(f"{k}: {v}" for k, v in (existing.get("extra_headers") or {}).items())
        h_t, _ = _f(form, t("chat_field_headers"), h_i, h=3)

        st = TkLabel(form, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12), anchor="w")
        st.pack(fill="x", padx=16, pady=(8, 0))

        def save():
            lbl = (l_v.get() if isinstance(l_v, tk.StringVar) else l_v).strip()
            url = (u_v.get() if isinstance(u_v, tk.StringVar) else u_v).strip()
            raw_m = m_t.get("1.0", "end-1c") if isinstance(m_t, tk.Text) else ""
            mods = [m.strip() for m in raw_m.splitlines() if m.strip()]
            fb = (f_v.get() if isinstance(f_v, tk.StringVar) else f_v).strip()
            raw_h = h_t.get("1.0", "end-1c") if isinstance(h_t, tk.Text) else ""
            ext_h = {k.strip(): v.strip() for line in raw_h.splitlines() if ":" in line for k, _, v in [line.partition(":")]}

            if not url: st.config(text=t("chat_url_empty"), fg=_c("TEXT_ERROR")); return
            if not mods: st.config(text=t("chat_need_model"), fg=_c("TEXT_ERROR")); return

            try:
                if is_edit: gpt_client.update_custom_provider(edit_pid, label=lbl, url=url, models=mods, fallback_model=fb, extra_headers=ext_h)
                else: 
                    pid = lbl.lower().replace(" ", "_")
                    import re; pid = re.sub(r"[^a-z0-9_]", "", pid) or "custom"
                    gpt_client.add_custom_provider(pid, lbl, url, mods, fb or mods[0], ext_h)
                form.destroy(); build_api_page()
            except Exception as e: st.config(text=str(e), fg=_c("TEXT_ERROR"))

        br = TkFrame(form, bg=_c("BG_CARD"))
        br.pack(fill="x", padx=16, pady=(6, 16))
        _make_button(br, t("chat_btn_cancel_x"), lambda: form.destroy(), bg=_c("BG_INPUT"), font_size=11, height=1, padx=6, pady=3).pack(side="right", padx=(4, 0))
        _make_button(br, t("chat_btn_save"), save, bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=6, pady=3).pack(side="right")

    def _open_catalogue_internal(parent):
        cat = gpt_client.PROVIDER_CATALOGUE
        dlg = tk.Toplevel(parent); _set_dark_titlebar(dlg); dlg.title(t("chat_catalogue_win")); dlg.geometry("560x520"); dlg.configure(bg=_c("BG_CARD")); dlg.transient(parent); dlg.grab_set()
        TkLabel(dlg, text=t("chat_catalogue_header"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 6))
        lo = TkFrame(dlg, bg=_c("BORDER"), padx=1, pady=1); lo.pack(fill="both", expand=True, padx=16)
        sc = tk.Scrollbar(lo); sc.pack(side="right", fill="y")
        lb = tk.Listbox(lo, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), selectbackground=_c("ACCENT"), selectforeground="#ffffff", activestyle="none", relief="flat", highlightthickness=0, font=("Segoe UI", 12), yscrollcommand=sc.set); lb.pack(fill="both", expand=True); sc.config(command=lb.yview)
        already = set(pid for pid, _, _ in _all_provider_entries())
        for e in cat: lb.insert(tk.END, f"{e['label']}{'  ✓' if e['id'] in already else ''}  —  {e['notes']}")
        
        def add():
            sel = lb.curselection()
            if not sel: return
            e = cat[sel[0]]
            gpt_client.add_custom_provider(e['id'], e['label'], e['url'], e['models'], e['models'][0] if e['models'] else "", e.get('extra_headers', {}))
            dlg.destroy(); build_api_page()
        
        br = TkFrame(dlg, bg=_c("BG_CARD")); br.pack(fill="x", padx=16, pady=(8, 16))
        _make_button(br, t("chat_btn_close_x"), lambda: dlg.destroy(), bg=_c("BG_INPUT"), font_size=11, height=1, padx=6, pady=3).pack(side="right", padx=(4, 0))
        _make_button(br, t("chat_btn_add"), add, bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=6, pady=3).pack(side="right")
        lb.bind("<Double-Button-1>", add)

    # ── Environment Section (карточка «Системное окружение» в Local Page) ──────
    def _log_env_error(stage: str, full_trace: str):
        """Пишет traceback в файл рядом с приложением — единственный способ его
        увидеть, если приложение запущено без консоли (pythonw/portable)."""
        try:
            from engine.paths import BASE_DIR
            log_path = os.path.join(BASE_DIR, "env_error_log.txt")
        except Exception:
            log_path = "env_error_log.txt"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"── {datetime.now().isoformat()} — {stage} ──\n{full_trace}\n\n")
        except Exception:
            pass

    def _build_environment_section(container):
        """Карточка «Системное окружение»: проверка CPU/GPU, статус llama-cpp-python
        и (пере)установка библиотеки. Логика вынесена в auto_install_local_ai."""
        from engine.gui.chat_window.auto_install_local_ai import LocalAIInstallController

        # Очистить "залипший" чекпоинт, если библиотека уже установлена
        try:
            LocalAIInstallController().cleanup_orphaned_checkpoint()
        except Exception:
            pass

        card_outer = tk.Frame(container, bg=_c("BORDER"))
        card_outer.pack(fill="x", pady=(0, 15))
        card = tk.Frame(card_outer, bg=_c("BG_CARD"))
        card.pack(fill="x", padx=1, pady=1)

        header = TkFrame(card, bg=_c("BG_CARD"))
        header.pack(fill="x", padx=14, pady=(12, 6))
        TkLabel(header, text=t("env_section_title"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
                font=("Segoe UI", 13, "bold"), anchor="w").pack(side="left")

        body = TkFrame(card, bg=_c("BG_CARD"))
        body.pack(fill="x", padx=14, pady=(0, 14))

        status_lbl = TkLabel(body, text=t("env_status_hint"),
                              bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 12),
                              anchor="w", wraplength=480, justify="left")
        status_lbl.pack(fill="x", pady=(4, 10))

        btn_row = TkFrame(body, bg=_c("BG_CARD"))
        btn_row.pack(fill="x")

        # ── Лог-область (изначально скрыта, раскрывается при запуске процесса) ──
        log_frame = TkFrame(body, bg=_c("BORDER"), padx=1, pady=1)

        log_inner = TkFrame(log_frame, bg=_c("BG_INPUT"))
        log_inner.pack(fill="both", expand=True)
        log_sc = tk.Scrollbar(log_inner)
        log_sc.pack(side="right", fill="y")
        log_txt = tk.Text(
            log_inner, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"),
            relief="flat", highlightthickness=0, font=("Consolas", 11), wrap="word",
            state="disabled", yscrollcommand=log_sc.set, height=8,
        )
        log_txt.pack(fill="both", expand=True, padx=6, pady=6)
        log_sc.config(command=log_txt.yview)
        _bind_text_hotkeys(log_txt)

        log_visible = [False]
        log_was_shown = [False]

        # ── Полный лог: отдельный, ничем не урезаемый буфер ────────────────────
        # Мини-консоль (log_txt) намеренно схлопывает \r-прогресс (pip/cmake),
        # чтобы не зависать на больших объёмах вывода. Полный лог должен хранить
        # ВООБЩЕ ВСЁ, что пришло через log_cb, независимо от этой оптимизации —
        # иначе окно "полного лога" просто дублирует урезанный снимок мини-консоли.
        _full_log_lines = []
        _full_log_ref = {"txt": None}

        def _safe_config(widget, **kwargs):
            """Безопасный config: не падает, если виджет уже уничтожен."""
            try:
                if widget.winfo_exists():
                    widget.config(**kwargs)
            except tk.TclError:
                pass

        def _append_log(line):
            def _do():
                # ── Полный лог: пишем ВСЕГДА, без схлопывания \r-прогресса ──
                # Это единственное место, где строка попадает в приложение,
                # так что именно тут должен наполняться полный буфер —
                # до и независимо от любых оптимизаций мини-консоли ниже.
                full_line = line[1:] if line.startswith("\r") else line
                _full_log_lines.append(full_line)

                full_widget = _full_log_ref.get("txt")
                if full_widget is not None:
                    try:
                        if full_widget.winfo_exists():
                            full_widget.insert("end", full_line + "\n")
                            full_widget.see("end")
                        else:
                            _full_log_ref["txt"] = None
                    except Exception:
                        _full_log_ref["txt"] = None

                # ── Мини-консоль: схлопывает \r-прогресс pip/cmake в одну
                # строку, чтобы не зависать на больших объёмах вывода ──
                if not log_txt.winfo_exists():
                    return
                log_txt.config(state="normal")
                if line.startswith("\r"):
                    # Прогресс-бар pip: заменить последнюю строку
                    last_line = int(log_txt.index("end-1c").split(".")[0])
                    if last_line > 1:
                        log_txt.delete(f"{last_line-1}.0", "end-1c")
                    log_txt.insert("end-1c", line[1:])
                else:
                    log_txt.insert("end", line + "\n")
                log_txt.see("end")
                log_txt.config(state="disabled")
            _safe_after(0, _do)

        def _show_log(visible=True):
            log_visible[0] = visible
            if visible:
                log_was_shown[0] = True
                if log_frame.winfo_exists() and not log_frame.winfo_ismapped():
                    log_frame.pack(fill="x", pady=(10, 0), expand=False)
                    log_frame.pack_propagate(False)
                    log_frame.config(height=140)
                if log_toggle_btn.winfo_exists():
                    log_toggle_btn.config(text="▲")
                    log_toggle_btn.pack(side="left", padx=(4, 0))
                if log_full_btn.winfo_exists():
                    log_full_btn.pack(side="left", padx=(4, 0))
            else:
                if log_frame.winfo_exists() and log_frame.winfo_ismapped():
                    log_frame.pack_forget()
                if log_was_shown[0]:
                    if log_toggle_btn.winfo_exists():
                        log_toggle_btn.config(text="▼")
                        log_toggle_btn.pack(side="left", padx=(4, 0))
                    if log_full_btn.winfo_exists():
                        log_full_btn.pack(side="left", padx=(4, 0))
                else:
                    if log_toggle_btn.winfo_exists():
                        log_toggle_btn.pack_forget()
                    if log_full_btn.winfo_exists():
                        log_full_btn.pack_forget()

        def _toggle_log():
            _show_log(not log_visible[0])

        def _show_full_log():
            """Открыть полный лог в отдельном окне.

            Источник — независимый несокращаемый буфер _full_log_lines,
            а не мини-консоль (та схлопывает \\r-прогресс ради производительности
            и поэтому не хранит всю историю). Пока окно открыто, новые строки
            дописываются сюда же живьём через _full_log_ref."""
            full_text = "\n".join(_full_log_lines)

            dlg = tk.Toplevel(win)
            _set_dark_titlebar(dlg)
            dlg.title(t("env_log_full_title"))
            dlg.geometry("720x520")
            dlg.configure(bg=_c("BG_CARD"))
            dlg.transient(win)

            outer = TkFrame(dlg, bg=_c("BORDER"), padx=1, pady=1)
            outer.pack(fill="both", expand=True, padx=16, pady=(16, 12))
            inner = TkFrame(outer, bg=_c("BG_INPUT"))
            inner.pack(fill="both", expand=True)
            sc = tk.Scrollbar(inner)
            sc.pack(side="right", fill="y")
            txt = tk.Text(
                inner, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"),
                relief="flat", highlightthickness=0, font=("Consolas", 11), wrap="word",
                yscrollcommand=sc.set,
            )
            txt.pack(fill="both", expand=True, padx=6, pady=6)
            sc.config(command=txt.yview)
            _bind_text_hotkeys(txt)

            txt.insert("1.0", full_text)
            txt.see("end")

            # Регистрируем виджет — пока окно открыто, _append_log будет
            # дописывать сюда новые строки в реальном времени.
            _full_log_ref["txt"] = txt

            def _on_full_log_close():
                _full_log_ref["txt"] = None
                dlg.destroy()

            dlg.protocol("WM_DELETE_WINDOW", _on_full_log_close)

            # Контекстное меню: копировать всё / выделенное
            ctx = tk.Menu(txt, tearoff=0, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"),
                          activebackground=_c("ACCENT"), activeforeground="#ffffff")
            ctx.add_command(label=t("ctx_select_all"), command=lambda: txt.tag_add("sel", "1.0", "end"))
            ctx.add_command(label=t("env_log_copy_selection"),
                            command=lambda: dlg.clipboard_append(txt.selection_get()))
            ctx.add_command(label=t("env_log_copy_all"),
                            command=lambda: (txt.tag_add("sel", "1.0", "end"),
                                             dlg.clipboard_append(txt.get("1.0", "end-1c"))))
            txt.bind("<Button-3>", lambda e: ctx.post(e.x_root, e.y_root))
            txt.bind("<Control-Button-1>", lambda e: ctx.post(e.x_root, e.y_root))

            def _copy_all():
                dlg.clipboard_clear()
                dlg.clipboard_append(txt.get("1.0", "end-1c"))

            def _copy_selection():
                try:
                    selected = txt.selection_get()
                    dlg.clipboard_clear()
                    dlg.clipboard_append(selected)
                except tk.TclError:
                    pass

            br = TkFrame(dlg, bg=_c("BG_CARD"))
            br.pack(fill="x", padx=16, pady=(0, 16))
            _make_button(br, t("env_log_copy_all"), _copy_all,
                         bg=_c("BG_INPUT"), font_size=11, height=1, padx=8, pady=3).pack(side="left", padx=(0, 6))
            _make_button(br, t("env_log_copy_selection"), _copy_selection,
                         bg=_c("BG_INPUT"), font_size=11, height=1, padx=8, pady=3).pack(side="left")
            _make_button(br, t("chat_btn_close_x"), _on_full_log_close,
                         bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=8, pady=3).pack(side="right")

        def _set_buttons(checking=False, installing=False):
            if checking:
                _safe_config(check_btn, state="disabled", text=t("env_btn_checking"))
                _safe_config(install_btn, state="disabled", text=t("env_btn_install_short"))
                _safe_config(remove_btn, state="disabled")
            elif installing:
                _safe_config(check_btn, state="disabled", text=t("env_btn_check_short"))
                _safe_config(install_btn, state="disabled", text=t("env_btn_installing"))
                _safe_config(remove_btn, state="disabled")
            else:
                _safe_config(check_btn, state="normal", text=t("env_btn_check_short"))
                _safe_config(install_btn, state="normal", text=t("env_btn_install_short"))
                _safe_config(remove_btn, state="normal")

        def _set_status(text, color_key):
            color_map = {
                "success": _c("TEXT_SUCCESS"),
                "error": _c("TEXT_ERROR"),
                "dim": _c("TEXT_DIM"),
                "main": _c("TEXT_MAIN"),
            }
            _safe_config(status_lbl, text=text, fg=color_map.get(color_key, _c("TEXT_DIM")))

        controller = LocalAIInstallController(
            log_cb=_append_log,
            status_cb=_set_status,
            buttons_cb=lambda c, i: _set_buttons(checking=c, installing=i),
            error_cb=lambda title, tb: _log_env_error(title, tb),
        )

        def _run_check():
            _show_log(True)
            controller.check_environment()

        def _prompt_resume_and_install():
            stage = controller.get_resume_stage()
            if stage:
                resume = messagebox.askyesno(
                    t("env_resume_title"),
                    t("env_resume_msg", stage),
                    parent=win,
                )
            else:
                resume = False
            controller.install(resume=resume)

        def _run_uninstall():
            if not messagebox.askyesno(t("env_uninstall_title"), t("env_uninstall_msg"), parent=win):
                return
            controller.uninstall()

        def _cancel_process():
            controller.request_cancel()

        def _clear_log():
            log_txt.config(state="normal")
            log_txt.delete("1.0", "end")
            log_txt.config(state="disabled")
            _full_log_lines.clear()
            full_widget = _full_log_ref.get("txt")
            if full_widget is not None:
                try:
                    if full_widget.winfo_exists():
                        full_widget.delete("1.0", "end")
                    else:
                        _full_log_ref["txt"] = None
                except Exception:
                    _full_log_ref["txt"] = None

        def _copy_log():
            log_txt.config(state="normal")
            content = log_txt.get("1.0", "end-1c")
            log_txt.config(state="disabled")
            try:
                body.clipboard_clear()
                body.clipboard_append(content)
            except Exception:
                pass

        # ── Контекстное меню ───────────────────────────────────────────────────
        menu = tk.Menu(body, tearoff=0, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"),
                       activebackground=_c("ACCENT"), activeforeground="#ffffff",
                       relief="flat", bd=0)
        menu.add_command(label=t("env_ctx_copy_log"), command=_copy_log)
        menu.add_command(label=t("env_ctx_clear_log"), command=_clear_log)
        menu.add_separator()
        menu.add_command(label=t("env_ctx_cancel"), command=_cancel_process, state="disabled")
        menu.add_command(label=t("env_ctx_hide_log"), command=lambda: _show_log(False))
        menu.add_command(label=t("env_ctx_show_log"), command=lambda: _show_log(True))

        def _update_menu_state():
            if controller.is_running():
                menu.entryconfig(t("env_ctx_cancel"), state="normal")
            else:
                menu.entryconfig(t("env_ctx_cancel"), state="disabled")

        def _show_context_menu(event):
            _update_menu_state()
            menu.post(event.x_root, event.y_root)

        for widget in (body, status_lbl, btn_row, log_txt):
            widget.bind("<Button-3>", _show_context_menu)
            widget.bind("<Control-Button-1>", _show_context_menu)

        check_btn = _make_button(btn_row, t("env_btn_check_short"), _run_check,
                                 bg=_c("BG_INPUT"), font_size=10, height=1, padx=6, pady=3)
        check_btn.pack(side="left", padx=(0, 4))
        install_btn = _make_button(btn_row, t("env_btn_install_short"), _prompt_resume_and_install,
                                   bg=_c("BG_ACTIVE"), font_size=10, height=1, padx=6, pady=3)
        install_btn.pack(side="left")
        remove_btn = _make_button(btn_row, "🗑", _run_uninstall,
                                  bg=_c("BG_INPUT"), font_size=10, height=1, width=3, padx=4, pady=3)
        remove_btn.pack(side="left", padx=(4, 0))

        # Стрелка сворачивания лога (изначально скрыта, появляется вместе с логом)
        log_toggle_btn = _make_button(
            btn_row, "▲", _toggle_log,
            bg=_c("BG_INPUT"), font_size=10, height=1, width=3, padx=4, pady=3,
        )
        # Кнопка открытия полного лога в отдельном окне
        log_full_btn = _make_button(
            btn_row, t("env_log_full_btn"), _show_full_log,
            bg=_c("BG_INPUT"), font_size=10, height=1, width=3, padx=4, pady=3,
        )

        # Проверка не запускается автоматически — только по кнопке "Проверить"
        pass

    # ── Sidebar Menu Buttons ──────────────────────────────────────────────────
    def create_menu_btn(text, page_id):
        btn = TkButton(
            sidebar, text=text,
            bg=_c("BG_CARD"), fg=_c("TEXT_DIM"),
            activebackground=_c("BG_INPUT"), activeforeground=_c("TEXT_MAIN"),
            relief="flat", bd=0, font=("Segoe UI", 13),
            anchor="w", cursor="hand2",
            command=lambda: show_page(page_id)
        )
        btn.pack(fill="x", padx=10, pady=2)
        return btn

    btn_gen = create_menu_btn(t("settings_menu_general"), "general")
    btn_api = create_menu_btn(t("settings_menu_api"), "api")
    btn_loc = create_menu_btn(t("settings_menu_local"), "local")

    def refresh_menu_style():
        for b, pid in [(btn_gen, "general"), (btn_api, "api"), (btn_loc, "local")]:
            if current_page[0] == pid:
                b.config(fg=_c("TEXT_MAIN"), bg=_c("BG_INPUT"))
            else:
                b.config(fg=_c("TEXT_DIM"), bg=_c("BG_CARD"))

    old_show_page = show_page
    def show_page_with_style(pid):
        old_show_page(pid)
        refresh_menu_style()
    
    btn_gen.config(command=lambda: show_page_with_style("general"))
    btn_api.config(command=lambda: show_page_with_style("api"))
    btn_loc.config(command=lambda: show_page_with_style("local"))

    show_page_with_style("api")
    
    def close_settings(event=None):
        state._settings_window = None
        try: win.grab_release()
        except Exception: pass
        try: win.destroy()
        except Exception: pass
        return "break"

    win.bind("<Escape>", close_settings)
    win.protocol("WM_DELETE_WINDOW", close_settings)
    win.focus_set()
    return "break"

# Inter-module imports
from engine.gui.chat_window.engine.utils import _now_ts, _now_full, _approx_tokens, _ai_display_name, _build_editor_compose_prompt
from engine.gui.chat_window.engine.sessions import _load_sessions, _save_sessions, _enforce_limits, _create_session_dict, _get_current_session, _update_session_title_if_needed, _messages_for_api
from engine.gui.chat_window.engine.generation import _run_generation
from engine.gui.chat_window.ui_utils import _c, _safe_after, _widget_exists, _set_dark_titlebar, _get_app_parent, _show_window, _call_and_break, _ask_simple_text, _make_button, _set_button_text, _set_button_state, _is_descendant, _get_widget_text, _select_all_widget, _paste_clipboard_into_widget, _copy_to_clipboard
from engine.gui.chat_window.hotkeys import _event_has_ctrl, _event_has_shift, _match_hotkey, _on_ctrl_keypress, _handle_text_ctrl, _handle_window_ctrl, _bind_window_hotkeys, _bind_text_hotkeys
from engine.gui.chat_window.placeholders import _create_placeholder_overlay, _sync_text_placeholder, _refresh_placeholder_state, _update_input_placeholder_text
from engine.gui.chat_window.chat_scroll import _is_chat_near_bottom, _scroll_chat_to_bottom, _show_new_message_indicator, _hide_new_message_indicator, _scroll_to_new_message, _chat_mousewheel
from engine.gui.chat_window.chat_history import _refresh_session_list, _on_session_select, new_chat, delete_current_chat, clear_chat_history
from engine.gui.chat_window.chat_messages import _add_message_bubble, _add_system_message, _resize_bubble_text, content_lines_estimate, _lighten_color, _selected_bubble_frame_get, _select_bubble, _on_bubble_text_click, _show_bubble_context_menu, _update_wraplengths, _render_current_session, _add_empty_state, _destroy_empty_state_if_any, _clear_messages_ui
from engine.gui.chat_window.chat_input import _focus_chat_input, _reset_editor_mode, _input_has_placeholder, _set_input_placeholder, _clear_input_placeholder, _get_input_text, _clear_input_text, _resize_input, _update_token_counter, _paste_into_input, _on_input_focus_in, _on_input_focus_out, _on_input_key_release, _on_enter, _submit_prompt, send_chat_message, _insert_prompt_into_chat_input
from engine.gui.chat_window.chat_typing import _show_typing, _animate_typing, _hide_typing
from engine.gui.chat_window.chat_actions import _send_to_main_editor, _stop_generation, _set_generation_ui, improve_text_with_gpt, paste_from_editor, set_chat_status, append_chat_message
from engine.gui.chat_window.chat_export import export_current_chat
from engine.gui.chat_window.chat_search import open_search
from engine.gui.chat_window.chat_editor import _show_editor_preview, _hide_editor_preview, open_editor_text_window, _get_selected_or_all_text, _show_editor_window
from engine.gui.chat_window import init, open_chat_window