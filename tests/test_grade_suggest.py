"""调色与建议：小函数，测行为不测实现。"""
from PIL import Image

from ops import suggest as sg
from studio import theme as th


def test_grade_none_is_identity():
    img = Image.new("RGB", (20, 20), (100, 100, 100))
    assert th.grade(img, None).tobytes() == img.tobytes()


def test_grade_contrast_change():
    """纯色图对比度不变，要用有两极的画布才看得出差异。"""
    img = Image.new("RGB", (2, 2))
    img.putpixel((0, 0), (60, 60, 60))
    img.putpixel((1, 1), (200, 200, 200))
    out = th.grade(img, {"contrast": 1.6})
    assert out.getpixel((0, 0))[0] < 60
    assert out.getpixel((1, 1))[0] > 200


def test_grade_warmth_raises_red():
    img = Image.new("RGB", (10, 10), (100, 100, 100))
    r, g, b = th.grade(img, {"warmth": 0.2}).getpixel((0, 0))
    assert r > 100 and b < 100


def test_grade_lift_brightens():
    img = Image.new("RGB", (10, 10), (50, 50, 50))
    assert th.grade(img, {"lift": 20}).getpixel((0, 0))[0] > 50


def test_suggest_shape():
    r = sg.suggest()
    assert set(r) >= {"variable", "why", "how", "confidence"}
    assert r["confidence"] in ("low", "medium", "high")


def test_tag_mapping_covers_all_known_tags():
    for tag in ("topic", "script", "visual", "pace", "audio", "product"):
        assert tag in sg.TAG_TO_VARIABLE
        var, how = sg.TAG_TO_VARIABLE[tag]
        assert var and how
