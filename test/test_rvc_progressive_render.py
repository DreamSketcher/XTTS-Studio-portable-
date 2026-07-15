from engine.gui.rvc_model_dropdown import RVCModelDropdown


class FakeTrigger:
    def __init__(self):
        self.callbacks = []
        self.counter = 0

    def after(self, delay, callback):
        self.counter += 1
        self.callbacks.append((delay, callback))
        return f"timer-{self.counter}"

    def run_next(self):
        _delay, callback = self.callbacks.pop(0)
        callback()


class FakeRow:
    pass


def _dropdown():
    dropdown = RVCModelDropdown.__new__(RVCModelDropdown)
    dropdown.trigger_btn = FakeTrigger()
    dropdown._render_token = 1
    dropdown._batch_after_id = None
    dropdown._rows_container = object()
    dropdown._render_metrics = {
        "renders": 1,
        "last_initial_ms": 0.0,
        "last_total_ms": 0.0,
        "last_rows": 0,
        "batched_rows": 0,
    }
    dropdown.rendered = []
    dropdown._render_remote_row = lambda entry: dropdown.rendered.append(entry) or FakeRow()
    dropdown._bind_wheel_tree = lambda row: None
    dropdown._refresh_list_scroll = lambda: None
    return dropdown


def test_large_result_is_rendered_in_eight_row_batches():
    dropdown = _dropdown()
    entries = list(range(20))
    dropdown._schedule_remote_batches(entries, 0, 1, 0.0)
    assert dropdown.rendered == []
    assert dropdown.trigger_btn.callbacks[0][0] == 8

    dropdown.trigger_btn.run_next()
    assert dropdown.rendered == list(range(8))
    dropdown.trigger_btn.run_next()
    assert dropdown.rendered == list(range(16))
    dropdown.trigger_btn.run_next()
    assert dropdown.rendered == entries
    assert dropdown._render_metrics["batched_rows"] == 20


def test_stale_render_token_cancels_batch_without_widgets():
    dropdown = _dropdown()
    dropdown._schedule_remote_batches(list(range(20)), 0, 999, 0.0)
    assert dropdown.trigger_btn.callbacks == []
    assert dropdown.rendered == []


def test_snapshot_returns_copy():
    dropdown = _dropdown()
    snapshot = dropdown.render_performance_snapshot()
    snapshot["renders"] = 100
    assert dropdown._render_metrics["renders"] == 1
