"""B-roll 素材库：索引、按关键词挑选、确定性抽样。"""
from pathlib import Path

from studio import broll


def test_index_builds(tmp_path):
    # 用假 mp4 建索引：不该崩，秒数为 None
    (tmp_path / "blur-slide.mp4").write_bytes(b"\x00" * 64)
    (tmp_path / "countdown-arc.mp4").write_bytes(b"\x00" * 64)
    items = broll.rebuild_index(tmp_path)
    assert {i["name"] for i in items} == {"blur-slide", "countdown-arc"}
    assert all("file" in i for i in items)


def test_pick_by_english_keyword(tmp_path):
    for n in ("blur-slide", "neon-glow", "typewriter-reveal"):
        (tmp_path / f"{n}.mp4").write_bytes(b"\x00" * 32)
    broll.rebuild_index(tmp_path)
    assert broll.pick("blur", tmp_path)
    assert broll.pick("type", tmp_path)[0]["name"] == "typewriter-reveal"


def test_pick_by_chinese_intent(tmp_path):
    for n in ("bottom-push-stack-wipe", "hit-counter"):
        (tmp_path / f"{n}.mp4").write_bytes(b"\x00" * 32)
    broll.rebuild_index(tmp_path)
    assert any("wipe" in h["name"] for h in broll.pick("转场", tmp_path))


def test_pick_empty_returns_nothing(tmp_path):
    broll.rebuild_index(tmp_path)
    assert broll.pick("转场", tmp_path) == []


def test_describe_shape(tmp_path):
    (tmp_path / "x.mp4").write_bytes(b"\x00" * 32)
    broll.rebuild_index(tmp_path)
    d = broll.describe(tmp_path)
    assert d["count"] == 1 and "intents" in d
