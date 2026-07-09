from __future__ import annotations
import tkinter as tk
import engine.gui.chat_window.state as state
from engine.gui.chat_window.custom_widgets import CTK_AVAILABLE, CTkFrame, CTkLabel, CTkButton, TkFrame, TkLabel, TkButton, TkRawFrame
from i18n import t

try:
    from engine.gui.colors import Colors, scaled_font_size
except Exception:
    def scaled_font_size(x): return x
    Colors = None

def _add_message_bubble(message: dict, smooth_scroll: bool = True, force_scroll: bool = False):
    if not _widget_exists(state.chat_messages_frame):
        return

    role = message.get("role", "assistant")
    content = message.get("content", "")
    ts = message.get("ts", _now_ts())
    tokens = _approx_tokens(content)

    _destroy_empty_state_if_any()
    _was_near_bottom = _is_chat_near_bottom()

    if role == "system":
        _add_system_message(content, ts)
        if smooth_scroll and (_is_chat_near_bottom() or force_scroll):
            _scroll_chat_to_bottom(immediate=force_scroll)
        return

    is_user = role == "user"

    row = TkFrame(state.chat_messages_frame, bg=_c("BG_DARK"))
    row._is_message_row = True
    row.pack(fill="x", padx=14, pady=8)

    avatar_text = "🧑" if is_user else "🤖"
    avatar = TkLabel(
        row,
        text=avatar_text,
        bg=_c("BG_DARK"),
        fg=_c("TEXT_MAIN"),
        font=("Segoe UI Emoji", 22),
        width=2,
    )

    bubble_bg = _c("ACCENT") if is_user else _c("BG_CARD")
    bubble_fg = "#ffffff" if is_user else _c("TEXT_MAIN")
    bubble_hover = _lighten_color(bubble_bg, 0.10)

    # Unified rounded card for bubble (like audio/history cards)
    bubble = TkFrame(
        row,
        bg=bubble_bg,
    )
    # Use CTkFrame for rounded if available
    try:
        bubble_outer = CTkFrame(row, fg_color=bubble_bg, corner_radius=18,
                                border_width=1, border_color=_c("BORDER") if not is_user else bubble_bg)
        bubble_outer.pack_propagate(False)
        bubble = bubble_outer
        inner_bg = bubble_bg
    except Exception:
        bubble = tk.Frame(
            row,
            bg=bubble_bg,
            highlightthickness=1,
            highlightbackground=_c("BORDER") if not is_user else bubble_bg,
            padx=14,
            pady=10,
        )
        inner_bg = bubble_bg

    # inner content
    meta = tk.Frame(bubble, bg=inner_bg)
    meta.pack(fill="x", padx=14, pady=(10,4))

    author = t("chat_author_you") if is_user else _ai_display_name()
    meta_fg = "#dbeafe" if is_user else _c("TEXT_DIM")

    tk.Label(
        meta,
        text=t("chat_meta_format", author, ts, tokens),
        bg=inner_bg,
        fg=meta_fg,
        font=("Segoe UI", scaled_font_size(11)),
        anchor="w",
    ).pack(side="left")

    btn_box = tk.Frame(meta, bg=inner_bg)
    btn_box.pack(side="right")

    def _send_selected_or_full(lbl=None):
        if lbl is not None and _widget_exists(lbl):
            try:
                sel = lbl.get("sel.first", "sel.last").strip()
                if sel:
                    _send_to_main_editor(sel)
                    return
            except Exception:
                pass
        _send_to_main_editor(content)

    to_editor_btn = tk.Button(
        btn_box,
        text="→",
        command=lambda: _send_selected_or_full(text_label),
        bg=inner_bg,
        fg=meta_fg,
        activebackground=bubble_hover,
        activeforeground=_c("TEXT_MAIN"),
        relief="flat",
        bd=0,
        cursor="hand2",
        font=("Segoe UI", scaled_font_size(11), "bold"),
        width=3,
        padx=2,
        pady=0,
    )
    to_editor_btn.pack(side="right", padx=(4, 0))

    copy_btn = tk.Button(
        btn_box,
        text="",
        command=lambda t=content: _copy_to_clipboard(t),
        bg=inner_bg,
        fg=meta_fg,
        activebackground=bubble_hover,
        activeforeground=_c("TEXT_MAIN"),
        relief="flat",
        bd=0,
        cursor="hand2",
        font=("Segoe UI", scaled_font_size(11)),
        width=7,
        padx=2,
        pady=0,
    )
    copy_btn.pack(side="right")

    text_label = tk.Text(
        bubble,
        bg=inner_bg,
        fg=bubble_fg,
        font=("Segoe UI", scaled_font_size(13)),
        relief="flat",
        highlightthickness=0,
        bd=0,
        wrap="word",
        padx=14,
        pady=6,
        cursor="arrow",
        takefocus=0,
    )
    text_label.insert("1.0", content)
    text_label.bind("<Key>", lambda e: "break")
    text_label.bind("<<Paste>>", lambda e: "break")
    text_label.bind("<<Cut>>", lambda e: "break")
    text_label.bind("<Button-2>", lambda e: "break")
    text_label.bind("<Button-1>", lambda e: _on_bubble_text_click(e))
    text_label.bind("<B1-Motion>", lambda e: "ignore_disabled_drag" or None)
    text_label.pack(fill="x", padx=2, pady=(0,10))
    text_label._bubble_content = content
    text_label._bubble_bg = inner_bg
    state._message_labels.append(text_label)

    def _send_selected_or_full2():
        try:
            ranges = text_label.tag_ranges("sel")
            if ranges:
                sel = text_label.get(ranges[0], ranges[1]).strip()
                if sel:
                    _send_to_main_editor(sel)
                    return
        except Exception:
            pass
        _send_to_main_editor(content)

    to_editor_btn.config(command=_send_selected_or_full2)
    _resize_bubble_text(text_label)

    text_label.bind("<Button-3>", lambda e, c=content: _show_bubble_context_menu(e, c, text_label))
    bubble.bind("<Button-3>", lambda e, c=content: _show_bubble_context_menu(e, c, text_label))

    spacer_left = tk.Frame(row, bg=_c("BG_DARK"))
    spacer_right = tk.Frame(row, bg=_c("BG_DARK"))

    if is_user:
        spacer_left.pack(side="left", fill="x", expand=True)
        bubble.pack(side="left", padx=(60, 12), anchor="e", fill="x", expand=False)
        avatar.pack(side="left", anchor="n", pady=(2,0))
    else:
        avatar.pack(side="left", anchor="n", pady=(2,0))
        bubble.pack(side="left", padx=(12, 60), anchor="w", fill="x", expand=False)
        spacer_right.pack(side="left", fill="x", expand=True)

    def _select_this_bubble(_event=None):
        _select_bubble(bubble, content, inner_bg)

    for w in (row, bubble, meta):
        try:
            w.bind("<Button-1>", _select_this_bubble)
        except Exception:
            pass

    def on_enter(_event=None):
        if bubble is _selected_bubble_frame_get():
            return
        try:
            bubble.config(bg=bubble_hover)
            meta.config(bg=bubble_hover)
            text_label.config(bg=bubble_hover)
            copy_btn.config(text="Copy", bg=bubble_hover)
            for child in meta.winfo_children():
                try:
                    child.config(bg=bubble_hover)
                except Exception:
                    pass
        except Exception:
            pass

    def on_leave(_event=None):
        if bubble is _selected_bubble_frame_get():
            return
        try:
            bubble.config(bg=inner_bg)
            meta.config(bg=inner_bg)
            text_label.config(bg=inner_bg)
            copy_btn.config(text="", bg=inner_bg)
            to_editor_btn.config(bg=inner_bg)
            for child in meta.winfo_children():
                try:
                    child.config(bg=inner_bg)
                except Exception:
                    pass
        except Exception:
            pass

    bubble._on_select_colors = (inner_bg, bubble_hover, meta, text_label, copy_btn, to_editor_btn)

    for w in (row, bubble, meta, text_label, avatar):
        try:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
        except Exception:
            pass

    _safe_after(50, lambda: _resize_bubble_text(text_label) if _widget_exists(text_label) else None)

    def _check_and_scroll():
        if not _widget_exists(state.chat_canvas):
            return
        if _was_near_bottom:
            _scroll_chat_to_bottom(immediate=False)
            _hide_new_message_indicator()
        elif role == "assistant" and smooth_scroll:
            _show_new_message_indicator()

    _safe_after(150, _check_and_scroll)


