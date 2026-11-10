"""机器质检：成片进审批队列前的最后一道闸。

为什么必须有：机器出的片子最常见的死法不是「难看」，而是
「第一帧是黑的」「音轨没声」「字幕出框」「时长失控」——
这些肉眼扫一眼可能漏，但机器一秒钟能拦下来。

判定分三级：
    block  不能进审批，直接回炉
    warn   可以进审批，但要在审批页标出来
    info   只记录
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from . import ff

# 抖音竖屏的合理区间
MIN_SECONDS = 10
MAX_SECONDS = 60
TARGET_LUFS = (-17.0, -12.0)     # 太小声听不见，太大声会被压
TARGET_PEAK = -1.0               # dBTP 上限
EXPECTED_SIZE = (1080, 1920)


def _probe(video: Path) -> dict:
    """解析 ffmpeg -i 的输出（本机没有 ffprobe 时的通用做法）。"""
    proc = subprocess.run([ff.ffmpeg(), "-hide_banner", "-i", str(video)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = proc.stderr
    out = {"duration": None, "width": None, "height": None, "fps": None, "has_audio": False}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", text)
    if m:
        h, mi, s = m.groups()
        out["duration"] = int(h) * 3600 + int(mi) * 60 + float(s)
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", text)
    if m:
        out["width"], out["height"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?)\s*fps", text)
    if m:
        out["fps"] = float(m.group(1))
    out["has_audio"] = bool(re.search(r"Audio:", text))
    return out


def _black_ratio(video: Path, duration: float) -> float:
    """blackdetect 给出黑段落，累加时长占比。"""
    proc = subprocess.run(
        [ff.ffmpeg(), "-hide_banner", "-nostats", "-i", str(video),
         "-vf", "blackdetect=d=0.08:pix_th=0.10", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    total = 0.0
    for m in re.finditer(r"black_duration:\s*([\d.]+)", proc.stderr):
        total += float(m.group(1))
    return total / duration if duration else 0.0


def _grab(video: Path, t: float, out: Path) -> Image.Image | None:
    proc = subprocess.run(
        [ff.ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(video),
         "-frames:v", "1", str(out)], capture_output=True, text=True)
    if not out.exists():
        return None
    return Image.open(out).convert("L")


def _frame_motion(video: Path, tmp: Path) -> float:
    """首 0.4 秒的画面变化量。0 附近说明开场是死帧。"""
    a = _grab(video, 0.0, tmp / "f0.png")
    b = _grab(video, 0.4, tmp / "f1.png")
    if a is None or b is None:
        return 0.0
    diff = ImageChops.difference(a, b)
    return float(ImageStat.Stat(diff).mean[0])


def _loudness(video: Path) -> tuple[float | None, float | None]:
    proc = subprocess.run(
        [ff.ffmpeg(), "-hide_banner", "-nostats", "-i", str(video),
         "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    i = re.search(r"I:\s+(-?[\d.]+)\s*LUFS", proc.stderr)
    peak = re.search(r"Peak:\s+(-?[\d.]+)\s*dBFS", proc.stderr)
    return (float(i.group(1)) if i else None,
            float(peak.group(1)) if peak else None)


def inspect(video: Path, subtitle_chars: int | None = None) -> dict:
    issues: list[dict] = []

    def add(level: str, code: str, message: str):
        issues.append({"level": level, "code": code, "message": message})

    if not video.exists():
        return {"ok": False, "issues": [{"level": "block", "code": "missing", "message": "成片不存在"}]}

    meta = _probe(video)
    dur = meta["duration"] or 0.0

    if meta["width"] and (meta["width"], meta["height"]) != EXPECTED_SIZE:
        add("block", "size", f"分辨率 {meta['width']}x{meta['height']}，应为 1080x1920")
    if not meta["has_audio"]:
        add("block", "no_audio", "没有音轨")

    if dur < MIN_SECONDS:
        add("block", "too_short", f"时长 {dur:.1f}s < {MIN_SECONDS}s")
    elif dur > MAX_SECONDS:
        add("block", "too_long", f"时长 {dur:.1f}s > {MAX_SECONDS}s，完播率会崩")

    if dur:
        ratio = _black_ratio(video, dur)
        if ratio > 0.25:
            add("block", "black_frames", f"黑帧占比 {ratio:.0%}，画面像没加载出来")
        elif ratio > 0.10:
            add("warn", "black_frames", f"黑帧占比 {ratio:.0%} 偏高")

    with tempfile.TemporaryDirectory() as td:
        motion = _frame_motion(video, Path(td))
    if motion < 1.2:
        add("block" if motion < 0.5 else "warn", "dead_open",
            f"开场 0.4 秒画面变化量 {motion:.2f}，第 0 帧几乎没动")

    lufs, peak = _loudness(video)
    if lufs is not None and not (TARGET_LUFS[0] <= lufs <= TARGET_LUFS[1]):
        add("warn", "loudness", f"整体响度 {lufs:.1f} LUFS，建议 -16 ~ -14")
    if peak is not None and peak > TARGET_PEAK:
        add("warn", "peak", f"峰值 {peak:.1f} dBFS，可能削波")

    if subtitle_chars is not None and subtitle_chars > 18:
        add("warn", "subtitle_len", f"单句字幕 {subtitle_chars} 字，超过 18 字会折行压画面")

    blocked = any(i["level"] == "block" for i in issues)
    return {
        "ok": not blocked,
        "video": str(video),
        "meta": {**meta, "duration": round(dur, 2)},
        "metrics": {"black_ratio": round(_black_ratio(video, dur), 3) if dur else None,
                    "open_motion": round(motion, 2), "lufs": lufs, "peak": peak},
        "issues": issues,
        "verdict": "blocked" if blocked else ("warn" if issues else "pass"),
    }


def main(argv=None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="成片机器质检")
    ap.add_argument("video", type=Path)
    a = ap.parse_args(argv)
    r = inspect(a.video)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    import sys as _s
    _s.exit(main())
