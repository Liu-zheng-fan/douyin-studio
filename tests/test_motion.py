"""动画内核：纯函数，测边界和单调性。"""
import math

import pytest

from studio import motion as mo


def test_clamp_bounds():
    assert mo.clamp(-1) == 0
    assert mo.clamp(2) == 1
    assert mo.clamp(0.5) == 0.5
    with pytest.raises(ValueError):
        mo.clamp(0.5, 1, 0)


def test_progress_and_lerp():
    assert mo.progress(5, 0, 10) == 0.5
    assert mo.progress(-1, 0, 10) == 0
    assert mo.progress(99, 0, 10) == 1
    assert mo.lerp(0, 10, 0.25) == 2.5
    with pytest.raises(ValueError):
        mo.progress(1, 5, 5)


@pytest.mark.parametrize("fn", [mo.ease_out_cubic, mo.ease_in_out_cubic,
                                mo.ease_out_expo, mo.ease_in_quad, mo.ease_out_quad])
def test_easing_monotonic_and_bounded(fn):
    prev = -1
    for i in range(51):
        v = fn(i / 50)
        assert 0 <= v <= 1
        assert v >= prev - 1e-9
        prev = v


def test_spring_starts_at_zero_and_settles():
    assert mo.spring(0) == 0
    assert abs(mo.spring(5, freq=2, damping=0.6) - 1) < 0.02


def test_spring_overshoots_with_low_damping():
    peak = max(mo.spring(t / 100, freq=2, damping=0.3) for t in range(200))
    assert peak > 1.0


def test_bezier_endpoints():
    f = mo.bezier(0.42, 0, 0.58, 1)
    assert f(0) == 0 and f(1) == 1
    assert 0 <= f(0.5) <= 1


def test_track_keyframes():
    keys = [(0, 0), (1, 100), (2, 50)]
    assert mo.track(-1, keys) == 0
    assert mo.track(1, keys) == 100
    assert mo.track(3, keys) == 50
    with pytest.raises(ValueError):
        mo.track(0, [])


def test_pulse_within_range():
    for t in range(0, 300):
        v = mo.pulse(t / 10, period=1.2)
        assert 0 <= v <= 1


def test_stagger_increases():
    assert mo.stagger(0) < mo.stagger(1) < mo.stagger(2)
