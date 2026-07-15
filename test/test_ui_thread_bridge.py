import threading

from engine.gui.ui_thread_bridge import UIThreadBridge


class FakeWidget:
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

    def run_next(self):
        token = next(iter(self.callbacks))
        _delay, callback = self.callbacks.pop(token)
        callback()


def test_worker_post_does_not_touch_widget():
    widget = FakeWidget()
    bridge = UIThreadBridge(widget)
    bridge.begin()
    scheduled_before = widget.counter

    thread = threading.Thread(target=lambda: bridge.post(lambda: None))
    thread.start()
    thread.join()

    assert widget.counter == scheduled_before
    assert bridge.snapshot()["queued"] == 1


def test_callbacks_execute_when_ui_poller_drains():
    widget = FakeWidget()
    bridge = UIThreadBridge(widget)
    values = []
    bridge.begin()
    bridge.post(values.append, 42)
    bridge.producer_done()
    widget.run_next()
    assert values == [42]
    assert bridge.snapshot()["polling"] is False


def test_multiple_producers_share_one_poller():
    widget = FakeWidget()
    bridge = UIThreadBridge(widget)
    bridge.begin()
    bridge.begin()
    assert len(widget.callbacks) == 1
    bridge.post(lambda: None)
    bridge.producer_done()
    widget.run_next()
    assert bridge.snapshot()["producers"] == 1
    assert bridge.snapshot()["polling"] is True
    bridge.producer_done()
    widget.run_next()
    assert bridge.snapshot()["polling"] is False


def test_destroy_cancels_and_discards():
    widget = FakeWidget()
    bridge = UIThreadBridge(widget)
    bridge.begin()
    bridge.post(lambda: None)
    timer = bridge._after_id
    bridge.destroy()
    assert timer in widget.cancelled
    assert bridge.snapshot() == {
        "producers": 0,
        "queued": 0,
        "polling": False,
        "destroyed": True,
    }
