from __future__ import annotations
import json
import os
import threading
import uuid
from datetime import datetime
from tkinter import filedialog, messagebox
import tkinter as tk

from i18n import t

import engine.gui.chat_window.state as state
from engine.gui.chat_window.custom_widgets import CTK_AVAILABLE, ctk, CTkFrame, CTkLabel, CTkButton, TkFrame, TkLabel, TkButton, TkRawFrame

# Unified style imports
from engine.gui.colors import Colors, scaled_font_size, scaled_size
try:
    from engine.paths import BASE_DIR, ICON_PATH
except Exception:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ICON_PATH = os.path.join(BASE_DIR, "icon.ico")

# For pill style buttons we also use main widgets
try:
    from engine.gui.widgets import CompatCTkFrame, CompatCTkButton, CompatCTkLabel
    HAS_MAIN_WIDGETS = True
except Exception:
    HAS_MAIN_WIDGETS = False
    CompatCTkFrame = CTkFrame
    CompatCTkButton = CTkButton
    CompatCTkLabel = CTkLabel


def _apply_window_icon(win: tk.Toplevel):
    try:
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("XTTSStudio.App")
        except Exception:
            pass
    except Exception:
        pass
    candidates = [ICON_PATH, os.path.join(str(BASE_DIR), "icon.ico"), os.path.join(str(BASE_DIR), "icon.png")]
    ico = None
    png = None
    for p in candidates:
        if p and os.path.isfile(p):
            if p.lower().endswith(".ico") and not ico:
                ico = p
            elif p.lower().endswith(".png") and not png:
                png = p
    if ico:
        try:
            win.iconbitmap(default=ico)
            win.after(200, lambda: win.iconbitmap(default=ico))
        except Exception:
            pass
    try:
        if png:
            photo = tk.PhotoImage(file=png)
            win.iconphoto(True, photo)
            win._icon_photo_ref = photo
    except Exception:
        pass


def _round_btn(parent, text, cmd, diameter=36, primary=False):
    try:
        bg = Colors.BG_ACTIVE if primary else Colors.BG_INPUT
        hover = "#2ea043" if primary else Colors.BG_HOVER
        sd = scaled_size(diameter, min_size=diameter)
        return CompatCTkButton(
            parent, text=text, command=cmd,
            width=sd, height=sd, corner_radius=sd//2,
            fg_color=bg, text_color=Colors.TEXT_MAIN, hover_color=hover,
            border_width=0, font=("Segoe UI", scaled_font_size(15)),
        )
    except Exception:
        # fallback to old _make_button
        return _make_button(parent, text, cmd, bg=_c("BG_INPUT"), font_size=11)


def init(root, colors, create_button_fn, get_text_fn, set_text_fn, placeholder, use_gpt_var=None):
    state._root = root
    state._colors = colors
    state._create_button = create_button_fn
    state._get_text = get_text_fn
    state._set_text = set_text_fn
    state._placeholder = placeholder
    state._use_gpt_var = use_gpt_var
    _load_sessions()


