"""ffmpeg / ffprobe 定位与调用。

本机没有系统级 ffmpeg，优先用 imageio-ffmpeg 自带的静态二进制；
装了系统 ffmpeg 的话也可以直接改环境变量 DOUYIN_FFMPEG 指过去。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def ffmpeg() -> str:
    env = os.environ.get("DOUYIN_FFMPEG")
    if env and Path(env).exists():
        return env
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "找不到 ffmpeg。装一个（winget install Gyan.FFmpeg）"
            "或在环境变量 DOUYIN_FFMPEG 里指定路径。"
        ) from exc


def ffprobe() -> str | None:
    env = os.environ.get("DOUYIN_FFPROBE")
    if env and Path(env).exists():
        return env
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    # imageio-ffmpeg 只带 ffmpeg，没有 ffprobe
    guess = Path(ffmpeg()).with_name("ffprobe.exe")
    return str(guess) if guess.exists() else None


def run(args: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        args,
        check=False,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"命令失败（{proc.returncode}）：{' '.join(args)}\n{proc.stderr[-2000:]}"
        )
    return proc


def probe_duration(path: Path) -> float:
    """返回秒数；没有 ffprobe 时从 mp4 的 mvhd 里读时长，够用。"""
    pr = ffprobe()
    if pr:
        out = run([pr, "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=nw=1:nk=1", str(path)]).stdout.strip()
        try:
            return float(out)
        except ValueError:
            pass
    with open(path, "rb") as fh:
        data = fh.read(4096)
    idx = data.find(b"mvhd")
    if idx == -1:
        raise RuntimeError("无法读出时长")
    ver = data[idx + 4]
    if ver == 0:
        timescale = int.from_bytes(data[idx + 16:idx + 20], "big")
        duration = int.from_bytes(data[idx + 20:idx + 24], "big")
    else:
        timescale = int.from_bytes(data[idx + 24:idx + 28], "big")
        duration = int.from_bytes(data[idx + 28:idx + 36], "big")
    return duration / max(1, timescale)
