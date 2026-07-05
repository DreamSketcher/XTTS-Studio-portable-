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

def open_gpt_settings(event=None):
    try:
        from engine import gpt_client
        from engine import local_llm_client
    except Exception as e:
        messagebox.showerror("Настройки AI", f"Не удалось загрузить модули AI: {e}", parent=_get_app_parent() or state._root)
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
    win.title(t("chat_settings_win_title"))
    win.geometry("850x700")
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
        sidebar, text="Настройки AI",
        bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
        font=("Segoe UI", 14, "bold"),
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
        canvas.configure(scrollregion=canvas.bbox("all"))

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

    def show_page(page_id):
        for child in canvas_frame.winfo_children():
            child.destroy()
        
        if page_id == "api":
            build_api_page()
        elif page_id == "local":
            build_local_page()
        elif page_id == "general":
            build_general_page()
        
        update_scroll_region()
        current_page[0] = page_id

    # ── API Page implementation ───────────────────────────────────────────────
    def build_api_page():
        container = TkFrame(canvas_frame, bg=_c("BG_CARD"))
        container.pack(fill="both", expand=True, padx=20, pady=20)

        TkLabel(
            container, text=t("chat_providers_header"),
            bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 16, "bold"),
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
                
                tk.Label(header, text=arrow, bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), width=2).pack(side="left")
                tk.Label(header, text=dot, bg=_c("BG_CARD"), font=("Segoe UI", 12)).pack(side="left", padx=(0, 6))
                
                title_box = tk.Frame(header, bg=_c("BG_CARD"))
                title_box.pack(side="left", fill="x", expand=True)
                
                tk.Label(title_box, text=info.get("label", pid), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12), anchor="w").pack(anchor="w")
                
                cur_model = gpt_client.get_model(pid)
                has_key = bool(gpt_client.get_api_key(pid))
                sub = f"{'✅ ключ задан' if has_key else '❌ нет ключа'} · {cur_model or '—'}"
                tk.Label(title_box, text=sub, bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 10), anchor="w").pack(anchor="w")
                
                if is_active:
                    tk.Label(header, text="АКТИВНЫЙ", bg=_c("BG_CARD"), fg=_c("TEXT_SUCCESS"), font=("Segoe UI", 10, "bold")).pack(side="right")
                
                header.bind("<Button-1>", lambda e, p=pid: _toggle_card(p))
                for w in title_box.winfo_children():
                    w.bind("<Button-1>", lambda e, p=pid: _toggle_card(p))

                if not is_expanded: continue
                
                body = tk.Frame(card, bg=_c("BG_CARD"))
                body.pack(fill="x", padx=12, pady=(0, 12))
                tk.Frame(body, bg=_c("BORDER"), height=1).pack(fill="x", pady=(0, 10))
                
                TkLabel(body, text="API Key", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 11), anchor="w").pack(fill="x", pady=(0, 4))
                card_key_var = tk.StringVar(value=gpt_client.get_api_key(pid))
                key_row = tk.Frame(body, bg=_c("BG_CARD"))
                key_row.pack(fill="x")
                ke = tk.Entry(key_row, textvariable=card_key_var, show="•", bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=1, highlightbackground=_c("BORDER"), highlightcolor=_c("ACCENT"), font=("Consolas", 11))
                ke.pack(side="left", fill="x", expand=True, ipady=5)
                _bind_text_hotkeys(ke)
                
                show_v = tk.BooleanVar(value=False)
                tk.Checkbutton(key_row, text="👁", variable=show_v, command=lambda e=ke, v=show_v: e.config(show="" if v.get() else "•"), bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), selectcolor=_c("BG_INPUT"), activebackground=_c("BG_CARD"), relief="flat", font=("Segoe UI", 10)).pack(side="left", padx=(6, 0))
                
                hint = info.get("key_hint", "")
                if hint:
                    url = hint if hint.startswith("http") else f"https://{hint}"
                    link_lbl = tk.Label(body, text=hint, bg=_c("BG_CARD"), fg=_c("ACCENT"), font=("Segoe UI", 11), cursor="hand2", anchor="w")
                    link_lbl.pack(fill="x", pady=(3, 8))
                    link_lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

                TkLabel(body, text="Модель", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 11), anchor="w").pack(fill="x", pady=(4, 4))
                models = list(info.get("models", []) or [])
                card_model_var = tk.StringVar(value=cur_model or (models[0] if models else ""))
                if models:
                    for m in models:
                        tk.Radiobutton(body, text=m, variable=card_model_var, value=m, bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), selectcolor=_c("BG_INPUT"), activebackground=_c("BG_CARD"), font=("Segoe UI", 11), anchor="w", cursor="hand2").pack(fill="x", anchor="w")
                else:
                    TkLabel(body, text="Список моделей пуст.", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11)).pack(anchor="w")
                
                card_status = TkLabel(body, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 10), anchor="w")
                card_status.pack(fill="x", pady=(8, 4))
                
                def _save_card(p=pid, kv=card_key_var, mv=card_model_var, st=card_status):
                    try:
                        gpt_client.set_api_key(kv.get().strip(), p)
                        if mv.get(): gpt_client.set_model(mv.get(), p)
                        st.config(text="💾 Сохранено", fg=_c("TEXT_SUCCESS"))
                        _rebuild_accordion()
                    except Exception as e: st.config(text=str(e), fg=_c("TEXT_ERROR"))
                
                def _test_card(p=pid, kv=card_key_var, st=card_status):
                    st.config(text="Проверка ключа...", fg=_c("TEXT_DIM"))
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
                _make_button(btn_row, "🔑 Проверить", _test_card, bg=_c("BG_INPUT"), font_size=10, height=1, padx=6, pady=2).pack(side="left", fill="x", expand=True, padx=(0, 4))
                _make_button(btn_row, "💾 Сохранить", _save_card, bg=_c("BG_INPUT"), font_size=10, height=1, padx=6, pady=2).pack(side="left", fill="x", expand=True, padx=(0, 4))
                if not is_active:
                    _make_button(btn_row, "✓ Активным", _activate_card, bg=_c("BG_ACTIVE"), font_size=10, height=1, padx=6, pady=2).pack(side="left", fill="x", expand=True, padx=(0, 4))
                
                if is_custom:
                    def _edit_this(p=pid): _open_provider_form(edit_pid=p)
                    def _delete_this(p=pid, lbl=info.get("label", pid)):
                        if messagebox.askyesno("Удалить провайдер", f"Удалить «{lbl}»?", parent=win):
                            gpt_client.delete_custom_provider(p)
                            _rebuild_accordion()
                    _make_button(btn_row, "✎", _edit_this, bg=_c("BG_INPUT"), font_size=10, height=1, width=3, padx=4, pady=2).pack(side="left", padx=(0, 4))
                    _make_button(btn_row, "🗑", _delete_this, bg=_c("BG_INPUT"), font_size=10, height=1, width=3, padx=4, pady=2).pack(side="left")
                else:
                    def _hide_this(p=pid, lbl=info.get("label", pid)):
                        if messagebox.askyesno("Скрыть провайдер", f"Скрыть «{lbl}»?", parent=win):
                            gpt_client.hide_provider(p)
                            _rebuild_accordion()
                    _make_button(btn_row, "🚫 Скрыть", _hide_this, bg=_c("BG_INPUT"), font_size=10, height=1, padx=6, pady=2).pack(side="left", fill="x", expand=True)

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
            form.title("Редактировать провайдер" if is_edit else "Добавить провайдер")
            form.geometry("480x540")
            form.configure(bg=_c("BG_CARD"))
            form.transient(win)
            form.grab_set()

            def _f(p, l, i="", h=1):
                TkLabel(p, text=l, bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 11), anchor="w").pack(fill="x", padx=16, pady=(10, 3))
                if h == 1:
                    v = tk.StringVar(value=i); e = tk.Entry(p, textvariable=v, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=1, highlightbackground=_c("BORDER"), highlightcolor=_c("ACCENT"), font=("Segoe UI", 11))
                    e.pack(fill="x", padx=16, ipady=5); _bind_text_hotkeys(e); return v, e
                else:
                    fr = TkFrame(p, bg=_c("BORDER"), padx=1, pady=1); fr.pack(fill="x", padx=16)
                    in_ = TkFrame(fr, bg=_c("BG_INPUT")); in_.pack(fill="x")
                    t_ = tk.Text(in_, height=h, wrap="word", bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=0, font=("Segoe UI", 11), padx=6, pady=6)
                    t_.insert("1.0", i); t_.pack(fill="x"); _bind_text_hotkeys(t_); return t_, t_

            l_v, _ = _f(form, "Название", existing.get("label", ""))
            u_v, _ = _f(form, "URL эндпоинта", existing.get("url", ""))
            m_i = "\n".join(existing.get("models", []))
            m_t, _ = _f(form, "Модели", m_i, h=4)
            f_v, _ = _f(form, "Fallback модель", existing.get("fallback_model", ""))
            h_i = "\n".join(f"{k}: {v}" for k, v in (existing.get("extra_headers") or {}).items())
            h_t, _ = _f(form, "Доп. заголовки", h_i, h=3)

            st = TkLabel(form, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), anchor="w")
            st.pack(fill="x", padx=16, pady=(8, 0))

            def save():
                lbl = (l_v.get() if isinstance(l_v, tk.StringVar) else l_v).strip()
                url = (u_v.get() if isinstance(u_v, tk.StringVar) else u_v).strip()
                raw_m = m_t.get("1.0", "end-1c") if isinstance(m_t, tk.Text) else ""
                mods = [m.strip() for m in raw_m.splitlines() if m.strip()]
                fb = (f_v.get() if isinstance(f_v, tk.StringVar) else f_v).strip()
                raw_h = h_t.get("1.0", "end-1c") if isinstance(h_t, tk.Text) else ""
                ext_h = {k.strip(): v.strip() for line in raw_h.splitlines() if ":" in line for k, _, v in [line.partition(":")]}

                if not url: st.config(text="URL пуст", fg=_c("TEXT_ERROR")); return
                if not mods: st.config(text="Нет моделей", fg=_c("TEXT_ERROR")); return

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
            _make_button(br, "✕ Отмена", lambda: form.destroy(), bg=_c("BG_INPUT"), font_size=11, height=1, padx=8, pady=3).pack(side="right", padx=(6, 0))
            _make_button(br, "💾 Сохранить", save, bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=8, pady=3).pack(side="right")

    def _open_catalogue_internal(parent):
        cat = gpt_client.PROVIDER_CATALOGUE
        dlg = tk.Toplevel(parent); _set_dark_titlebar(dlg); dlg.title("Каталог провайдеров"); dlg.geometry("560x520"); dlg.configure(bg=_c("BG_CARD")); dlg.transient(parent); dlg.grab_set()
        TkLabel(dlg, text="Выберите провайдера из каталога", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 6))
        lo = TkFrame(dlg, bg=_c("BORDER"), padx=1, pady=1); lo.pack(fill="both", expand=True, padx=16)
        sc = tk.Scrollbar(lo); sc.pack(side="right", fill="y")
        lb = tk.Listbox(lo, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), selectbackground=_c("ACCENT"), selectforeground="#ffffff", activestyle="none", relief="flat", highlightthickness=0, font=("Segoe UI", 11), yscrollcommand=sc.set); lb.pack(fill="both", expand=True); sc.config(command=lb.yview)
        already = set(pid for pid, _, _ in _all_provider_entries())
        for e in cat: lb.insert(tk.END, f"{e['label']}{'  ✓' if e['id'] in already else ''}  —  {e['notes']}")
        
        def add():
            sel = lb.curselection()
            if not sel: return
            e = cat[sel[0]]
            gpt_client.add_custom_provider(e['id'], e['label'], e['url'], e['models'], e['models'][0] if e['models'] else "", e.get('extra_headers', {}))
            dlg.destroy(); build_api_page()
        
        br = TkFrame(dlg, bg=_c("BG_CARD")); br.pack(fill="x", padx=16, pady=(8, 16))
        _make_button(br, "✕ Закрыть", lambda: dlg.destroy(), bg=_c("BG_INPUT"), font_size=11, height=1, padx=8, pady=3).pack(side="right", padx=(6, 0))
        _make_button(br, "＋ Добавить", add, bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=8, pady=3).pack(side="right")
        lb.bind("<Double-Button-1>", add)

    # ── Local Page implementation ─────────────────────────────────────────────
    def build_local_page():
        container = TkFrame(canvas_frame, bg=_c("BG_CARD"))
        container.pack(fill="both", expand=True, padx=20, pady=20)

        TkLabel(
            container, text=t("local_models_header"),
            bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        TkLabel(
            container, text=t("local_models_desc"),
            bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11),
            anchor="w", wraplength=500,
        ).pack(anchor="w", pady=(0, 20))

        # Installed models list
        
        # Installed models list
        list_frame = TkFrame(container, bg=_c("BG_CARD"))
        list_frame.pack(fill="x", pady=(0, 15))
        TkLabel(list_frame, text=t("local_model_active"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 11), anchor="w").pack(fill="x", pady=(0, 6))

        installed = local_llm_client.list_installed_models()
        active_id = local_llm_client.get_active_model_id()

        status_lbl = TkLabel(container, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), anchor="w")

        if not installed:
            TkLabel(list_frame, text="Установленных моделей нет. Добавьте .gguf через «Из папки».", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), anchor="w").pack(fill="x")
        else:
            for m in installed:
                row = TkFrame(list_frame, bg=_c("BG_CARD"))
                row.pack(fill="x", pady=2)
                is_active = m.get("id") == active_id
                dot = "🟢" if is_active else "⚪"
                TkLabel(row, text=f"{dot} {m.get('label', m.get('filename', '?'))}", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 11), anchor="w").pack(side="left", fill="x", expand=True)

                def _activate(mid=m.get("id")):
                    local_llm_client.set_active_model_id(mid)
                    gpt_client.set_model(mid, "local")
                    gpt_client.set_provider("local")
                    status_lbl.config(text="💾 Активировано", fg=_c("TEXT_SUCCESS"))
                    show_page_with_style("local")

                def _remove(mid=m.get("id"), lbl=m.get("label", "")):
                    if messagebox.askyesno("Удалить модель", f"Удалить «{lbl}» из списка? Файл в /models/ останется на диске.", parent=win):
                        local_llm_client.remove_model(mid)
                        show_page_with_style("local")
                if not is_active:
                    _make_button(row, "✓ Активировать", _activate, bg=_c("BG_ACTIVE"), font_size=10, height=1, padx=6, pady=2).pack(side="right", padx=(4, 0))
                _make_button(row, "🗑", _remove, bg=_c("BG_INPUT"), font_size=10, height=1, width=3, padx=4, pady=2).pack(side="right")

        # Catalog Button
        _make_button(
            container, t("local_model_catalog_btn"), 
            lambda: _open_local_catalog(win), 
            bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=12, pady=6
        ).pack(anchor="w", pady=(10, 0))

        status_lbl.pack(fill="x", pady=(10, 0))

    # ── General Page implementation ─────────────────────────────────────────────
    def build_general_page():
        container = TkFrame(canvas_frame, bg=_c("BG_CARD"))
        container.pack(fill="both", expand=True, padx=20, pady=20)
        TkLabel(
            container, text="Общие настройки",
            bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 15))
        TkLabel(
            container, text="Здесь будут дополнительные системные настройки.",
            bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11),
            anchor="w",
        ).pack(anchor="w")

    # ── Helpers for API Page ────────────────────────────────────────────────────
    def _open_provider_form_internal(parent, edit_pid=None):
        is_edit = edit_pid is not None
        existing = {}
        if is_edit:
            for p in gpt_client.list_custom_providers():
                if p.get("id") == edit_pid: existing = p; break

        form = tk.Toplevel(parent)
        _set_dark_titlebar(form)
        form.title("Редактировать провайдер" if is_edit else "Добавить провайдер")
        form.geometry("480x540")
        form.configure(bg=_c("BG_CARD"))
        form.transient(parent)
        form.grab_set()

        def _f(p, l, i="", h=1):
            TkLabel(p, text=l, bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 11), anchor="w").pack(fill="x", padx=16, pady=(10, 3))
            if h == 1:
                v = tk.StringVar(value=i); e = tk.Entry(p, textvariable=v, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=1, highlightbackground=_c("BORDER"), highlightcolor=_c("ACCENT"), font=("Segoe UI", 11))
                e.pack(fill="x", padx=16, ipady=5); _bind_text_hotkeys(e); return v, e
            else:
                fr = TkFrame(p, bg=_c("BORDER"), padx=1, pady=1); fr.pack(fill="x", padx=16)
                in_ = TkFrame(fr, bg=_c("BG_INPUT")); in_.pack(fill="x")
                t_ = tk.Text(in_, height=h, wrap="word", bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), insertbackground=_c("TEXT_MAIN"), relief="flat", highlightthickness=0, font=("Segoe UI", 11), padx=6, pady=6)
                t_.insert("1.0", i); t_.pack(fill="x"); _bind_text_hotkeys(t_); return t_, t_

        l_v, _ = _f(form, "Название", existing.get("label", ""))
        u_v, _ = _f(form, "URL эндпоинта", existing.get("url", ""))
        m_i = "\n".join(existing.get("models", []))
        m_t, _ = _f(form, "Модели", m_i, h=4)
        f_v, _ = _f(form, "Fallback модель", existing.get("fallback_model", ""))
        h_i = "\n".join(f"{k}: {v}" for k, v in (existing.get("extra_headers") or {}).items())
        h_t, _ = _f(form, "Доп. заголовки", h_i, h=3)

        st = TkLabel(form, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), anchor="w")
        st.pack(fill="x", padx=16, pady=(8, 0))

        def save():
            lbl = (l_v.get() if isinstance(l_v, tk.StringVar) else l_v).strip()
            url = (u_v.get() if isinstance(u_v, tk.StringVar) else u_v).strip()
            raw_m = m_t.get("1.0", "end-1c") if isinstance(m_t, tk.Text) else ""
            mods = [m.strip() for m in raw_m.splitlines() if m.strip()]
            fb = (f_v.get() if isinstance(f_v, tk.StringVar) else f_v).strip()
            raw_h = h_t.get("1.0", "end-1c") if isinstance(h_t, tk.Text) else ""
            ext_h = {k.strip(): v.strip() for line in raw_h.splitlines() if ":" in line for k, _, v in [line.partition(":")]}

            if not url: st.config(text="URL пуст", fg=_c("TEXT_ERROR")); return
            if not mods: st.config(text="Нет моделей", fg=_c("TEXT_ERROR")); return

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
        _make_button(br, "✕ Отмена", lambda: form.destroy(), bg=_c("BG_INPUT"), font_size=11, height=1, padx=8, pady=3).pack(side="right", padx=(6, 0))
        _make_button(br, "💾 Сохранить", save, bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=8, pady=3).pack(side="right")

    def _open_catalogue_internal(parent):
        cat = gpt_client.PROVIDER_CATALOGUE
        dlg = tk.Toplevel(parent); _set_dark_titlebar(dlg); dlg.title("Каталог провайдеров"); dlg.geometry("560x520"); dlg.configure(bg=_c("BG_CARD")); dlg.transient(parent); dlg.grab_set()
        TkLabel(dlg, text="Выберите провайдера из каталога", bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 6))
        lo = TkFrame(dlg, bg=_c("BORDER"), padx=1, pady=1); lo.pack(fill="both", expand=True, padx=16)
        sc = tk.Scrollbar(lo); sc.pack(side="right", fill="y")
        lb = tk.Listbox(lo, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), selectbackground=_c("ACCENT"), selectforeground="#ffffff", activestyle="none", relief="flat", highlightthickness=0, font=("Segoe UI", 11), yscrollcommand=sc.set); lb.pack(fill="both", expand=True); sc.config(command=lb.yview)
        already = set(pid for pid, _, _ in _all_provider_entries())
        for e in cat: lb.insert(tk.END, f"{e['label']}{'  ✓' if e['id'] in already else ''}  —  {e['notes']}")
        
        def add():
            sel = lb.curselection()
            if not sel: return
            e = cat[sel[0]]
            gpt_client.add_custom_provider(e['id'], e['label'], e['url'], e['models'], e['models'][0] if e['models'] else "", e.get('extra_headers', {}))
            dlg.destroy(); build_api_page()
        
        br = TkFrame(dlg, bg=_c("BG_CARD")); br.pack(fill="x", padx=16, pady=(8, 16))
        _make_button(br, "✕ Закрыть", lambda: dlg.destroy(), bg=_c("BG_INPUT"), font_size=11, height=1, padx=8, pady=3).pack(side="right", padx=(6, 0))
        _make_button(br, "＋ Добавить", add, bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=8, pady=3).pack(side="right")
        lb.bind("<Double-Button-1>", add)

    def _open_local_catalog(parent):
        catalog = local_llm_client.LOCAL_MODEL_CATALOG
        dlg = tk.Toplevel(parent); _set_dark_titlebar(dlg); dlg.title(t("local_catalog_title")); dlg.geometry("600x550"); dlg.configure(bg=_c("BG_CARD")); dlg.transient(parent); dlg.grab_set()
        TkLabel(dlg, text=t("local_catalog_header"), bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"), font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(15, 10))
        
        list_outer = TkFrame(dlg, bg=_c("BORDER"), padx=1, pady=1); list_outer.pack(fill="both", expand=True, padx=16, pady=(0, 15))
        sc = tk.Scrollbar(list_outer); sc.pack(side="right", fill="y")
        lb = tk.Listbox(list_outer, bg=_c("BG_INPUT"), fg=_c("TEXT_MAIN"), selectbackground=_c("ACCENT"), selectforeground="#ffffff", activestyle="none", relief="flat", highlightthickness=0, font=("Segoe UI", 11), yscrollcommand=sc.set); lb.pack(fill="both", expand=True); sc.config(command=lb.yview)
        
        for m in catalog: lb.insert(tk.END, m['label'])
        
        info_box = TkFrame(dlg, bg=_c("BG_CARD"), pady=10)
        info_box.pack(fill="x", padx=16)
        desc_lbl = TkLabel(info_box, text="", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"), font=("Segoe UI", 11), anchor="w", wraplength=550); desc_lbl.pack(anchor="w")
        link_lbl = TkLabel(info_box, text="", bg=_c("BG_CARD"), fg=_c("ACCENT"), font=("Segoe UI", 11), cursor="hand2", anchor="w"); link_lbl.pack(anchor="w")

        def update_info(e=None):
            sel = lb.curselection()
            if not sel: return
            m = catalog[sel[0]]
            desc_lbl.config(text=t("local_model_meta_desc").format(m['description']))
            link_lbl.config(text=t("local_model_meta_link"))
            link_lbl.bind("<Button-1>", lambda e, u=m['download_link']: webbrowser.open(u))

        lb.bind("<<ListboxSelect>>", update_info)
        
        def install():
            sel = lb.curselection()
            if not sel: return
            messagebox.showinfo(
                "Скачивание пока недоступно",
                "Загрузка моделей из встроенного каталога появится позже. Пока используйте «📁 Из папки».",
                parent=dlg,
            )

        def select_from_folder():
            file_path = filedialog.askopenfilename(
                title="Выберите файл модели",
                filetypes=[("Model files", "*.gguf *.bin *.pt *.safetensors"), ("All files", "*.*")]
            )
            if file_path:
                if messagebox.askyesno("Перемещение модели", "Выбранный файл модели будет перемещен в папку проекта /models/. Продолжить?", parent=dlg):
                    try:
                        entry = local_llm_client.move_model_file(file_path)
                        local_llm_client.set_active_model_id(entry["id"])
                        gpt_client.set_model(entry["id"], "local")
                        gpt_client.set_provider("local")
                        messagebox.showinfo("Модель добавлена", f"«{entry['label']}» перенесена в /models/ и активирована.", parent=dlg)
                        dlg.destroy(); show_page_with_style("local")
                    except Exception as e:
                        messagebox.showerror("Ошибка", str(e), parent=dlg)

        br = TkFrame(dlg, bg=_c("BG_CARD")); br.pack(fill="x", padx=16, pady=(0, 15))
        _make_button(br, "✕ Закрыть", lambda: dlg.destroy(), bg=_c("BG_INPUT"), font_size=11, height=1, padx=8, pady=3).pack(side="right", padx=(6, 0))
        _make_button(br, "📁 Из папки", select_from_folder, bg=_c("BG_INPUT"), font_size=11, height=1, padx=8, pady=3).pack(side="right", padx=(0, 4))
        _make_button(br, t("local_model_install_btn"), install, bg=_c("BG_ACTIVE"), font_size=11, height=1, padx=8, pady=3).pack(side="right")
        lb.bind("<Double-Button-1>", install)

    # ── Sidebar Menu Buttons ──────────────────────────────────────────────────
    def create_menu_btn(text, page_id):
        btn = TkButton(
            sidebar, text=text,
            bg=_c("BG_CARD"), fg=_c("TEXT_DIM"),
            activebackground=_c("BG_INPUT"), activeforeground=_c("TEXT_MAIN"),
            relief="flat", bd=0, font=("Segoe UI", 12),
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