def _add_system_message(content: str, ts: str):
    row = tk.Frame(state.chat_messages_frame, bg=_c("BG_DARK"))
    row._is_message_row = True
    row.pack(fill="x", padx=18, pady=10)

    card = CTkFrame(row, fg_color=_c("BG_CARD"), corner_radius=14,
                    border_width=1, border_color=_c("BORDER"))
    card.pack(anchor="center", padx=12, pady=4)

    label = TkLabel(
        card,
        text=f"{ts} · {content}",
        bg=_c("BG_CARD"),
        fg=_c("TEXT_DIM"),
        font=("Segoe UI", scaled_font_size(11), "italic"),
        wraplength=560,
        justify="center",
        padx=16,
        pady=10,
    )
    label.pack()
    state._message_labels.append(label)


def _resize_bubble_text(text_widget):
    if not _widget_exists(text_widget):
        return
    try:
        text_widget.update_idletasks()
        n = int(text_widget.tk.call(text_widget._w, "count", "-displaylines", "1.0", "end"))
        text_widget.config(height=max(1, n))
    except Exception:
        try:
            content = text_widget.get("1.0", "end-1c")
            text_widget.config(height=max(1, content.count("\n") + 1))
        except Exception:
            pass


def content_lines_estimate(text_widget) -> int:
    try:
        content = text_widget.get("1.0", "end-1c")
        return max(1, content.count("\n") + 1)
    except Exception:
        return 1


