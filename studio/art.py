"""图像与视频素材：载入、裁切、风格化、抽帧。

这个模块解决一个现实问题：**没有生图模型**。
所以路线是「已有的图 → 用算法改成本片的画风 → 合成进画面」，
而不是「用文字生成一张新图」。

风格化不是滤镜堆叠，每种处理都对应风格库里的一类画风：
    halftone  美漫网点（K13）
    pop       波普（K14）
    duotone   双色调/丝网印（L/M 类）
    ink       线稿/剪影（K 类低彩度）
    chalk     粉笔黑板（K10）
    poster    海报色块
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

STYLES = ("none", "halftone", "pop", "duotone", "ink", "chalk", "poster")


# ------------------------------------------------------------------ 基础
def cover_fit(img: Image.Image, w: int, h: int, focus: float = 0.5) -> Image.Image:
    """等比铺满并居中裁切。focus 控制纵向取景位置（0 顶 1 底）。"""
    img = img.convert("RGB")
    scale = max(w / img.width, h / img.height)
    nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = int((nh - h) * focus)
    return img.crop((left, top, left + w, top + h))


def _gray(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"), dtype=np.float32) / 255.0


def _to_img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))


def stylize(img: Image.Image, style: str = "none", accent=(255, 214, 102)) -> Image.Image:
    if style in (None, "", "none"):
        return img.convert("RGB")
    if style not in STYLES:
        raise ValueError(f"未知风格 {style}，可用：{', '.join(STYLES)}")

    img = img.convert("RGB")

    if style == "poster":
        q = img.quantize(colors=6, method=Image.MEDIANCUT).convert("RGB")
        return Image.blend(img, q, 0.75)

    if style == "duotone":
        g = _gray(img)
        dark = np.array([18, 20, 26], dtype=np.float32) / 255
        light = np.array(accent, dtype=np.float32) / 255
        out = dark[None, None, :] + (light - dark)[None, None, :] * g[:, :, None]
        return _to_img(out)

    if style == "pop":
        # 色阶压缩 + 轻微通道错位，做出丝网印的廉价感
        q = img.quantize(colors=5, method=Image.MEDIANCUT).convert("RGB")
        r, g, b = q.split()
        r = ImageOps.autocontrast(r, cutoff=2)
        shifted = Image.merge("RGB", (r, g, b))
        base = np.asarray(shifted, dtype=np.float32)
        off = np.roll(base, 6, axis=1)
        out = np.clip(base * 0.85 + off * 0.15, 0, 255)
        return Image.fromarray(out.astype(np.uint8)).filter(ImageFilter.SMOOTH)

    if style == "halftone":
        g = _gray(img)
        h, w = g.shape
        cell = 9
        paper = Image.new("RGB", (w, h), (245, 241, 232))
        d = ImageDraw.Draw(paper)
        for y in range(0, h, cell):
            for x in range(0, w, cell):
                block = g[y:y + cell, x:x + cell]
                if block.size == 0:
                    continue
                v = 1.0 - float(block.mean())          # 越暗点越大
                r = v * cell * 0.62
                if r > 0.4:
                    cx, cy = x + cell / 2, y + cell / 2
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(20, 20, 24))
        return paper

    if style == "ink":
        edges = img.convert("L").filter(ImageFilter.FIND_EDGES)
        e = np.asarray(edges, dtype=np.float32) / 255.0
        e = np.clip(e * 3.2, 0, 1)
        out = np.ones((e.shape[0], e.shape[1], 3), dtype=np.float32) * 0.06
        out[:, :, 0] += e * 0.9
        out[:, :, 1] += e * 0.9
        out[:, :, 2] += e * 0.95
        return _to_img(out)

    if style == "chalk":
        g = _gray(img)
        edges = img.convert("L").filter(ImageFilter.FIND_EDGES)
        e = np.clip(np.asarray(edges, dtype=np.float32) / 255.0 * 3.6, 0, 1)
        board = np.array([28, 34, 32], dtype=np.float32) / 255
        out = np.ones((g.shape[0], g.shape[1], 3), dtype=np.float32) * board
        # 用原图亮度做淡淡的填充，再加白色描边
        out += g[:, :, None] * 0.10
        out += e[:, :, None] * np.array([0.92, 0.94, 0.90], dtype=np.float32)
        return _to_img(out)

    return img


def scrim(img: Image.Image, strength: float = 0.72, top: bool = True, bottom: bool = True) -> Image.Image:
    """上下压暗，保证白字可读。纯黑渐变，不做花哨。"""
    w, h = img.size
    ov = Image.new("L", (1, h), 0)
    px = ov.load()
    for y in range(h):
        k = 0.0
        if top and y < h * 0.45:
            k = max(k, (1 - y / (h * 0.45)) ** 1.6)
        if bottom and y > h * 0.5:
            k = max(k, ((y - h * 0.5) / (h * 0.5)) ** 1.8)
        px[0, y] = int(255 * k * strength)
    ov = ov.resize((w, h))
    dark = Image.new("RGB", img.size, (0, 0, 0))
    return Image.composite(dark, img, ov)


# ------------------------------------------------------------------ 视频抽帧
def extract_frames(path: Path, out_dir: Path, size: tuple[int, int], fps: int = 30,
                   max_frames: int = 240, blur: float = 0) -> list[Path]:
    """把一段素材视频抽成帧。用于「真实镜头做背景」的 broll 镜头。

    blur>0 时在 ffmpeg 里就糊掉——铺底素材常常带大字，不糊会像图层没对齐。
    """
    from . import ff

    out_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{path}|{size}|{fps}|{blur}|{path.stat().st_mtime_ns}".encode()).hexdigest()[:12]
    cache = out_dir / key
    if cache.exists() and any(cache.iterdir()):
        return sorted(cache.glob("*.png"))

    cache.mkdir(parents=True, exist_ok=True)
    w, h = size
    vf = f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if blur > 0:
        vf += f",gblur=sigma={blur}"
    ff.run([
        ff.ffmpeg(), "-y", "-loglevel", "error", "-i", str(path),
        "-vf", vf, "-frames:v", str(max_frames), str(cache / "%05d.png"),
    ])
    frames = sorted(cache.glob("*.png"))
    if not frames:
        raise RuntimeError(f"从 {path} 抽不出帧")
    return frames


def pick_frame(frames: list[Path], t: float, fps: int = 30) -> Image.Image:
    if not frames:
        raise ValueError("没有可用帧")
    idx = min(len(frames) - 1, max(0, int(t * fps)))
    return Image.open(frames[idx]).convert("RGB")
