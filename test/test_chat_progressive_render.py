from engine.gui.chat_window import chat_messages


class FakeRoot:
    def __init__(self):
        self.callbacks = []
        self.cancelled = []

    def after(self, delay, callback):
        self.callbacks.append((delay, callback))
        return f"timer-{len(self.callbacks)}"

    def after_cancel(self, timer):
        self.cancelled.append(timer)

    def run_next(self):
        _delay, callback = self.callbacks.pop(0)
        callback()


class FakeFrame:
    def __init__(self, *args, **kwargs):
        pass

    def winfo_exists(self):
        return True

    def pack(self, *args, **kwargs):
        pass


class FakeButton(FakeFrame):
    def __init__(self, *args, command=None, **kwargs):
        super().__init__()
        self.command = command


def test_session_messages_render_in_cancellable_batches(monkeypatch):
    root = FakeRoot()
    messages = [{"content": str(i)} for i in range(15)]
    rendered = []
    monkeypatch.setattr(chat_messages.state, "_root", root)
    monkeypatch.setattr(chat_messages.state, "chat_messages_frame", FakeFrame())
    monkeypatch.setattr(chat_messages, "_hide_new_message_indicator", lambda: None)
    monkeypatch.setattr(chat_messages, "_clear_messages_ui", lambda: None)
    monkeypatch.setattr(chat_messages, "_get_current_session", lambda: {"messages": messages})
    monkeypatch.setattr(
        chat_messages,
        "_add_message_bubble",
        lambda message, smooth_scroll=False: rendered.append(message),
    )
    monkeypatch.setattr(chat_messages, "_update_wraplengths", lambda: None)
    monkeypatch.setattr(chat_messages, "_scroll_chat_to_bottom", lambda immediate=False: None)
    monkeypatch.setattr(chat_messages, "_update_token_counter", lambda: None)
    chat_messages._session_render_after_id = None

    chat_messages._render_current_session()
    assert len(rendered) == chat_messages._SESSION_RENDER_BATCH
    assert len(root.callbacks) == 1
    root.run_next()
    assert len(rendered) == chat_messages._SESSION_RENDER_BATCH * 2
    root.run_next()
    assert rendered == messages


def test_large_session_renders_only_latest_window(monkeypatch):
    root = FakeRoot()
    messages = [{"content": str(i)} for i in range(100)]
    session = {"id": "large", "messages": messages}
    rendered = []
    monkeypatch.setattr(chat_messages.state, "_root", root)
    monkeypatch.setattr(chat_messages.state, "chat_messages_frame", FakeFrame())
    monkeypatch.setattr(chat_messages, "TkFrame", FakeFrame)
    monkeypatch.setattr(chat_messages, "TkButton", FakeButton)
    monkeypatch.setattr(chat_messages, "_hide_new_message_indicator", lambda: None)
    monkeypatch.setattr(chat_messages, "_clear_messages_ui", lambda: None)
    monkeypatch.setattr(chat_messages, "_get_current_session", lambda: session)
    monkeypatch.setattr(
        chat_messages,
        "_add_message_bubble",
        lambda message, smooth_scroll=False: rendered.append(message),
    )
    monkeypatch.setattr(chat_messages, "_update_wraplengths", lambda: None)
    monkeypatch.setattr(chat_messages, "_scroll_chat_to_bottom", lambda immediate=False: None)
    monkeypatch.setattr(chat_messages, "_update_token_counter", lambda: None)
    chat_messages._session_visible_counts.pop("large", None)
    chat_messages._session_render_after_id = None

    chat_messages._render_current_session()
    while root.callbacks:
        root.run_next()

    assert rendered == messages[-chat_messages._SESSION_VISIBLE_WINDOW :]


def test_new_session_invalidates_pending_render(monkeypatch):
    root = FakeRoot()
    monkeypatch.setattr(chat_messages.state, "_root", root)
    monkeypatch.setattr(chat_messages.state, "chat_messages_frame", FakeFrame())
    monkeypatch.setattr(chat_messages, "_hide_new_message_indicator", lambda: None)
    monkeypatch.setattr(chat_messages, "_clear_messages_ui", lambda: None)
    monkeypatch.setattr(chat_messages, "_get_current_session", lambda: {"messages": []})
    monkeypatch.setattr(chat_messages, "_add_empty_state", lambda: None)
    monkeypatch.setattr(chat_messages, "_update_token_counter", lambda: None)
    chat_messages._session_render_after_id = "old-timer"

    chat_messages._render_current_session()
    assert "old-timer" in root.cancelled
