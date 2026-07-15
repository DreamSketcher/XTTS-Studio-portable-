from engine.gui.rvc_model_dropdown import RVCModelDropdown


class FakeTrigger:
    def __init__(self):
        self.callbacks = []

    def after_idle(self, callback):
        self.callbacks.append(callback)
        return "idle-1"


def test_activate_row_patches_only_previous_and_current():
    dropdown = RVCModelDropdown.__new__(RVCModelDropdown)
    dropdown._active_row_key = ("local", "old")
    dropdown._active_row_widget = None
    dropdown._row_records = {}
    dropdown.trigger_btn = FakeTrigger()
    refreshed = []
    dropdown._refresh_row_record = refreshed.append
    dropdown._ensure_active_row_visible = lambda: None

    dropdown._activate_row(("local", "new"))

    assert dropdown._active_row_key == ("local", "new")
    assert refreshed == [("local", "old"), ("local", "new")]
    assert len(dropdown.trigger_btn.callbacks) == 1


def test_activate_same_row_does_no_work():
    dropdown = RVCModelDropdown.__new__(RVCModelDropdown)
    dropdown._active_row_key = ("local", "same")
    dropdown.trigger_btn = FakeTrigger()
    dropdown._refresh_row_record = lambda key: (_ for _ in ()).throw(AssertionError(key))

    dropdown._activate_row(("local", "same"))

    assert dropdown.trigger_btn.callbacks == []