def _lighten_color(hex_color: str, factor: float = 0.1) -> str:
    try:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return hex_color
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def _selected_bubble_frame_get():
    return state._selected_bubble_frame


def _select_bubble(bubble_frame, content: str, base_bg: str):
    if _widget_exists(state._selected_bubble_frame) and state._selected_bubble_frame is not bubble_frame:
        try:
            prev_bg, _hover, prev_meta, prev_text, prev_copy, prev_to_editor = state._selected_bubble_frame._on_select_colors
            state._selected_bubble_frame.config(fg_color=prev_bg if hasattr(state._selected_bubble_frame, 'configure') else prev_bg, bg=prev_bg)
            prev_meta.config(bg=prev_bg)
            prev_text.config(bg=prev_bg)
            prev_copy.config(bg=prev_bg)
            prev_to_editor.config(bg=prev_bg)
            for child in prev_meta.winfo_children():
                try:
                    child.config(bg=prev_bg)
                except Exception:
                    pass
        except Exception:
            pass

    if state._selected_bubble_frame is bubble_frame:
        try:
            _, _hover, meta, text_w, copy_b, to_editor_b = bubble_frame._on_select_colors
            meta.config(bg=base_bg)
            text_w.config(bg=base_bg)
            copy_b.config(bg=base_bg)
            to_editor_b.config(bg=base_bg)
        except Exception:
            pass
        state._selected_bubble_frame = None
        state._selected_bubble_content = ""
        set_chat_status(t("chat_selection_cleared"))
        return

    try:
        bubble_frame.configure(border_color=_c("ACCENT"), border_width=2)
    except Exception:
        try:
            bubble_frame.config(highlightbackground=_c("ACCENT"), highlightthickness=2)
        except Exception:
            pass

    state._selected_bubble_frame = bubble_frame
    state._selected_bubble_content = content
    set_chat_status(t("chat_msg_selected"))


def _on_bubble_text_click(event):
    return None


