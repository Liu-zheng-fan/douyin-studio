"""逐帧渲染：把 script.json 变成一串 PNG。

确定性：同样输入 → 同样帧。不读时钟、不用随机数。
字幕在帧里烧，不依赖 libass（本机 ffmpeg 未必带）。
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from . import fields
from . import shots as shot_lib
from . import theme as th

SUB_MAX_CHARS = 13


def _split_caption(text: str, max_chars: int = SUB_MAX_CHARS) -> list[str]:
    """按标点和长度切字幕，一行不超过 max_chars 个汉字。"""
    if not text:
        return []
    chunks: list[str] = []
    cur = ""
    for ch in text:
        cur += ch
        if ch in "，。！？、；：,.!?;:" and len(cur) >= 6:
            chunks.append(cur)
            cur = ""
        elif len(cur) >= max_chars:
            chunks.append(cur)
            cur = ""
    if cur:
        if chunks and len(cur) < 4:
            chunks[-1] += cur
        else:
            chunks.append(cur)
    return chunks


def plan_timeline(script: dict, speech: list[float], lead: float, tail: float):
    """返回 (每镜时长, 镜头起点列表, 字幕表)。"""
    durations = [round(s + lead + tail, 3) for s in speech]
    starts: list[float] = []
    acc = 0.0
    for d in durations:
        starts.append(round(acc, 3))
        acc += d

    subs: list[tuple[float, float, str]] = []
    for i, shot in enumerate(script["shots"]):
        say = (shot.get("say") or "").strip()
        if not say:
            continue
        chunks = _split_caption(say)
        if not chunks:
            continue
        spoken = speech[i]
        per = spoken / len(chunks)
        t0 = starts[i] + lead
        for k, c in enumerate(chunks):
            subs.append((round(t0 + k * per, 3), round(t0 + (k + 1) * per, 3), c))
    return durations, starts, subs


def _active_sub(subs, t):
    for a, b, text in subs:
        if a <= t < b:
            return text
    return ""


def render_frames(script: dict, durations, starts, subs, frames_dir: Path, assets: dict) -> int:
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("*.png"):
        old.unlink()

    fps = int(script.get("fps", th.FPS))
    variant = script.get("backdrop", "dark")
    sub_y = int(script.get("subtitle_y", 1430))
    field = script.get("field")            # noise / dots / particles / flow
    drift = float(script.get("drift", 0.012))   # 每镜缓慢推近的幅度，0 关闭
    bg = th.backdrop(variant)

    n = 0
    for idx, shot in enumerate(script["shots"]):
        dur = durations[idx]
        count = max(1, int(round(dur * fps)))
        for k in range(count):
            t_local = k / fps
            t_abs = starts[idx] + t_local
            base = fields.render(field, t_abs) if field else bg.copy()
            frame = shot_lib.render(base, shot, t_local, dur, assets)
            if drift > 0:
                # 整镜缓慢推近 1.0 → 1+drift。没有它，静止的字卡在手机上像截图。
                z = 1.0 + drift * (t_local / max(dur, 0.01))
                w, h = frame.size
                cw, ch = int(w / z), int(h / z)
                left, top = (w - cw) // 2, (h - ch) // 2
                frame = frame.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BILINEAR)
            frame = th.ambient(frame, t_abs)
            text = _active_sub(subs, t_abs)
            if text:
                th.draw_subtitle(frame, text, y=sub_y)
            n += 1
            frame.save(frames_dir / f"{n:05d}.png", compress_level=1)
    return n


def write_manifest(out: Path, script: dict, durations, starts, subs, frame_count: int) -> Path:
    data = {
        "title": script.get("title"),
        "fps": script.get("fps", th.FPS),
        "size": [th.W, th.H],
        "total_seconds": round(sum(durations), 3),
        "frame_count": frame_count,
        "shots": [
            {
                "index": i,
                "type": s.get("type"),
                "start": starts[i],
                "duration": durations[i],
                "text": s.get("text") or s.get("name") or s.get("a") or s.get("label"),
            }
            for i, s in enumerate(script["shots"])
        ],
        "subtitles": [{"start": a, "end": b, "text": c} for a, b, c in subs],
    }
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_script(path: Path) -> dict:
    script = json.loads(path.read_text(encoding="utf-8"))
    if "shots" not in script or not script["shots"]:
        raise SystemExit("script.json 里没有 shots")
    script.setdefault("fps", th.FPS)
    # 分辨率写死为竖屏；如果有人填了别的值，直接纠正并提示
    want = script.get("size")
    if want and list(want) != [th.W, th.H]:
        print(f"注意：本项目只出竖屏 {th.W}x{th.H}，已忽略 size={want}")
    return script
