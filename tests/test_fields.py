"""动态背景与动态文字：出图、确定性、动效确实在变。"""
from PIL import Image

from studio import fields, theme as th, typefx


def test_field_render_size_and_mode():
    for kind in fields.FIELDS:
        img = fields.render(kind, 1.5)
        assert img.size == (th.W, th.H)
        assert img.mode == "RGB"


def test_field_is_deterministic():
    a = fields.render("noise", 2.0)
    b = fields.render("noise", 2.0)
    assert a.tobytes() == b.tobytes()


def test_field_changes_over_time():
    a = fields.render("dots", 0.0)
    b = fields.render("dots", 1.0)
    assert a.tobytes() != b.tobytes()


def test_unknown_field_raises():
    try:
        fields.render("no_such_field", 0.0)
    except ValueError:
        return
    raise AssertionError("应该抛 ValueError")


def test_typefx_draws_progressively():
    canvas = Image.new("RGB", (th.W, th.H), th.BG)
    from PIL import ImageDraw
    d = ImageDraw.Draw(canvas)
    fnt = th.font(90)
    lines = ["逐字出现测试"]
    typefx.draw("type", d, lines, fnt, 100, 400, 0.02, th.INK)
    early = canvas.tobytes()
    canvas2 = Image.new("RGB", (th.W, th.H), th.BG)
    typefx.draw("type", ImageDraw.Draw(canvas2), lines, fnt, 100, 400, 1.2, th.INK)
    assert early != canvas2.tobytes()


def test_all_fx_render_without_error():
    canvas = Image.new("RGB", (th.W, th.H), th.BG)
    from PIL import ImageDraw
    d = ImageDraw.Draw(canvas)
    for fx in typefx.FX:
        typefx.draw(fx, d, ["测试文字"], th.font(80), 80, 600, 0.8, th.INK)


def test_unknown_fx_raises():
    canvas = Image.new("RGB", (100, 100), th.BG)
    from PIL import ImageDraw
    try:
        typefx.draw("nope", ImageDraw.Draw(canvas), ["x"], th.font(20), 0, 0, 0.5, th.INK)
    except ValueError:
        return
    raise AssertionError("应该抛 ValueError")
