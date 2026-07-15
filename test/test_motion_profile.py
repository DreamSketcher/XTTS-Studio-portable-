import pytest

from engine.gui import motion_profile


@pytest.fixture(autouse=True)
def reset_profile(monkeypatch):
    monkeypatch.delenv("XTTS_UI_MOTION", raising=False)
    motion_profile._cached = None
    motion_profile._adaptive_degraded = False
    yield
    motion_profile._cached = None
    motion_profile._adaptive_degraded = False


def test_profiles_control_decorative_effects():
    motion_profile.set_motion_profile("ultra")
    assert motion_profile.decorative_effects_enabled() is True
    motion_profile.set_motion_profile("balanced")
    assert motion_profile.decorative_effects_enabled() is True
    for profile in ("performance", "reduced", "off"):
        motion_profile.set_motion_profile(profile)
        assert motion_profile.decorative_effects_enabled() is False


def test_balanced_and_performance_reduce_timer_frequency():
    motion_profile.set_motion_profile("ultra")
    ultra = motion_profile.adjusted_interval(40)
    motion_profile.set_motion_profile("balanced")
    balanced = motion_profile.adjusted_interval(40)
    motion_profile.set_motion_profile("performance")
    performance = motion_profile.adjusted_interval(40)
    assert ultra < balanced < performance


def test_balanced_adaptive_degradation_slows_without_disabling_effects():
    motion_profile.set_motion_profile("balanced")
    normal = motion_profile.adjusted_interval(40)
    motion_profile.set_adaptive_degraded(True)
    assert motion_profile.get_effective_motion_profile() == "adaptive"
    assert motion_profile.decorative_effects_enabled() is True
    assert motion_profile.adjusted_interval(40) > normal


def test_off_disables_transitions():
    motion_profile.set_motion_profile("off")
    assert motion_profile.transitions_enabled() is False
    assert motion_profile.adjusted_interval(40) == 2000


def test_invalid_profile_is_rejected():
    with pytest.raises(ValueError):
        motion_profile.set_motion_profile("cinematic")
