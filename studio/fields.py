"""程序化动态背景。

移植自 fy-code-animation 的 implementations/backgrounds（FlowField / ParticleAtmosphere /
DotGrid / NoiseGradient / LightSweep / Grain），以及它的 readingAttenuation 思路：
**背景在文字区域自动衰减**，保证白字永远压得住。

为什么需要：纯色底 + 大字，帧差只有 4–6，手机上像"没加载出来"。
背景只要缓慢流动，帧差就能翻倍，而观众的注意力仍然在文字上。

所有函数都是确定性的：同一个 (kind, t, seed) 永远得到同一帧。
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import theme as th


def _rand(seed: str, key: str) -> float:
    """确定性伪随机：同 key 永远同值。不用 random 模块，避免状态。"""
    h = hashlib.md5(f"{seed}:{key}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def _smooth(x: float) -> float:
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ fields
_GRID_CACHE: dict[tuple, np.ndarray] = {}


def _grid(seed: str, k: int, freq: int) -> np.ndarray:
    """噪声网格与时间无关，缓存起来——这一项省掉 60% 的耗时。"""
    key = (seed, k, freq)
    g = _GRID_CACHE.get(key)
    if g is None:
        gh = gw = freq + 2
        g = np.array([[_rand(seed, f"{k}:{i}:{j}") for j in range(gw)] for i in range(gh)],
                     dtype=np.float32)
        _GRID_CACHE[key] = g
    return g


def noise_field(t: float, w: int = th.W, h: int = th.H, seed: str = "noise",
                colors=((16, 18, 24), (46, 52, 64)), octaves: int = 3,
                cell: int = 22, speed: float = 0.06) -> Image.Image:
    """低分辨率值噪声，上采样后很柔和，成本极低。"""
    cols, rows = max(2, w // cell), max(2, h // cell)
    ph = t * speed
    acc = np.zeros((rows, cols), dtype=np.float32)
    total = 0.0
    for k in range(octaves):
        a = 0.5 ** k
        freq = 3 * (2 ** k)
        grid = _grid(seed, k, freq)
        gh, gw = grid.shape
        ys = np.linspace(0, gh - 1.001, rows) + ph
        xs = np.linspace(0, gw - 1.001, cols) + ph * 0.6
        y0, x0 = ys.astype(int) % (gh - 1), xs.astype(int) % (gw - 1)
        fy, fx = ys - np.floor(ys), xs - np.floor(xs)
        v = (grid[y0][:, x0] * (1 - fx) + grid[y0][:, x0 + 1] * fx) * (1 - fy)[:, None] + \
            (grid[y0 + 1][:, x0] * (1 - fx) + grid[y0 + 1][:, x0 + 1] * fx) * fy[:, None]
        acc += a * v
        total += a
    acc /= total
    lo, hi = np.array(colors[0], dtype=np.float32), np.array(colors[1], dtype=np.float32)
    rgb = lo[None, None, :] + (hi - lo)[None, None, :] * acc[:, :, None]
    img = Image.fromarray(rgb.astype(np.uint8), "RGB")
    return img.resize((w, h), Image.BILINEAR)


def dots(t: float, w: int = th.W, h: int = th.H, spacing: int = 54,
         color=(120, 132, 148), focus: tuple[int, int] | None = None,
         amplitude: float = 5.0) -> Image.Image:
    """点阵 + 从中心扩散的涟漪。"""
    img = Image.new("RGB", (w, h), th.BG)
    d = ImageDraw.Draw(img)
    fx, fy = focus or (w // 2, int(h * 0.42))
    for y in range(spacing // 2, h, spacing):
        for x in range(spacing // 2, w, spacing):
            dx, dy = x - fx, y - fy
            r = math.hypot(dx, dy) or 1.0
            u = t - r / 520.0
            wave = 0.0 if u < 0 else math.sin(u * 13) * math.exp(-u * 3.5) * amplitude
            px = x + wave * dx / r
            py = y + wave * dy / r
            d.ellipse([px - 1.4, py - 1.4, px + 1.4, py + 1.4], fill=color)
    return img


def particles(t: float, w: int = th.W, h: int = th.H, count: int = 70,
              seed: str = "p", color=(150, 168, 186)) -> Image.Image:
    """漂浮尘埃：慢速漂移 + 呼吸。"""
    img = Image.new("RGB", (w, h), th.BG)
    d = ImageDraw.Draw(img)
    phase = (t % 14) / 14 * math.pi * 2
    for i in range(count):
        rx, ry = _rand(seed, f"{i}x"), _rand(seed, f"{i}y")
        a = _rand(seed, f"{i}a") * math.pi * 2
        x = rx * w + math.sin(phase + a) * 26
        y = ry * h + math.cos(phase + a) * 20
        r = 0.8 + ry * 2.2
        alpha = 0.25 + 0.6 * ry
        c = tuple(int(v * alpha + b * (1 - alpha)) for v, b in zip(color, th.BG))
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    return img


def flow(t: float, w: int = th.W, h: int = th.H, lines: int = 34, steps: int = 16,
         step_len: float = 26, color=(58, 66, 78)) -> Image.Image:
    """流场短线：沿噪声方向画短线段，缓慢旋转。"""
    img = Image.new("RGB", (w, h), th.BG)
    d = ImageDraw.Draw(img)
    phase = math.sin(t * 0.25) * math.pi
    for i in range(lines):
        x = _rand("f", f"{i}x") * w
        y = _rand("f", f"{i}y") * h
        for _ in range(steps):
            ang = 1.8 * math.sin(x / w * 5 + phase) + 1.3 * math.cos(y / h * 4 - phase)
            nx, ny = x + math.cos(ang) * step_len, y + math.sin(ang) * step_len
            d.line([(x, y), (nx, ny)], fill=color, width=2)
            x, y = nx, ny
            if not (-w < x < 2 * w and -h < y < 2 * h):
                break
    return img.filter(ImageFilter.GaussianBlur(1.2))


# ------------------------------------------------------------------ compose
_ATT_CACHE: dict[tuple, Image.Image] = {}


def reading_attenuation(img: Image.Image, box: tuple[int, int, int, int] | None = None,
                        strength: float = 0.55) -> Image.Image:
    """文字区域把背景压暗。没有它，浮动的点会穿过文字，读起来很脏。

    蒙版与时间无关，缓存——高斯模糊 90 是这里最贵的一步。
    """
    w, h = img.size
    x0, y0, x1, y1 = box or (0, int(h * 0.34), w, int(h * 0.86))
    key = (w, h, x0, y0, x1, y1, round(strength, 2))
    mask = _ATT_CACHE.get(key)
    if mask is None:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rectangle([x0, y0, x1, y1], fill=int(255 * strength))
        mask = mask.filter(ImageFilter.GaussianBlur(90))
        _ATT_CACHE[key] = mask
    dark = Image.new("RGB", (w, h), th.BG)
    return Image.composite(dark, img, mask)


FIELDS = {
    "noise": noise_field,
    "dots": dots,
    "particles": particles,
    "flow": flow,
}


def render(kind: str = "noise", t: float = 0.0, attenuate: bool = True,
           scale: float = 0.5) -> Image.Image:
    """半分辨率画，再放大。背景本来就要虚，省一半以上时间。"""
    if kind not in FIELDS:
        raise ValueError(f"未知背景 {kind}，可用：{', '.join(FIELDS)}")
    w, h = max(2, int(th.W * scale)), max(2, int(th.H * scale))
    img = FIELDS[kind](t, w, h)
    if (w, h) != (th.W, th.H):
        img = img.resize((th.W, th.H), Image.BILINEAR)
    if attenuate:
        img = reading_attenuation(img)
    return img


def light_sweep(img: Image.Image, progress: float, opacity: float = 0.12) -> Image.Image:
    """一道斜向扫光。用于镜头切换或强调。"""
    w, h = img.size
    x = -w * 0.6 + progress * w * 2.2
    ov = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(ov)
    band = int(w * 0.22)
    for i in range(band):
        a = int(255 * opacity * math.sin(math.pi * i / band) ** 2)
        d.line([(x + i, -h * 0.4), (x + i - h * 0.5, h * 1.4)], fill=a, width=2)
    ov = ov.filter(ImageFilter.GaussianBlur(24))
    white = Image.new("RGB", (w, h), (255, 250, 240))
    return Image.composite(white, img, ov)
