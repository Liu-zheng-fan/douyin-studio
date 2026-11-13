"""后期三件套：bloom、颗粒、暗角。

移植自 vibe-knowledge-film 的 vk.js:204/258-266（Canvas 版 bloom + 颗粒 + 暗角）。
为什么必须有：PIL 逐帧渲染的画面是"干净的死"，而参考片每个像素每帧都在动——
颗粒本身就是帧间差异的来源，这一项能把帧差直接拉起来。

顺序：bloom → 颗粒 → 暗角。全都用 numpy，1080×1920 单帧约 40ms。
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

_GRAIN: list[np.ndarray] = []
_VIGNETTE: dict[tuple[int, int], np.ndarray] = {}


def _grain_plates(size=(480, 270), n: int = 6, seed: int = 7) -> list[np.ndarray]:
    """预生成 n 张颗粒图。按帧序号轮换，避免静态噪点看起来像脏屏。"""
    if _GRAIN:
        return _GRAIN
    rng = np.random.default_rng(seed)
    for _ in range(n):
        a = rng.normal(0, 1.0, (size[1], size[0])).astype(np.float32)
        a = np.clip(a * 26 + 128, 0, 255)
        _GRAIN.append(a)
    return _GRAIN


def _vignette_mask(w: int, h: int, strength: float = 0.35) -> np.ndarray:
    key = (w, h)
    if key in _VIGNETTE:
        return _VIGNETTE[key]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / 1.4142
    mask = np.clip(1.0 - strength * np.power(r, 2.2), 0, 1)
    _VIGNETTE[key] = mask
    return mask


def apply(frame: Image.Image, t: float, frame_index: int = 0,
          bloom: float = 0.0, grain: float = 0.0, vignette: float = 0.0) -> Image.Image:
    """按需叠加三项。参数为 0 时跳过，零成本。"""
    if not (bloom or grain or vignette):
        return frame

    w, h = frame.size
    arr = np.asarray(frame.convert("RGB"), dtype=np.float32)

    if bloom > 0:
        # 降采样 → 模糊 → 只留高光 → 加回去（对应 vk.js 的两档 bloom）
        small = frame.resize((max(1, w // 4), max(1, h // 4)), Image.BILINEAR)
        glow = small.filter(ImageFilter.GaussianBlur(3)).resize((w, h), Image.BILINEAR)
        g = np.asarray(glow, dtype=np.float32)
        g = np.maximum(g - 110.0, 0.0)          # 只让高光发光
        arr = arr + g * bloom

    if grain > 0:
        plates = _grain_plates()
        plate = plates[frame_index % len(plates)]
        up = Image.fromarray(plate.astype(np.uint8), "L").resize((w, h), Image.BILINEAR)
        n = np.asarray(up, dtype=np.float32) - 128.0
        arr = arr + n[..., None] * grain

    if vignette > 0:
        arr = arr * _vignette_mask(w, h, vignette)[..., None]

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