def open_chat_window():
    if state._root is None:
        raise RuntimeError("chat_window.init(...) must be called before open_chat_window().")

    _load_sessions()

    if _widget_exists(state._chat_window):
        _show_window(state._chat_window)
        return

    win = tk.Toplevel(state._root)
    win.title(t("chat_win_title"))
    win.geometry("1050x720")
    win.minsize(640, 600)
    win.resizable(True, True)
    win.configure(bg=_c("BG_DARK"))
    _set_dark_titlebar(win)
    _apply_window_icon(win)

    state._chat_window = win

    # Root layout - dark
    main = TkFrame(win, bg=_c("BG_DARK"))
    main.pack(fill="both", expand=True)

    # Sidebar - rounded card like audio/history
    sidebar_outer = TkFrame(main, bg=_c("BG_DARK"))
    sidebar_outer.pack(side="left", fill="y", padx=(14,6), pady=14)

    sidebar = CompatCTkFrame(sidebar_outer, fg_color=_c("BG_CARD"), corner_radius=20,
                             border_width=1, border_color=_c("BORDER"))
    sidebar.pack(fill="y", expand=True)
    # fixed width via inner frame
    sidebar_inner = TkFrame(sidebar, bg=_c("BG_CARD"))
    sidebar_inner.pack(fill="both", expand=True, padx=2, pady=2)
    sidebar_inner.configure(width=240)
    sidebar_inner.pack_propagate(False)
    try:
        sidebar_inner.config(width=240)
    except Exception:
        pass

    TkLabel(
        sidebar_inner,
        text="XTTS AI",
        bg=_c("BG_CARD"),
        fg=_c("TEXT_MAIN"),
        font=("Segoe UI", scaled_font_size(16), "bold"),
        anchor="w",
    ).pack(fill="x", padx=16, pady=(18, 10))

    # Pill for new chat buttons
    new_pill = CompatCTkFrame(sidebar_inner, fg_color=_c("BG_INPUT"), corner_radius=18,
                              border_width=0)
    new_pill.pack(fill="x", padx=10, pady=(0,10))
    new_row = TkFrame(new_pill, bg=_c("BG_INPUT"))
    new_row.pack(fill="x", padx=8, pady=8)

    state.new_chat_btn = _round_btn(new_row, "＋ " + t("chat_btn_new_chat"), new_chat, diameter=36, primary=True)
    try:
        state.new_chat_btn.configure(width=scaled_size(200, min_size=180), corner_radius=18)
    except Exception:
        pass
    state.new_chat_btn.pack(fill="x", pady=(0,6))

    state.delete_chat_btn = _round_btn(new_row, t("chat_btn_delete_chat"), delete_current_chat, diameter=32)
    try:
        state.delete_chat_btn.configure(fg_color=_c("BG_CARD"), hover_color=_c("BG_HOVER"))
    except Exception:
        pass
    state.delete_chat_btn.pack(fill="x")

    TkLabel(
        sidebar_inner,
        text=t("chat_search_label"),
        bg=_c("BG_CARD"),
        fg=_c("TEXT_DIM"),
        font=("Segoe UI", scaled_font_size(11)),
        anchor="w",
    ).pack(fill="x", padx=16, pady=(12, 8))

    list_outer_border = TkFrame(sidebar_inner, bg=_c("BORDER"))
    list_outer_border.pack(fill="both", expand=True, padx=10, pady=(0, 12))
    list_outer = TkFrame(list_outer_border, bg=_c("BORDER"))
    list_outer.pack(fill="both", expand=True, padx=1, pady=1)

    list_scroll = tk.Scrollbar(list_outer)
    list_scroll.pack(side="right", fill="y")

    state.session_listbox = tk.Listbox(
        list_outer,
        bg=_c("BG_INPUT"),
        fg=_c("TEXT_MAIN"),
        selectbackground=_c("ACCENT"),
        selectforeground="#ffffff",
        activestyle="none",
        relief="flat",
        highlightthickness=0,
        font=("Segoe UI", scaled_font_size(12)),
        yscrollcommand=list_scroll.set,
    )
    state.session_listbox.pack(fill="both", expand=True)
    list_scroll.config(command=state.session_listbox.yview)
    state.session_listbox.bind("<<ListboxSelect>>", _on_session_select)

    # Chat area
    right = TkFrame(main, bg=_c("BG_DARK"))
    right.pack(side="left", fill="both", expand=True, padx=(0,14), pady=14)

    # Header as pill card
    header_card = CompatCTkFrame(right, fg_color=_c("BG_CARD"), corner_radius=18,
                                 border_width=1, border_color=_c("BORDER"))
    header_card.pack(fill="x", pady=(0,10))
    header = TkFrame(header_card, bg=_c("BG_CARD"))
    header.pack(fill="x", padx=12, pady=10)

    TkLabel(
        header,
        text=t("chat_header"),
        bg=_c("BG_CARD"),
        fg=_c("TEXT_MAIN"),
        font=("Segoe UI", scaled_font_size(16), "bold"),
    ).pack(side="left")

    # Header buttons as round
    scroll_bottom_btn = _round_btn(header, "⬇", lambda: _scroll_chat_to_bottom(immediate=True), diameter=36)
    scroll_bottom_btn.pack(side="right", padx=(6,0))

    state.export_btn = _round_btn(header, "⤴", export_current_chat, diameter=36)
    state.export_btn.pack(side="right", padx=(6,0))

    state.settings_btn = _round_btn(header, "⚙", open_gpt_settings, diameter=36)
    state.settings_btn.pack(side="right", padx=(6,0))

    # Status row - pill
    status_card = CompatCTkFrame(right, fg_color=_c("BG_CARD"), corner_radius=14,
                                 border_width=1, border_color=_c("BORDER"))
    status_card.pack(side="bottom", fill="x", pady=(6,0))
    status_row = TkFrame(status_card, bg=_c("BG_CARD"))
    status_row.pack(fill="x", padx=12, pady=8)

    state.chat_status_label = TkLabel(
        status_row,
        text=t("chat_ready"),
        bg=_c("BG_CARD"),
        fg=_c("TEXT_DIM"),
        font=("Segoe UI", scaled_font_size(11)),
        anchor="w",
    )
    state.chat_status_label.pack(side="left", fill="x", expand=True)

    state.chat_token_label = TkLabel(
        status_row,
        text=t("chat_token_counter", 0, 0),
        bg=_c("BG_CARD"),
        fg=_c("TEXT_DIM"),
        font=("Segoe UI", scaled_font_size(11)),
        anchor="e",
    )
    state.chat_token_label.pack(side="right")

    # Actions — pill with round buttons, like audio player controls
    action_card = CompatCTkFrame(right, fg_color=_c("BG_INPUT"), corner_radius=26)
    action_card.pack(side="bottom", fill="x", pady=(8,8))
    action_row = TkFrame(action_card, bg=_c("BG_INPUT"))
    action_row.pack(fill="x", padx=12, pady=8)

    state.improve_btn = CompatCTkButton(
        action_row,
        text=t("chat_btn_improve"),
        command=improve_text_with_gpt,
        fg_color=_c("BG_CARD"),
        text_color=_c("TEXT_MAIN"),
        hover_color=_c("BG_HOVER"),
        corner_radius=18,
        height=scaled_size(40, min_size=36),
        font=("Segoe UI", scaled_font_size(13)),
        cursor="hand2",
    )
    state.improve_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

    state.paste_editor_btn = CompatCTkButton(
        action_row,
        text=t("chat_btn_from_editor"),
        command=paste_from_editor,
        fg_color=_c("BG_CARD"),
        text_color=_c("TEXT_MAIN"),
        hover_color=_c("BG_HOVER"),
        corner_radius=18,
        height=scaled_size(40, min_size=36),
        font=("Segoe UI", scaled_font_size(13)),
        cursor="hand2",
    )
    state.paste_editor_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

    state.clear_btn = CompatCTkButton(
        action_row,
        text=t("chat_btn_clear"),
        command=clear_chat_history,
        fg_color=_c("BG_CARD"),
        text_color=_c("TEXT_MAIN"),
        hover_color=_c("BG_DANGER"),
        corner_radius=18,
        height=scaled_size(40, min_size=36),
        font=("Segoe UI", scaled_font_size(13)),
        cursor="hand2",
    )
    state.clear_btn.pack(side="left", fill="x", expand=True)

    # Input card — bottom, rounded 20 like audio player card
    composer_outer = TkFrame(right, bg=_c("BG_DARK"))
    composer_outer.pack(side="bottom", fill="x", pady=(0, 0))
    state.composer_outer_ref = [composer_outer]

    composer_card = CompatCTkFrame(
        composer_outer,
        fg_color=_c("BG_CARD"),
        corner_radius=20,
        border_width=1,
        border_color=_c("BORDER"),
    )
    composer_card.pack(fill="x")
    state.composer_card_ref = [composer_card]

    hint_row = TkFrame(composer_card, bg=_c("BG_CARD"))
    hint_row.pack(fill="x", padx=16, pady=(12, 6))

    state._hint_text_var = tk.StringVar(value=t("chat_hint_default"))
    _hint_label = TkLabel(
        hint_row,
        textvariable=state._hint_text_var,
        bg=_c("BG_CARD"),
        fg=_c("TEXT_DIM"),
        font=("Segoe UI", scaled_font_size(12)),
        anchor="w",
    )
    _hint_label.pack(side="left", fill="x", expand=True)

    def _toggle_free_chat():
        state._free_chat_mode = not state._free_chat_mode
        try:
            _free_chat_btn.config(
                text=t("chat_free_mode_on") if state._free_chat_mode else t("chat_free_mode"),
                fg=_c("ACCENT") if state._free_chat_mode else _c("TEXT_DIM"),
            )
        except Exception:
            pass
        set_chat_status(t("chat_mode_free") if state._free_chat_mode else t("chat_mode_editor"))
        _mode_label.config(
            text=t("chat_mode_free_small") if state._free_chat_mode else t("chat_mode_editor_small"),
            fg=_c("ACCENT") if state._free_chat_mode else _c("TEXT_MUTED"),
        )

    _free_chat_btn = tk.Button(
        hint_row,
        text=t("chat_free_mode"),
        command=_toggle_free_chat,
        bg=_c("BG_CARD"),
        fg=_c("TEXT_DIM"),
        activebackground=_c("BG_CARD"),
        activeforeground=_c("ACCENT"),
        relief="flat",
        bd=0,
        font=("Segoe UI", scaled_font_size(10)),
        cursor="hand2",
        padx=6,
        pady=0,
    )
    _mode_label = tk.Label(
        hint_row,
        text=t("chat_switch_mode"),
        bg=_c("BG_CARD"),
        fg=_c("TEXT_MUTED"),
        font=("Segoe UI", scaled_font_size(10), "italic"),
    )
    _mode_label.pack(side="right", padx=(0, 6))
    _free_chat_btn.pack(side="right")

    input_row = TkFrame(composer_card, bg=_c("BG_CARD"))
    input_row.pack(fill="x", padx=12, pady=(0, 16))

    input_border = TkRawFrame(input_row, bg=_c("BORDER"),
                           highlightthickness=1, highlightbackground=_c("BORDER"))
    input_border.pack(side="left", fill="x", expand=True, padx=(0, 8))

    input_inner = TkRawFrame(input_border, bg=_c("BG_INPUT"))
    input_inner.pack(fill="x")

    state.chat_input = tk.Text(
        input_inner,
        height=3,
        wrap="word",
        bg=_c("BG_INPUT"),
        fg=_c("TEXT_MAIN"),
        insertbackground=_c("TEXT_MAIN"),
        relief="flat",
        highlightthickness=0,
        font=("Segoe UI", scaled_font_size(13)),
        padx=12,
        pady=12,
        undo=True,
    )
    state.chat_input.pack(fill="x")
    state.chat_input.lift()

    state.chat_input_placeholder_label = _create_placeholder_overlay(
        input_inner,
        state.chat_input,
        t("chat_placeholder_input"),
        x=13,
        y=12,
        fg=_c("TEXT_DIM"),
        bg=_c("BG_INPUT"),
        font=("Segoe UI", scaled_font_size(11), "italic"),
    )

    state.chat_send_btn = _round_btn(input_row, "➤", send_chat_message, diameter=44, primary=True)
    state.chat_send_btn.pack(side="right")

    # Messages scrollable canvas - rounded outer
    canvas_outer_border = CompatCTkFrame(right, fg_color=_c("BORDER"), corner_radius=14)
    canvas_outer_border.pack(side="top", fill="both", expand=True, pady=(0, 10))
    canvas_outer = TkFrame(canvas_outer_border, bg=_c("BORDER"))
    canvas_outer.pack(fill="both", expand=True, padx=1, pady=1)

    state.chat_scrollbar = tk.Scrollbar(canvas_outer)
    state.chat_scrollbar.pack(side="right", fill="y")

    state.chat_canvas = tk.Canvas(
        canvas_outer,
        bg=_c("BG_DARK"),
        highlightthickness=0,
        bd=0,
        yscrollcommand=state.chat_scrollbar.set,
    )
    state.chat_canvas.pack(side="left", fill="both", expand=True)
    state.chat_scrollbar.config(command=state.chat_canvas.yview)

    CHAT_BOTTOM_PADDING = 50
    state.chat_messages_frame = TkFrame(state.chat_canvas, bg=_c("BG_DARK"))
    state.chat_canvas_window = state.chat_canvas.create_window(
        (0, 0),
        window=state.chat_messages_frame,
        anchor="nw",
        width=1,
    )

    def on_frame_configure(event=None):
        try:
            bbox = state.chat_canvas.bbox("all")
            if bbox:
                x0, y0, x1, y1 = bbox
                state.chat_canvas.configure(scrollregion=(x0, y0, x1, y1 + CHAT_BOTTOM_PADDING))
            else:
                state.chat_canvas.configure(scrollregion=bbox)
        except Exception:
            pass

    def on_canvas_configure(event):
        try:
            new_width = event.width
            old_width = getattr(state.chat_canvas, "_last_width", None)
            state.chat_canvas._last_width = new_width
            state.chat_canvas.itemconfig(state.chat_canvas_window, width=new_width)
            if old_width != new_width:
                _update_wraplengths()
        except Exception:
            pass

    state.chat_messages_frame.bind("<Configure>", on_frame_configure)
    state.chat_canvas.bind("<Configure>", on_canvas_configure)

    for target in (win, state.chat_canvas, state.chat_messages_frame):
        try:
            target.bind("<MouseWheel>", _chat_mousewheel, add="+")
            target.bind("<Button-4>", _chat_mousewheel, add="+")
            target.bind("<Button-5>", _chat_mousewheel, add="+")
        except Exception:
            pass

    state.chat_input.bind("<FocusIn>", _on_input_focus_in)
    state.chat_input.bind("<FocusOut>", _on_input_focus_out)
    state.chat_input.bind("<KeyRelease>", _on_input_key_release)
    state.chat_input.bind("<Return>", _on_enter)

    def _chat_input_context_menu(event):
        menu = tk.Menu(
            win, tearoff=0,
            bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
            activebackground=_c("BORDER"),
            activeforeground=_c("TEXT_MAIN"),
            relief="flat", borderwidth=1,
            font=("Segoe UI", scaled_font_size(11)),
        )
        menu.add_command(label=t("ctx_cut"), command=lambda: state.chat_input.event_generate("<<Cut>>"))
        menu.add_command(label=t("ctx_copy"), command=lambda: state.chat_input.event_generate("<<Copy>>"))
        menu.add_command(label=t("ctx_paste"), command=lambda: _paste_clipboard_into_widget(state.chat_input))
        menu.add_separator()
        menu.add_command(label=t("ctx_select_all"), command=lambda: _select_all_widget(state.chat_input))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    state.chat_input.bind("<Button-3>", _chat_input_context_menu)

    def _send_shortcut(event=None):
        if event is not None and _event_has_shift(event):
            return None
        send_chat_message()
        return "break"

    def _new_chat_shortcut(event=None):
        new_chat()
        return "break"

    def _export_shortcut(event=None):
        export_current_chat()
        return "break"

    def _search_shortcut(event=None):
        return open_search(event)

    chat_handlers = {
        "f": _search_shortcut,
        "n": _new_chat_shortcut,
        "s": _export_shortcut,
    }

    _bind_window_hotkeys(win, chat_handlers)
    _bind_text_hotkeys(state.chat_input, chat_handlers)

    def _ctrl_enter(event=None):
        if state._editor_mode and state._editor_preview_content:
            _submit_prompt("", clear_input=True)
            _focus_chat_input()
            return "break"
        send_chat_message()
        return "break"

    win.bind("<Control-Return>", _ctrl_enter)
    state.chat_input.bind("<Control-Return>", _ctrl_enter)

    _refresh_session_list()
    _render_current_session()
    _set_input_placeholder()
    _focus_chat_input()

    def on_close():
        _hide_new_message_indicator()
        _stop_generation(silent=True)
        _stop_generation(silent=True)
        _save_sessions()
        try:
            if _widget_exists(state._search_window):
                state._search_window.destroy()
        except Exception:
            pass
        try:
            if _widget_exists(state._settings_window):
                state._settings_window.destroy()
        except Exception:
            pass
        try:
            if _widget_exists(state._editor_window):
                state._editor_window.destroy()
        except Exception:
            pass

        state._chat_window = None
        state._search_window = None
        state._settings_window = None
        state._editor_window = None
        state._hint_text_var = None
        state._editor_mode = False
        state._free_chat_mode = False
        state._editor_preview_frame = None
        state._editor_preview_text = None
        state._editor_preview_content = ""
        state.session_listbox = None
        state.chat_canvas = None
        state.chat_scrollbar = None
        state.chat_messages_frame = None
        state.chat_canvas_window = None
        state.chat_input = None
        state.chat_input_placeholder_label = None
        state.chat_send_btn = None
        state.chat_status_label = None
        state.chat_token_label = None
        state.improve_btn = None
        state.paste_editor_btn = None
        state.clear_btn = None
        state.export_btn = None
        state.settings_btn = None
        state.new_chat_btn = None
        state.delete_chat_btn = None
        state.editor_source_text = None
        state.editor_comment_text = None
        state.editor_stats_label = None
        state.editor_status_label = None
        try:
            win.destroy()
        except Exception:
            pass

    win.protocol("WM_DELETE_WINDOW", on_close)
    try:
        state.chat_input.focus_set()
    except Exception:
        pass
    try:
        win.after(150, lambda: _apply_window_icon(win))
    except Exception:
        pass


def reapply_language():
    if not _widget_exists(state._chat_window):
        return
    try:
        win_ref = state._chat_window
        close_handler = win_ref.protocol("WM_DELETE_WINDOW")
        if close_handler:
            win_ref.tk.call(close_handler)
        else:
            win_ref.destroy()
    except Exception:
        try:
            state._chat_window.destroy()
        except Exception:
            pass
        state._chat_window = None
    try:
        open_chat_window()
    except Exception:
        pass


# Inter-module imports (keep at bottom to avoid circular)
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
from engine.gui.chat_window.chat_settings import open_gpt_settings
from engine.gui.chat_window.chat_editor import _show_editor_preview, _hide_editor_preview, open_editor_text_window, _get_selected_or_all_text, _show_editor_window

def main():
    root = tk.Tk()
    root.withdraw()
    init(root, {}, lambda *args, **kwargs: None, lambda: "", lambda x: None, "test")
    open_chat_window()
    root.mainloop()

if __name__ == "__main__":
    main()
