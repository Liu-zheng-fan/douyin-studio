"""转场：把两个镜头接起来，而不是硬切。

移植自 fy-code-animation 的 implementations/transitions：
crossfade / fadeThrough / directionalWipe / push / zoomThrough。
原版是 React 的 style 对象，这里是逐帧 PIL 合成——因为我们本来就在逐帧渲染。

为什么需要：硬切在 26 秒里出现 5 次，观众会把每次切换读成"卡了一下"。
带方向的转场会把注意力顺着推向下一个画面。
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

TRANSITIONS = ("crossfade", "fade", "wipe", "push", "zoom", "none")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _slide(img: Image.Image, dx: int, dy: int) -> Image.Image:
    out = Image.new("RGB", img.size, (0, 0, 0))
    out.paste(img, (dx, dy))
    return out


def blend(prev: Image.Image, cur: Image.Image, p: float,
          kind: str = "crossfade", direction: str = "left",
          softness: int = 90) -> Image.Image:
    """p 从 0 到 1：0 完全是上一镜，1 完全是这一镜。"""
    p = _clamp01(p)
    if kind in ("none", None) or p >= 1.0:
        return cur
    if p <= 0.0:
        return prev
    if kind == "crossfade":
        return Image.blend(prev, cur, p)

    if kind == "fade":
        # 先压到黑，再从黑出来
        if p < 0.5:
            k = 1 - p * 2
            black = Image.new("RGB", prev.size, (0, 0, 0))
            return Image.blend(prev, black, k)
        k = (p - 0.5) * 2
        black = Image.new("RGB", cur.size, (0, 0, 0))
        return Image.blend(black, cur, k)

    w, h = cur.size

    if kind == "wipe":
        mask = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(mask)
        if direction in ("left", "right"):
            edge = int(p * (w + softness * 2)) - softness
            if direction == "left":
                d.rectangle([0, 0, max(0, edge), h], fill=255)
            else:
                d.rectangle([w - max(0, edge), 0, w, h], fill=255)
        else:
            edge = int(p * (h + softness * 2)) - softness
            if direction == "down":
                d.rectangle([0, 0, w, max(0, edge)], fill=255)
            else:
                d.rectangle([0, h - max(0, edge), w, h], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(softness / 3))
        return Image.composite(cur, prev, mask)

    if kind == "push":
        e = p * p * (3 - 2 * p)
        canvas = Image.new("RGB", (w, h), (0, 0, 0))
        if direction in ("left", "right"):
            dx = int(w * e)
            if direction == "left":       # 新画面从右边推进来
                canvas.paste(prev, (-dx, 0))
                canvas.paste(cur, (w - dx, 0))
            else:
                canvas.paste(prev, (dx, 0))
                canvas.paste(cur, (dx - w, 0))
        else:
            dy = int(h * e)
            if direction == "up":         # 新画面从下方推进来
                canvas.paste(prev, (0, -dy))
                canvas.paste(cur, (0, h - dy))
            else:
                canvas.paste(prev, (0, dy))
                canvas.paste(cur, (0, dy - h))
        return canvas

    if kind == "zoom":
        # 新画面从放大状态落回原位，旧画面同时被推走
        e = p * p * (3 - 2 * p)
        z = 1.0 + 0.35 * (1 - e)
        cw, ch = int(w / z), int(h / z)
        left, top = (w - cw) // 2, (h - ch) // 2
        big = cur.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BILINEAR)
        shrink = 1.0 + 0.12 * e
        sw, sh = int(w / shrink), int(h / shrink)
        small = prev.crop(((w - sw) // 2, (h - sh) // 2, (w - sw) // 2 + sw, (h - sh) // 2 + sh)).resize((w, h), Image.BILINEAR)
        return Image.blend(small, big, e)

    return Image.blend(prev, cur, p)


def pick(script: dict) -> tuple[str, str, float]:
    """从脚本里读转场设置。返回 (类型, 方向, 时长秒)。"""
    kind = script.get("transition", "crossfade")
    if kind not in TRANSITIONS:
        kind = "crossfade"
    direction = script.get("transition_dir", "left")
    dur = float(script.get("transition_dur", 0.28))
    return kind, direction, max(0.05, min(0.8, dur))
