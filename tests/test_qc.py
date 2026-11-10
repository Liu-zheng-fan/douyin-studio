"""机器质检：用一个故意做坏的视频，确认它能拦住。"""
import subprocess
from pathlib import Path

import pytest

from studio import ff, qc


@pytest.fixture(scope="module")
def bad_video(tmp_path_factory) -> Path:
    """720x1280 + 3 秒：尺寸错、时长过短，应该被 block。"""
    out = tmp_path_factory.mktemp("qc") / "bad.mp4"
    subprocess.run(
        [ff.ffmpeg(), "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=black:s=720x1280:d=3",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out)],
        check=True,
    )
    return out


def test_bad_video_blocked(bad_video):
    r = qc.inspect(bad_video)
    assert r["ok"] is False
    codes = {i["code"] for i in r["issues"]}
    assert "size" in codes
    assert "too_short" in codes
    assert r["verdict"] == "blocked"


def test_black_frames_detected(bad_video):
    r = qc.inspect(bad_video)
    assert r["metrics"]["black_ratio"] > 0.5


def test_missing_file_is_blocked(tmp_path):
    r = qc.inspect(tmp_path / "nope.mp4")
    assert r["ok"] is False
    assert r["issues"][0]["code"] == "missing"


def test_probe_reads_metadata(bad_video):
    r = qc.inspect(bad_video)
    assert r["meta"]["width"] == 720
    assert r["meta"]["height"] == 1280
    assert r["meta"]["has_audio"] is True
    assert 2.5 < r["meta"]["duration"] < 3.5
