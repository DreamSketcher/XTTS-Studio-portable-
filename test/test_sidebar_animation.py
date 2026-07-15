from engine.gui import layout
from engine.gui.animation_manager import AnimationManager


class FakePanel:
    def __init__(self):
        self.widths = []

    def configure(self, **kwargs):
        if "width" in kwargs:
            self.widths.append(kwargs["width"])


def test_sidebar_animation_reaches_exact_target(monkeypatch):
    panel = FakePanel()
    monkeypatch.setattr(layout, "left_panel", panel)
    layout._sidebar_visual_width = 260
    AnimationManager._instance = AnimationManager(root=None)
    completed = []

    layout._animate_left_panel_width(0, on_complete=lambda: completed.append(True))

    assert panel.widths[-1] == 0
    assert layout._sidebar_visual_width == 0
    assert completed == [True]
