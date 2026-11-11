"""形象库：命名约定、匹配规则、合成效果。"""
from PIL import Image, ImageDraw

from studio import character as ch
from studio import shots, theme as th


def _make_png(path, color=(90, 140, 200, 255), size=(400, 600)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, size[0] - 40, size[1] - 40], fill=color)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def test_actions_indexes_by_filename(tmp_path):
    _make_png(tmp_path / "端盆.png")
    _make_png(tmp_path / "挥手.png")
    got = ch.actions(tmp_path)
    assert set(got) == {"端盆", "挥手"}


def test_pick_exact_and_partial(tmp_path):
    _make_png(tmp_path / "端盆.png")
    _make_png(tmp_path / "挥手.png")
    assert ch.pick("端盆", tmp_path).name == "端盆.png"
    # 互相包含
    assert ch.pick("端着盆", tmp_path).name == "端盆.png"


def test_pick_miss_returns_none(tmp_path):
    _make_png(tmp_path / "端盆.png")
    assert ch.pick("飞天", tmp_path) is None


def test_pick_empty_dir(tmp_path):
    assert ch.pick("端盆", tmp_path / "nope") is None


def test_describe_reports_count(tmp_path):
    _make_png(tmp_path / "a.png")
    info = ch.describe(tmp_path)
    assert info["count"] == 1 and info["exists"] is True


def test_place_keeps_size_and_paints_pixels(tmp_path):
    p = tmp_path / "端盆.png"
    _make_png(p, (255, 0, 0, 255))
    frame = th.backdrop("flat")
    out = ch.place(frame, p, t=0.5)
    assert out.size == frame.size
    # 底部中心应该被角色覆盖
    r, g, b = out.getpixel((frame.width // 2, frame.height - 200))
    assert r > 100 and g < 120


def test_char_shot_renders(tmp_path):
    p = tmp_path / "端盆.png"
    _make_png(p)
    spec = {"type": "char", "_char_path": str(p), "text": ["小鲸鱼"], "caption_y": 0.26}
    out = shots.render(th.backdrop("flat"), spec, 1.0, 3.0, {})
    assert out.size == (th.W, th.H)


def test_char_shot_falls_back_without_image():
    spec = {"type": "char", "action": "不存在的动作", "text": ["缺形象"]}
    out = shots.render(th.backdrop("flat"), spec, 1.0, 3.0, {})
    assert out.size == (th.W, th.H)
