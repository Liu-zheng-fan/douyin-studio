"""封面：尺寸、两行上限、高亮胶囊。"""
from pathlib import Path

from PIL import Image

from studio import cover


def _script(**kw):
    base = {"title": "我不吃饭，但我卖装饭的盆", "cover_title": "我不吃饭\n但卖装饭的盆",
            "cover_kicker": "第 1 条", "handle": "@测试", "cover_pill": "39 块 9"}
    base.update(kw)
    return base


def test_cover_outputs_two_sizes(tmp_path):
    out = cover.build(_script(), tmp_path)
    a = Image.open(out["cover_3x4"])
    b = Image.open(out["cover_9x16"])
    assert a.size == (1080, 1440)
    assert b.size == (1080, 1920)


def test_cover_long_title_still_two_lines(tmp_path):
    """超长标题要缩字号，不能压到第三行或出界。"""
    out = cover.build(_script(cover_title="这是一句特别长的封面标题用来测试自动缩字号的能力"), tmp_path)
    assert Path(out["cover_3x4"]).exists()


def test_cover_without_pill_still_works(tmp_path):
    s = _script()
    s.pop("cover_pill")
    out = cover.build(s, tmp_path)
    assert Path(out["cover_3x4"]).exists()


def test_cover_pill_changes_output(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    cover.build(_script(), a)
    s = _script()
    s.pop("cover_pill")
    cover.build(s, b)
    assert (a / "cover_3x4.png").read_bytes() != (b / "cover_3x4.png").read_bytes()
