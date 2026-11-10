"""动态文字：逐字出现、波浪、抖动、光标。

为什么这个比背景重要：
实测给整片加动态背景，帧差只从 4.58 到 4.76（+4%）。
因为画面主体是一大块静止的字——字不动，观众眼睛就没有新东西可抓。

逐字出现（type）在开口的前 1–2 秒里每帧都在变，而且**观众会跟着字走**，
这是最低成本、最有效的"画面在动"。
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from . import motion as mo

# 每个字的出现节奏（秒）
CHAR_DELAY = 0.045


def _char_positions(lines: list[str], fnt, x: int, y: int, spacing: float):
    """把多行文字摊平成 (字符, x, y) 列表，用于逐字绘制。"""
    out = []
    cy = y
    for line in lines:
        cx = x
        for ch in line:
            out.append((ch, cx, cy))
            cx += fnt.getlength(ch)
        cy += int(fnt.size * spacing)
    return out


def draw_type(d: ImageDraw.ImageDraw, lines: list[str], fnt, x: int, y: int,
              t: float, fill, alpha: int = 255, spacing: float = 1.22,
              cps: float = 1 / CHAR_DELAY, stroke: int = 0,
              stroke_fill=(0, 0, 0, 255)) -> int:
    """逐字出现。返回整块高度结束的 y。

    打完字之后整块还在极慢地浮动——保证「任何一帧都不是静止的」。
    """
    chars = _char_positions(lines, fnt, x, y, spacing)
    shown = min(len(chars), int(t * cps) + 1)
    # 打完之后缓慢上浮 2px，来回呼吸
    drift = 0.0
    done_at = len(chars) / cps
    if t > done_at:
        drift = math.sin((t - done_at) * 1.6) * 2.0

    color = tuple(fill[:3]) + (alpha,)
    for i, (ch, cx, cy) in enumerate(chars):
        if i >= shown:
            break
        # 每个字刚出现时往下偏 10px + 放大一点点，落位后归零
        age = t - i / cps
        k = mo.clamp(age / 0.16)
        ease = mo.ease_out_cubic(k)
        dy = (1 - ease) * 10 + drift
        # 笔画描边（用于压在画面上）
        d.text((cx, cy + dy), ch, font=fnt, fill=color, anchor="la",
               stroke_width=stroke, stroke_fill=stroke_fill if stroke else None)

    # 还没打完时，末尾跟一个光标
    if shown < len(chars):
        _, cx, cy = chars[shown - 1] if shown else chars[0]
        w = fnt.getlength(chars[shown - 1][0]) if shown else fnt.size * 0.5
        if int(t * 6) % 2 == 0:
            d.rectangle([cx + w + 4, cy + fnt.size * 0.15,
                         cx + w + 4 + fnt.size * 0.12, cy + fnt.size * 1.05],
                        fill=tuple(fill[:3]) + (alpha,))
    return y + int(len(lines) * fnt.size * spacing)


def draw_wave(d: ImageDraw.ImageDraw, lines: list[str], fnt, x: int, y: int,
              t: float, fill, alpha: int = 255, spacing: float = 1.22,
              amp: float = 5.0, speed: float = 2.2, stroke: int = 0,
              stroke_fill=(0, 0, 0, 255)) -> int:
    """整行字轻微上下波动。适合已经打完、需要保持"活着"的段落。"""
    chars = _char_positions(lines, fnt, x, y, spacing)
    color = tuple(fill[:3]) + (alpha,)
    for i, (ch, cx, cy) in enumerate(chars):
        dy = math.sin(t * speed + i * 0.42) * amp
        d.text((cx, cy + dy), ch, font=fnt, fill=color, anchor="la",
               stroke_width=stroke, stroke_fill=stroke_fill if stroke else None)
    return y + int(len(lines) * fnt.size * spacing)


def draw_pop(d: ImageDraw.ImageDraw, lines: list[str], fnt, x: int, y: int,
             t: float, fill, alpha: int = 255, spacing: float = 1.22,
             stagger: float = 0.06, stroke: int = 0,
             stroke_fill=(0, 0, 0, 255)) -> int:
    """逐字弹出：每个字带一点回弹，适合标题。"""
    chars = _char_positions(lines, fnt, x, y, spacing)
    color = tuple(fill[:3]) + (alpha,)
    for i, (ch, cx, cy) in enumerate(chars):
        age = t - i * stagger
        if age < 0:
            continue
        k = mo.clamp(age / 0.28)
        s = mo.ease_out_back(k, 1.9)
        dy = (1 - s) * 16
        a = int(alpha * mo.clamp(age / 0.1))
        d.text((cx, cy + dy), ch, font=fnt, fill=tuple(fill[:3]) + (a,), anchor="la",
               stroke_width=stroke, stroke_fill=stroke_fill if stroke else None)
    return y + int(len(lines) * fnt.size * spacing)


FX = {"type": draw_type, "wave": draw_wave, "pop": draw_pop}


def draw(fx: str, d: ImageDraw.ImageDraw, lines: list[str], fnt, x: int, y: int,
         t: float, fill, alpha: int = 255, **kw) -> int:
    fn = FX.get(fx or "pop")
    if fn is None:
        raise ValueError(f"未知文字动效 {fx}，可用：{', '.join(FX)}")
    return fn(d, lines, fnt, x, y, t, fill, alpha, **kw)
