from unittest.mock import MagicMock

from engine.gui import statusbar
from engine.gui.chat_window import chat_input


class FakeRoot:
    def __init__(self):
        self.callbacks = {}
        self.cancelled = []
        self.counter = 0

    def after(self, delay, callback):
        self.counter += 1
        token = f"after-{self.counter}"
        self.callbacks[token] = (delay, callback)
        return token

    def after_cancel(self, token):
        self.cancelled.append(token)
        self.callbacks.pop(token, None)


class FakeVar:
    def __init__(self):
        self.values = []

    def set(self, value):
        self.values.append(value)


def test_statusbar_deduplicates_identical_text_and_stage():
    root = FakeRoot()
    status = FakeVar()
    stage = FakeVar()
    statusbar.init(root=root, status_var=status, stage_var=stage, progress_value=FakeVar())
    statusbar.set_status("running")
    statusbar.set_status("running")
    statusbar.set_stage("RUNNING")
    statusbar.set_stage("RUNNING")
    assert len(root.callbacks) == 2


def test_statusbar_throttles_progress_bursts():
    root = FakeRoot()
    statusbar.init(
        root=root,
        status_var=FakeVar(),
        stage_var=FakeVar(),
        progress_value=FakeVar(),
        progress_bar=None,
    )
    statusbar.set_progress(10)
    statusbar.set_progress(11)
    statusbar.set_progress(12)
    assert len(root.callbacks) == 1
    statusbar.set_progress(100)
    assert len(root.callbacks) == 2


def test_chat_token_history_is_cached(monkeypatch):
    label = MagicMock()
    monkeypatch.setattr(chat_input.state, "chat_token_label", label)
    monkeypatch.setattr(chat_input, "_widget_exists", lambda widget: True)
    monkeypatch.setattr(chat_input, "_get_input_text", lambda: "input")
    messages = [{"content": "a" * 1000}, {"content": "b" * 1000}]
    session = {"messages": messages}
    monkeypatch.setattr(chat_input, "_get_current_session", lambda: session)
    approx = MagicMock(side_effect=lambda text: len(text) // 4)
    monkeypatch.setattr(chat_input, "_approx_tokens", approx)
    monkeypatch.setattr(chat_input, "t", lambda *args: str(args))
    chat_input._chat_token_cache["key"] = None

    chat_input._update_token_counter()
    first_calls = approx.call_count
    chat_input._update_token_counter()

    # Second refresh only counts current input; history is served from cache.
    assert approx.call_count == first_calls + 1


def test_chat_input_refresh_is_debounced(monkeypatch):
    root = FakeRoot()
    monkeypatch.setattr(chat_input.state, "_root", root)
    resize = MagicMock()
    tokens = MagicMock()
    placeholder = MagicMock()
    monkeypatch.setattr(chat_input, "_resize_input", resize)
    monkeypatch.setattr(chat_input, "_update_token_counter", tokens)
    monkeypatch.setattr(chat_input, "_sync_text_placeholder", placeholder)
    chat_input._input_refresh_after_id = None

    chat_input._on_input_key_release()
    first = chat_input._input_refresh_after_id
    chat_input._on_input_key_release()

    assert first in root.cancelled
    assert len(root.callbacks) == 1
    _delay, callback = next(iter(root.callbacks.values()))
    callback()
    resize.assert_called_once()
    tokens.assert_called_once()
    placeholder.assert_called_once()