def _show_bubble_context_menu(event, content: str, text_widget=None):
    if not _widget_exists(state._chat_window):
        return

    def _get_sel_or_full():
        if text_widget is not None and _widget_exists(text_widget):
            try:
                ranges = text_widget.tag_ranges("sel")
                if ranges:
                    sel = text_widget.get(ranges[0], ranges[1]).strip()
                    if sel:
                        return sel
            except Exception:
                pass
        return content

    menu = tk.Menu(
        state._chat_window, tearoff=0,
        bg=_c("BG_CARD"), fg=_c("TEXT_MAIN"),
        activebackground=_c("BG_HOVER") if hasattr(state._colors, "BG_HOVER") else _c("BORDER"),
        activeforeground=_c("TEXT_MAIN"),
        relief="flat", borderwidth=1,
        font=("Segoe UI", 11),
    )
    menu.add_command(label=t("chat_ctx_copy"), command=lambda: _copy_to_clipboard(_get_sel_or_full()))
    menu.add_separator()
    menu.add_command(label=t("chat_ctx_to_editor"), command=lambda: _send_to_main_editor(_get_sel_or_full()))
    menu.add_command(label=t("chat_ctx_to_input"), command=lambda: _insert_prompt_into_chat_input(_get_sel_or_full()))
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def _update_wraplengths(event=None):
    if not _widget_exists(state.chat_canvas):
        return
    try:
        width = state.chat_canvas.winfo_width()
        if width < 50:
            return
        wrap_px = max(300, min(760, int(width * 0.66)))
        char_width = max(32, wrap_px // 7)
        for widget in list(state._message_labels):
            if not _widget_exists(widget):
                continue
            try:
                if isinstance(widget, tk.Text):
                    widget.config(width=char_width)
                else:
                    widget.config(wraplength=wrap_px)
            except Exception:
                pass
        try:
            state.chat_canvas.update_idletasks()
            state.chat_canvas.configure(scrollregion=state.chat_canvas.bbox("all"))
        except Exception:
            pass
    except Exception:
        pass


def _render_current_session():
    _hide_new_message_indicator()
    _clear_messages_ui()
    session = _get_current_session()
    messages = session.get("messages", [])
    if not messages:
        _add_empty_state()
    else:
        for m in messages:
            _add_message_bubble(m, smooth_scroll=False)
    _safe_after(0, _update_wraplengths)
    _safe_after(150, _update_wraplengths)
    _scroll_chat_to_bottom(immediate=True)
    _safe_after(200, lambda: _scroll_chat_to_bottom(immediate=True))
    _update_token_counter()


def _add_empty_state():
    if not _widget_exists(state.chat_messages_frame):
        return
    box = TkFrame(state.chat_messages_frame, bg=_c("BG_DARK"))
    box._is_empty_state = True
    box.pack(fill="both", expand=True, padx=24, pady=60)

    card = CTkFrame(box, fg_color=_c("BG_CARD"), corner_radius=20,
                    border_width=1, border_color=_c("BORDER"))
    card.pack(pady=10, padx=20)

    inner = TkFrame(card, bg=_c("BG_CARD"))
    inner.pack(padx=24, pady=24)

    TkLabel(inner, text="💬", bg=_c("BG_CARD"), fg=_c("TEXT_DIM"),
            font=("Segoe UI Emoji", 48)).pack(pady=(0, 12))
    TkLabel(inner, text=t("chat_new_chat_title"), bg=_c("BG_CARD"),
            fg=_c("TEXT_MAIN"), font=("Segoe UI", 18, "bold")).pack()
    TkLabel(inner, text=t("chat_welcome"), bg=_c("BG_CARD"),
            fg=_c("TEXT_DIM"), font=("Segoe UI", 13),
            wraplength=440, justify="center").pack(pady=(10, 0))


def _destroy_empty_state_if_any():
    if not _widget_exists(state.chat_messages_frame):
        return
    for child in state.chat_messages_frame.winfo_children():
        try:
            if getattr(child, "_is_empty_state", False):
                child.destroy()
        except Exception:
            pass


def _clear_messages_ui():
    state._message_labels = []
    state._typing_frame = None
    state._typing_label = None
    state._selected_bubble_frame = None
    state._selected_bubble_content = ""
    if not _widget_exists(state.chat_messages_frame):
        return
    for child in state.chat_messages_frame.winfo_children():
        try:
            child.destroy()
        except Exception:
            pass


from engine.gui.chat_window.engine.utils import _now_ts, _now_full, _approx_tokens, _ai_display_name, _build_editor_compose_prompt
from engine.gui.chat_window.engine.sessions import _load_sessions, _save_sessions, _enforce_limits, _create_session_dict, _get_current_session, _update_session_title_if_needed, _messages_for_api
from engine.gui.chat_window.engine.generation import _run_generation
from engine.gui.chat_window.ui_utils import _c, _safe_after, _widget_exists, _set_dark_titlebar, _get_app_parent, _show_window, _call_and_break, _ask_simple_text, _make_button, _set_button_text, _set_button_state, _is_descendant, _get_widget_text, _select_all_widget, _paste_clipboard_into_widget, _copy_to_clipboard
from engine.gui.chat_window.hotkeys import _event_has_ctrl, _event_has_shift, _match_hotkey, _on_ctrl_keypress, _handle_text_ctrl, _handle_window_ctrl, _bind_window_hotkeys, _bind_text_hotkeys
from engine.gui.chat_window.placeholders import _create_placeholder_overlay, _sync_text_placeholder, _refresh_placeholder_state, _update_input_placeholder_text
from engine.gui.chat_window.chat_scroll import _is_chat_near_bottom, _scroll_chat_to_bottom, _show_new_message_indicator, _hide_new_message_indicator, _scroll_to_new_message, _chat_mousewheel
from engine.gui.chat_window.chat_history import _refresh_session_list, _on_session_select, new_chat, delete_current_chat, clear_chat_history
from engine.gui.chat_window.chat_input import _focus_chat_input, _reset_editor_mode, _input_has_placeholder, _set_input_placeholder, _clear_input_placeholder, _get_input_text, _clear_input_text, _resize_input, _update_token_counter, _paste_into_input, _on_input_focus_in, _on_input_focus_out, _on_input_key_release, _on_enter, _submit_prompt, send_chat_message, _insert_prompt_into_chat_input
from engine.gui.chat_window.chat_typing import _show_typing, _animate_typing, _hide_typing
from engine.gui.chat_window.chat_actions import _send_to_main_editor, _stop_generation, _set_generation_ui, improve_text_with_gpt, paste_from_editor, set_chat_status, append_chat_message
from engine.gui.chat_window.chat_export import export_current_chat
from engine.gui.chat_window.chat_search import open_search
from engine.gui.chat_window.chat_settings import open_gpt_settings
from engine.gui.chat_window.chat_editor import _show_editor_preview, _hide_editor_preview, open_editor_text_window, _get_selected_or_all_text, _show_editor_window
from engine.gui.chat_window import init, open_chat_window
