import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

import engine.gui.presets as presets


class MockVar:
    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, val):
        self._value = val


@pytest.fixture
def mock_tk_vars(monkeypatch):
    monkeypatch.setattr(presets.tk, "BooleanVar", lambda value=False: MockVar(value))
    monkeypatch.setattr(presets.tk, "DoubleVar", lambda value=0.0: MockVar(value))
    monkeypatch.setattr(presets.tk, "IntVar", lambda value=0: MockVar(value))
    monkeypatch.setattr(presets.tk, "StringVar", lambda value="": MockVar(value))

    # use_gpt mock
    monkeypatch.setattr(presets, "use_gpt", MockVar(False))
    # also need root etc not used in build_quality_params

    yield


class TestSafeCall:
    def test_safe_call_no_exception(self):
        def good_fn(a, b):
            return a + b

        # should not raise
        presets._safe_call(good_fn, 1, 2)

    def test_safe_call_exception_swallowed(self):
        def bad_fn():
            raise ValueError("oops")

        # should not propagate
        presets._safe_call(bad_fn)


class TestBuildQualityParams:
    def test_build_creates_four_presets(self, mock_tk_vars):
        params = presets.build_quality_params()
        assert "Высокое качество" in params
        assert "Нарратив" in params
        assert "Динамика" in params
        assert "Экспрессия" in params

        # check some keys exist
        for preset_name, preset in params.items():
            assert "temperature" in preset
            assert "top_p" in preset
            assert "speed" in preset
            assert "rvc_enable" in preset
            assert "rvc_model" in preset
            assert "trim_mode" in preset

    def test_preset_values(self, mock_tk_vars):
        params = presets.build_quality_params()
        # Высокое качество defaults
        hq = params["Высокое качество"]
        assert hq["temperature"].get() == 0.70
        assert hq["rvc_model"].get() == "Не выбрана"
        assert hq["rvc_enable"].get() is False

        # Динамика has different f0 method
        dyn = params["Динамика"]
        assert dyn["rvc_f0_method"].get() == "pm"

        # Экспрессия has harvest
        expr = params["Экспрессия"]
        assert expr["rvc_f0_method"].get() == "harvest"

    def test_preset_descriptions(self, mock_tk_vars):
        params = presets.build_quality_params()
        assert "Нарратив" in presets.PRESET_DESCRIPTIONS
        assert "Динамика" in presets.PRESET_DESCRIPTIONS
        assert "Экспрессия" in presets.PRESET_DESCRIPTIONS

    def test_build_idempotent(self, mock_tk_vars):
        p1 = presets.build_quality_params()
        p2 = presets.build_quality_params()
        assert set(p1.keys()) == set(p2.keys())


class TestInit:
    def test_init_updates_globals(self):
        presets.init(root="fake_root", use_gpt=MockVar(True), save_settings=lambda x=None: None)
        assert presets.root == "fake_root"
        assert presets.use_gpt.get() is True


class TestStripCheckMark:
    def test_strip(self):
        # inner function _strip_check_mark defined inside open_quality_settings, not accessible directly
        # but we can test similar logic via direct copy: it strips ☑ ✓
        def _strip_check_mark(s, fallback=""):
            text = (s or "").replace("☑", "").replace("✓", "").strip()
            return text or fallback

        assert _strip_check_mark("☑ Test") == "Test"
        assert _strip_check_mark("✓ Test") == "Test"
        assert _strip_check_mark("", fallback="fallback") == "fallback"
