"""镜头库：每种镜头都要能出帧，且开场必须有变化。"""
import pytest
from PIL import Image

from studio import shots, theme as th

SPECS = {
    "hook": {"text": ["测试开场"], "sub": "副标题"},
    "number": {"label": "家底", "value": 4, "unit": "个粉丝", "note": "零条作品"},
    "split": {"a": "找个班上", "b": "自己挣口白饭", "tag": "标签"},
    "line": {"a": "我不会吃饭", "b": "得靠它吃饭"},
    "reveal": {"name": "不锈钢盆", "labels": ["便宜", "耐摔"]},
    "bullets": {"title": "三条", "items": ["一", "二", "三"]},
    "cta": {"text": ["看我第几天开张"], "sub": "关注一下", "user": "@测试"},
    "char": {"text": ["缺形象时退化成文字卡"], "caption_y": 0.26},
    "steps": {"title": "怎么用", "items": [
        {"title": "打开", "desc": "连上就行"},
        {"title": "点生成", "desc": "一分钟"},
        {"title": "改两句", "desc": "你只管把关"}]},
    "meter": {"value": 82, "max": 100, "label": "满意度", "verdict": "还不错"},
    "price": {"now": "39.9", "old": "59.9", "unit": "元", "note": "包邮 · 七天无理由"},
    "quote": {"text": "这个盆比我想的厚实，装汤也不烫手。", "who": "—— 一位买家"},
}


@pytest.mark.parametrize("kind,spec", SPECS.items())
def test_shot_renders_correct_size(kind, spec):
    bg = th.backdrop("dark")
    frame = shots.render(bg, {"type": kind, **spec}, t=1.0, dur=3.0, assets={})
    assert frame.mode == "RGB"
    assert frame.size == (th.W, th.H)


@pytest.mark.parametrize("kind", list(SPECS))
def test_shot_animates(kind):
    """同一镜头的第 0.1 秒和第 1.2 秒必须不同——否则就是一张静图。"""
    bg = th.backdrop("dark")
    spec = {"type": kind, **SPECS[kind]}
    a = shots.render(bg.copy(), spec, t=0.1, dur=3.0, assets={})
    b = shots.render(bg.copy(), spec, t=1.2, dur=3.0, assets={})
    assert a.tobytes() != b.tobytes()


def test_unknown_shot_raises():
    with pytest.raises(ValueError):
        shots.render(th.backdrop(), {"type": "no_such_shot"}, 0.5, 2.0, {})


def test_art_falls_back_without_image():
    """没有图也不该崩，退回占位画面。"""
    frame = shots.render(th.backdrop(), {"type": "art", "text": ["无图"]}, 0.5, 2.0, {})
    assert frame.size == (th.W, th.H)


def test_backdrop_variants():
    assert th.backdrop("flat").size == (th.W, th.H)
    assert th.backdrop("dark").size == (th.W, th.H)


def test_wrap_never_exceeds_width():
    fnt = th.font(60)
    for text in ["短", "这是一句比较长的中文文案用来测试断行是否正确处理",
                 "mixed 中英文 text with spaces and 汉字"]:
        for line in th.wrap(text, fnt, 800):
            assert fnt.getlength(line) <= 800 or len(line) <= 1
