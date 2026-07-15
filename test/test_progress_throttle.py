from engine.gui.progress_throttle import ProgressThrottle


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_limits_regular_updates_to_configured_rate():
    clock = FakeClock()
    throttle = ProgressThrottle(max_hz=10, clock=clock)
    assert throttle.should_emit(1) is True
    clock.now = 0.05
    assert throttle.should_emit(2) is False
    clock.now = 0.1
    assert throttle.should_emit(3) is True


def test_boundary_values_are_always_delivered():
    clock = FakeClock()
    throttle = ProgressThrottle(max_hz=10, clock=clock)
    assert throttle.should_emit(25) is True
    assert throttle.should_emit(100) is True
    clock.now = 0.001
    assert throttle.should_emit(0) is True


def test_duplicates_are_coalesced():
    throttle = ProgressThrottle(max_hz=1000, clock=lambda: 10.0)
    assert throttle.should_emit(42) is True
    assert throttle.should_emit(42) is False
    assert throttle.should_emit(42, force=True) is True


def test_reset_allows_immediate_emit():
    clock = FakeClock()
    throttle = ProgressThrottle(max_hz=1, clock=clock)
    assert throttle.should_emit(10) is True
    assert throttle.should_emit(20) is False
    throttle.reset()
    assert throttle.should_emit(20) is True
