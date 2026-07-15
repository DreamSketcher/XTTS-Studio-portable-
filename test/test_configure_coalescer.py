from types import SimpleNamespace

from engine.gui.configure_coalescer import ConfigureCoalescer


class FakeWidget:
    def __init__(self):
        self.callbacks = {}
        self.counter = 0
        self.cancelled = []

    def after_idle(self, callback):
        self.counter += 1
        token = f"idle-{self.counter}"
        self.callbacks[token] = callback
        return token

    def after_cancel(self, token):
        self.cancelled.append(token)
        self.callbacks.pop(token, None)

    def flush(self):
        token = next(iter(self.callbacks))
        self.callbacks.pop(token)()


def test_resize_storm_is_coalesced_to_latest_size():
    widget = FakeWidget()
    values = []
    coalescer = ConfigureCoalescer(widget, lambda w, h: values.append((w, h)))
    coalescer(SimpleNamespace(width=100, height=50))
    coalescer(SimpleNamespace(width=120, height=60))
    coalescer(SimpleNamespace(width=140, height=70))
    assert len(widget.callbacks) == 1
    widget.flush()
    assert values == [(140, 70)]


def test_subpixel_noise_below_threshold_is_ignored():
    widget = FakeWidget()
    values = []
    coalescer = ConfigureCoalescer(widget, lambda w, h: values.append((w, h)), threshold_px=4)
    coalescer(SimpleNamespace(width=100, height=50))
    widget.flush()
    coalescer(SimpleNamespace(width=102, height=52))
    assert widget.callbacks == {}
    assert values == [(100, 50)]


def test_cancel_removes_pending_callback():
    widget = FakeWidget()
    coalescer = ConfigureCoalescer(widget, lambda w, h: None)
    coalescer(SimpleNamespace(width=100, height=50))
    timer = coalescer._after_id
    coalescer.cancel()
    assert timer in widget.cancelled
    assert coalescer._pending_size is None
