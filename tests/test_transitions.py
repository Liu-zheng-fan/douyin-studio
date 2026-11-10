"""转场：端点、尺寸、差异性。"""
from PIL import Image

from studio import transitions as tr


def _img(color):
    return Image.new("RGB", (200, 400), color)


def test_endpoints_return_exact_frames():
    a, b = _img((0, 0, 0)), _img((255, 255, 255))
    assert tr.blend(a, b, 0.0, "crossfade").tobytes() == a.tobytes()
    assert tr.blend(a, b, 1.0, "crossfade").tobytes() == b.tobytes()


def test_all_kinds_keep_size():
    a, b = _img((10, 20, 30)), _img((200, 180, 160))
    for kind in tr.TRANSITIONS:
        out = tr.blend(a, b, 0.5, kind)
        assert out.size == (200, 400), kind
        assert out.mode == "RGB", kind


def test_midpoint_differs_from_both():
    a, b = _img((0, 0, 0)), _img((240, 240, 240))
    for kind in ("crossfade", "wipe", "push", "zoom"):
        mid = tr.blend(a, b, 0.5, kind)
        assert mid.tobytes() != a.tobytes(), kind
        assert mid.tobytes() != b.tobytes(), kind


def test_fade_goes_through_black():
    a, b = _img((255, 255, 255)), _img((255, 255, 255))
    mid = tr.blend(a, b, 0.5, "fade")
    r, g, bl = mid.getpixel((100, 200))
    assert r < 40 and g < 40 and bl < 40


def test_direction_changes_result():
    a, b = _img((0, 0, 0)), _img((255, 255, 255))
    left = tr.blend(a, b, 0.5, "wipe", "left")
    right = tr.blend(a, b, 0.5, "wipe", "right")
    assert left.tobytes() != right.tobytes()


def test_pick_defaults_and_clamp():
    assert tr.pick({}) == ("crossfade", "left", 0.28)
    kind, direction, dur = tr.pick({"transition": "wipe", "transition_dir": "up",
                                    "transition_dur": 5})
    assert (kind, direction) == ("wipe", "up")
    assert dur <= 0.8
    assert tr.pick({"transition": "bogus"})[0] == "crossfade"
