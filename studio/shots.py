"""竖屏镜头库。

每个镜头都要回答一个问题：**这一镜里，什么在变化？**
这是 fy-code-animation 的核心判准（不做「一句话 + 图标 + 淡入」的 PPT）。
所以每个镜头函数都绑定一种「语义操作」，而不是一种排版样式。

镜头签名统一为 fn(base: RGBA, t, dur, spec, assets) -> RGBA
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import motion as mo
from . import theme as th
from . import typefx


# ------------------------------------------------------------------ helpers
def _overlay(base: Image.Image) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    return ov, ImageDraw.Draw(ov)


def _blend(base: Image.Image, ov: Image.Image) -> Image.Image:
    if base.mode != "RGBA":
        base = base.convert("RGBA")
    return Image.alpha_composite(base, ov).convert("RGB")


def _rounded(d: ImageDraw.ImageDraw, box, r: int, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def _fit_image(path: Path, box_w: int, box_h: int) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    ratio = min(box_w / img.width, box_h / img.height)
    return img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.LANCZOS)


def _sweep(sprite: Image.Image, phase: float, strength: int = 120) -> Image.Image:
    """高光扫过，裁剪在 sprite 的 alpha 内。"""
    w, h = sprite.size
    band = Image.new("L", (w, h), 0)
    bd = ImageDraw.Draw(band)
    x = -w * 0.5 + phase * (w * 1.8)
    bw = max(8, int(w * 0.16))
    for i in range(bw):
        a = int(strength * math.sin(math.pi * i / bw) ** 2)
        bd.line([(x + i, -h), (x + i - h * 0.4, 2 * h)], fill=a, width=3)
    band = band.filter(ImageFilter.GaussianBlur(10))
    band = Image.composite(band, Image.new("L", (w, h), 0), sprite.getchannel("A"))
    layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    layer.putalpha(band)
    return Image.alpha_composite(sprite, layer)


def _placeholder(w: int, h: int, label: str = "产品图") -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded(d, [0, 0, w - 1, h - 1], 28, fill=(30, 33, 38, 255), outline=(58, 63, 70, 255), width=3)
    fnt = th.font(44, bold=False)
    d.text((w // 2, h // 2), label, font=fnt, fill=(110, 116, 124, 255), anchor="mm")
    return img


# ------------------------------------------------------------------ shots
def hook(base, t, dur, spec, assets):
    """开场：大字砸入 + 背景脉冲。第 0 帧就在动，不给观众划走的机会。"""
    ov, d = _overlay(base)

    # 背景脉冲：中心一圈快速扩散又收住，制造“砸下来”的冲击
    p = mo.progress(t, 0.0, 0.55)
    if p < 1:
        r = int(mo.lerp(60, 760, mo.ease_out_expo(p)))
        a = int(90 * (1 - p))
        d.ellipse([th.W // 2 - r, th.H * 0.42 - r, th.W // 2 + r, th.H * 0.42 + r],
                  outline=(255, 255, 255, a), width=max(2, int(14 * (1 - p))))

    lines = spec.get("text") or [""]
    size = spec.get("size", 148)
    # 自动缩字号：短句要撑满，长句不能溢出
    fnt = th.font(size, bold=True)
    while size > 60 and max(fnt.getlength(l) for l in lines) > th.TEXT_MAX_W:
        size -= 6
        fnt = th.font(size, bold=True)
    wrapped: list[str] = []
    for ln in lines:
        wrapped.extend(th.wrap(ln, fnt, th.TEXT_MAX_W))

    total_h = len(wrapped) * int(size * 1.2)
    y0 = th.H * 0.40 - total_h / 2

    s_in = mo.spring(t, freq=1.75, damping=0.52)
    scale = mo.lerp(0.72, 1.0, s_in)
    alpha = int(255 * mo.clamp(t / 0.16))

    fx = spec.get("fx")
    if fx:
        # 逐字动效：文字块居中，逐字绘制（每帧都在变）
        block_w = max((fnt.getlength(l) for l in wrapped), default=0)
        typefx.draw(fx, d, wrapped, fnt, int(th.W / 2 - block_w / 2), int(y0), t,
                    th.INK, alpha, stroke=int(spec.get("stroke", 0)))
    else:
        # 默认：整块弹入 + 缩放
        block_w, block_h = th.measure_block(wrapped, fnt)
        layer = Image.new("RGBA", (max(1, block_w + 80), max(1, block_h + 60)), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        th.draw_lines(ld, wrapped, fnt, 40, 30, th.INK, alpha, spacing=1.2)
        if scale != 1.0:
            layer = layer.resize((max(1, int(layer.width * scale)),
                                  max(1, int(layer.height * scale))), Image.LANCZOS)
        ov.alpha_composite(layer, (int(th.W / 2 - layer.width / 2),
                                   int(y0 - 30 + (1 - s_in) * 60)))

    # 强调条：随时间生长，保证任何一帧都有东西在变
    bar_w = mo.ease_out_expo(mo.progress(t, 0.1, 0.9)) * (th.W - th.TEXT_X * 2)
    if bar_w > 2:
        by = y0 + total_h + 26
        d.rounded_rectangle([th.TEXT_X, by, th.TEXT_X + bar_w, by + 8], radius=4, fill=th.ACCENT + (235,))

    if spec.get("sub"):
        sub_a = int(255 * mo.progress(t, 0.35, 0.8))
        sfnt = th.font(50, bold=False)
        for i, ln in enumerate(th.wrap(spec["sub"], sfnt, th.TEXT_MAX_W)):
            d.text((th.TEXT_X, y0 + total_h + 76 + i * 66), ln, font=sfnt,
                   fill=th.INK + (int(sub_a * 0.82),))
    return _blend(base, ov)


def number(base, t, dur, spec, assets):
    """数字滚动：把「差多少」变成可看见的增长。

    规格取自 brewreel 的 counter：支持 from（旧值）、prefix/suffix、showFrom（划掉旧值）。
    """
    ov, d = _overlay(base)
    label = spec.get("label", "")
    target = float(spec.get("value", spec.get("to", 0)))
    start_val = float(spec.get("from", 0))
    prefix = spec.get("prefix", "")
    suffix = spec.get("unit", spec.get("suffix", ""))
    show_from = bool(spec.get("showFrom")) and spec.get("from") is not None
    decimals = int(spec.get("decimals", 0))

    if label:
        a = int(255 * mo.progress(t, 0.0, 0.35))
        d.text((th.TEXT_X, th.H * 0.24), label, font=th.font(52, bold=False), fill=th.MUTED + (a,))

    # 旧值：先亮出来，落定前被红线划掉
    if show_from:
        f_old = th.font(80, bold=False)
        a = int(255 * mo.progress(t, 0.0, 0.3))
        old_txt = f"{prefix}{start_val:,.{decimals}f}{suffix}"
        d.text((th.W // 2, th.H * 0.32), old_txt, font=f_old, fill=th.MUTED + (a,), anchor="mm")
        strike = mo.ease_out_cubic(mo.progress(t, 0.55, 0.95))
        if strike > 0:
            w = f_old.getlength(old_txt)
            d.line([(th.W / 2 - w / 2 - 10, th.H * 0.32),
                    (th.W / 2 - w / 2 - 10 + (w + 20) * strike, th.H * 0.32)],
                   fill=th.ACCENT_2 + (235,), width=7)

    p = mo.ease_out_cubic(mo.progress(t, 0.15, 0.95))
    val = start_val + (target - start_val) * p
    fmt = ",.{}f".format(decimals)
    shown = f"{prefix}{val:{fmt}}{suffix}"

    size = 300 if len(shown) <= 5 else (230 if len(shown) <= 7 else 180)
    fnt = th.font(size, bold=True)
    cx = th.W // 2
    y = th.H * (0.47 if show_from else 0.435)
    d.text((cx, y), shown, font=fnt, fill=th.ACCENT + (255,), anchor="mm")

    # 落定那一拍弹一下
    settle = mo.progress(t, 0.9, 1.15)
    if 0 < settle < 1:
        glow = int(90 * math.sin(math.pi * settle))
        d.ellipse([cx - 260, y - 190, cx + 260, y + 190], outline=th.ACCENT + (glow,), width=6)

    note = spec.get("note", spec.get("sub"))
    if note:
        a = int(255 * mo.progress(t, 0.95, 1.25))
        ny = th.H * (0.66 if show_from else 0.62)
        for i, ln in enumerate(th.wrap(note, th.font(48, bold=False), th.TEXT_MAX_W)):
            d.text((cx, ny + i * 66), ln, font=th.font(48, bold=False),
                   fill=th.INK + (a,), anchor="ma")
    return _blend(base, ov)


def split(base, t, dur, spec, assets):
    """对比：上下两块，中间分隔线推进。用于「不是 A 而是 B」。"""
    ov, d = _overlay(base)
    good = spec.get("b") or spec.get("good") or ""
    bad = spec.get("a") or spec.get("bad") or ""
    mid = th.H * 0.46

    f1 = th.font(64, bold=True)
    f2 = th.font(92, bold=True)
    bad_lines = th.wrap(bad, f1, th.TEXT_MAX_W)
    good_lines = th.wrap(good, f2, th.TEXT_MAX_W)

    # 上半：被否定的。整块居中，红色划线压住文字中线
    a1 = int(255 * mo.progress(t, 0.0, 0.3))
    block_h = len(bad_lines) * int(f1.size * 1.2)
    y1 = int(mid - 150 - block_h / 2)
    th.draw_lines(d, bad_lines, f1, th.TEXT_X, y1, th.MUTED, a1, spacing=1.2)

    strike = mo.ease_out_cubic(mo.progress(t, 0.5, 0.92))
    if strike > 0 and bad_lines:
        widest = max(f1.getlength(l) for l in bad_lines)
        # 只划在文字实际宽度上，不是整条画布
        d.line([(th.TEXT_X - 8, y1 + int(f1.size * 0.55)),
                (th.TEXT_X - 8 + (widest + 16) * strike, y1 + int(f1.size * 0.55))],
               fill=th.ACCENT_2 + (240,), width=9)

    # 中间分隔线：从左往右推进
    p = mo.ease_out_cubic(mo.progress(t, 0.15, 0.6))
    if p > 0:
        d.line([(th.TEXT_X, mid), (th.TEXT_X + (th.W - th.TEXT_X * 2) * p, mid)],
               fill=(58, 62, 70, 255), width=3)

    # 下半：成立的。左侧加一条强调竖条，把结论单独拎出来
    a2 = int(255 * mo.progress(t, 0.55, 0.9))
    move = int(36 * (1 - mo.ease_out_cubic(mo.progress(t, 0.55, 1.0))))
    y2 = int(mid + 70 + move)
    if a2 > 0:
        d.rounded_rectangle([th.TEXT_X - 8, y2, th.TEXT_X + 2, y2 + len(good_lines) * int(f2.size * 1.18)],
                            radius=4, fill=th.ACCENT + (a2,))
    th.draw_lines(d, good_lines, f2, th.TEXT_X + 34, y2, th.INK, a2, spacing=1.18)

    tag = spec.get("tag")
    if tag:
        ta = int(255 * mo.progress(t, 1.0, 1.3))
        d.text((th.TEXT_X + 34, y2 + len(good_lines) * int(f2.size * 1.18) + 40), tag,
               font=th.font(40, bold=False), fill=th.ACCENT + (ta,))
    return _blend(base, ov)


def line(base, t, dur, spec, assets):
    """因果路径：A 先变，经过可见的线，才影响 B。

    fy 的判准：A/B 一起弹出只是并列；必须「触发先于反应、路径连续」。
    """
    ov, d = _overlay(base)
    a_text = spec.get("a", "")
    b_text = spec.get("b", "")
    mid = th.H * 0.46
    fnt = th.font(54, bold=True)

    def box(text, cx, cy, color, alpha):
        lines = th.wrap(text, fnt, 560)
        w, h = th.measure_block(lines, fnt)
        pad_x, pad_y = 40, 30
        b = [cx - w / 2 - pad_x, cy - h / 2 - pad_y, cx + w / 2 + pad_x, cy + h / 2 + pad_y]
        _rounded(d, b, 24, fill=(26, 29, 34, int(alpha * 0.96)), outline=color + (alpha,), width=3)
        th.draw_lines(d, lines, fnt, int(b[0] + pad_x), int(b[1] + pad_y), color, alpha, anchor="la")
        return b

    cx = th.W // 2
    ay, by = mid - 300, mid + 300
    a_alpha = int(255 * mo.progress(t, 0.0, 0.35))
    if a_alpha > 0:
        a_box = box(a_text, cx, ay, th.INK, a_alpha)
    else:
        a_box = [cx - 280, ay - 60, cx + 280, ay + 60]

    # 连线：从 A 下沿走到 B 上沿，走完才点亮 B —— 因果必须有先后
    p = mo.ease_in_out_cubic(mo.progress(t, 0.3, 0.95))
    y_from = a_box[3] + 8
    y_to = by - 96
    if p > 0:
        y_now = mo.lerp(y_from, y_to, p)
        d.line([(cx, y_from), (cx, y_now)], fill=th.ACCENT + (215,), width=8)
        if p > 0.6:
            d.polygon([(cx, y_now + 34), (cx - 22, y_now + 2), (cx + 22, y_now + 2)],
                      fill=th.ACCENT + (235,))

    b_alpha = int(255 * mo.progress(t, 0.9, 1.25))
    if b_alpha > 0:
        box(b_text, cx, by, th.ACCENT, b_alpha)
    return _blend(base, ov)


def reveal(base, t, dur, spec, assets):
    """产品揭晓：从下方升起 + 高光扫过 + 标签逐个贴上。"""
    ov, d = _overlay(base)
    name = spec.get("name", "")
    image = spec.get("image")
    labels = spec.get("labels") or []

    e = mo.ease_out_cubic(mo.progress(t, 0.0, 0.75))
    box_w, box_h = 760, 760
    cx, cy = th.W // 2, int(th.H * 0.44 + (1 - e) * 240)

    if image and Path(image).exists():
        sprite = _fit_image(Path(image), box_w, box_h)
    else:
        sprite = _placeholder(box_w, box_h, spec.get("placeholder", "产品图"))
    sprite = _sweep(sprite, mo.progress(t, 0.45, 1.25), 110)

    sh = Image.new("L", (sprite.width + 80, sprite.height + 80), 0)
    ImageDraw.Draw(sh).ellipse([40, sprite.height - 10, sprite.width + 40, sprite.height + 70], fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(26))
    shadow = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    shadow.putalpha(sh)
    ov.alpha_composite(shadow, (cx - sh.width // 2, cy - sh.height // 2 + 40))
    ov.alpha_composite(sprite, (cx - sprite.width // 2, cy - sprite.height // 2))

    if name:
        a = int(255 * mo.progress(t, 0.45, 0.85))
        fnt = th.font(84, bold=True)
        nw = fnt.getlength(name)
        d.text((th.W / 2, cy + box_h // 2 + 70), name, font=fnt, fill=th.INK + (a,), anchor="ma")

    for i, lab in enumerate(labels):
        a = int(255 * mo.progress(t, 0.7 + i * 0.15, 0.95 + i * 0.15))
        if a <= 0:
            continue
        y = cy + box_h // 2 + 190 + i * 76
        d.ellipse([th.TEXT_X, y + 14, th.TEXT_X + 16, y + 30], fill=th.ACCENT + (a,))
        d.text((th.TEXT_X + 40, y), lab, font=th.font(46, bold=False), fill=th.INK + (a,))
    return _blend(base, ov)


def bullets(base, t, dur, spec, assets):
    """要点：竖线生长 + 逐条错峰，制造节奏而不是整块出现。"""
    ov, d = _overlay(base)
    items = spec.get("items") or []
    title = spec.get("title", "")
    top = th.H * 0.30

    if title:
        a = int(255 * mo.progress(t, 0, 0.3))
        d.text((th.TEXT_X, top - 110), title, font=th.font(54, bold=False), fill=th.MUTED + (a,))

    n = max(1, len(items))
    bar_h = int(th.H * 0.34)
    grow = mo.ease_out_cubic(mo.progress(t, 0.15, 1.1))
    d.rounded_rectangle([th.TEXT_X, top, th.TEXT_X + 8, top + bar_h * grow], radius=4, fill=th.ACCENT + (255,))

    for i, item in enumerate(items):
        a = int(255 * mo.progress(t, mo.stagger(i, 0.22, 0.25), mo.stagger(i, 0.22, 0.5)))
        if a <= 0:
            continue
        y = top + int(i * (bar_h / n)) + 6
        off = int(26 * (1 - mo.ease_out_cubic(mo.progress(t, mo.stagger(i, 0.22, 0.25), mo.stagger(i, 0.22, 0.55)))))
        d.text((th.TEXT_X + 46 + off, y), item, font=th.font(62, bold=True), fill=th.INK + (a,))
    return _blend(base, ov)


def _kb_crop(img: Image.Image, t: float, dur: float, zoom: float = 0.06) -> Image.Image:
    """Ken Burns：缓慢推近。没有运镜的静态图在竖屏里就是一张壁纸。"""
    p = mo.ease_in_out_cubic(mo.progress(t, 0.0, max(0.1, dur)))
    z = 1.0 + zoom * p
    w, h = img.size
    cw, ch = int(w / z), int(h / z)
    left = (w - cw) // 2
    top = int((h - ch) * 0.45)
    return img.crop((left, top, left + cw, top + ch)).resize((th.W, th.H), Image.BILINEAR)


def _caption(d, spec, t, dur, y: float):
    """图/视频上的字：先小标，再主句，最后副句。"""
    kicker = spec.get("kicker")
    if kicker:
        a = int(255 * mo.progress(t, 0.0, 0.3))
        d.text((th.TEXT_X, y - 110), kicker, font=th.font(40, bold=False), fill=th.ACCENT + (a,))

    lines = spec.get("text") or []
    fnt = th.font(spec.get("size", 88), bold=True)
    wrapped: list[str] = []
    for ln in lines:
        wrapped.extend(th.wrap(ln, fnt, th.TEXT_MAX_W))
    a = int(255 * mo.progress(t, 0.15, 0.5))
    end_y = th.draw_lines(d, wrapped, fnt, th.TEXT_X, int(y), th.INK, a, spacing=1.2,
                          stroke=4, stroke_fill=(0, 0, 0, 210))

    if spec.get("sub"):
        sa = int(255 * mo.progress(t, 0.5, 0.8))
        for i, ln in enumerate(th.wrap(spec["sub"], th.font(44, bold=False), th.TEXT_MAX_W)):
            d.text((th.TEXT_X, end_y + 18 + i * 58), ln, font=th.font(44, bold=False),
                   fill=th.INK + (int(sa * 0.85),), stroke_width=3, stroke_fill=(0, 0, 0, 190))


def _band(frame: Image.Image, top: int, bottom: int, alpha: int = 155, blur: int = 60) -> Image.Image:
    """文字底下的柔边暗带。图片可能是亮的，白字直接压上去会糊。"""
    w, h = frame.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle([0, top, w, bottom], fill=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.putalpha(mask)
    return Image.alpha_composite(frame.convert("RGBA"), layer).convert("RGB")


def art(base, t, dur, spec, assets):
    """静图镜头：一张图 + 运镜 + 压暗 + 字。

    图可以是任何来源（风格库示例、产品照、用户给的角色图）。
    风格化在管线里预处理，这里只负责「动起来 + 压字」。
    """
    key = spec.get("_asset_key")
    img = assets.get(key) if key else None
    if img is None and spec.get("image") and Path(spec["image"]).exists():
        from .art import cover_fit
        img = cover_fit(Image.open(spec["image"]), th.W, th.H, float(spec.get("focus", 0.5)))
    if img is None:
        return reveal(base, t, dur, spec, assets)

    from .art import scrim
    frame = _kb_crop(scrim(img, float(spec.get("scrim", 0.55))), t, dur)
    cy = float(spec.get("caption_y", 0.52))
    frame = _band(frame, int(th.H * (cy - 0.12)), int(th.H * (cy + 0.30)), int(spec.get("band", 165)))
    ov, d = _overlay(frame.convert("RGBA"))
    _caption(d, spec, t, dur, th.H * cy)
    return _blend(frame, ov)


def broll(base, t, dur, spec, assets):
    """真实镜头做背景：从素材视频抽好的帧里按时间取。"""
    key = spec.get("_asset_key")
    frames = assets.get(key) if key else None
    if not frames:
        return art(base, t, dur, {**spec, "image": None}, assets)

    from .art import pick_frame, scrim
    idx = min(len(frames) - 1, int(mo.progress(t, 0, max(0.01, dur)) * len(frames)))
    img = pick_frame(frames, idx / max(1, th.FPS))
    frame = scrim(img, float(spec.get("scrim", 0.5)))
    cy = float(spec.get("caption_y", 0.52))
    frame = _band(frame, int(th.H * (cy - 0.12)), int(th.H * (cy + 0.30)), int(spec.get("band", 170)))
    ov, d = _overlay(frame.convert("RGBA"))
    _caption(d, spec, t, dur, th.H * cy)
    return _blend(frame, ov)


def char(base, t, dur, spec, assets):
    """角色出镜：透明 PNG 贴底 + 轻浮动 + 上方压字。

    形象从 characters/<角色>/<动作>.png 取；取不到就退回文字卡，不崩。
    """
    from . import character

    path = spec.get("_char_path")
    if path is None:
        path = character.pick(spec.get("action", ""), spec.get("characters"))
    if path is None:
        fallback = {**spec, "text": spec.get("text") or [spec.get("action") or "（缺形象）"]}
        return hook(base, t, dur, fallback, assets)

    frame = character.place(base.convert("RGB"), Path(path), t,
                            float(spec.get("height", 0.56)),
                            int(spec.get("bottom", 0)))
    cy = float(spec.get("caption_y", 0.30))
    frame = _band(frame, int(th.H * (cy - 0.08)), int(th.H * (cy + 0.26)),
                  int(spec.get("band", 170)))
    ov, d = _overlay(frame.convert("RGBA"))
    _caption(d, spec, t, dur, th.H * cy)
    return _blend(frame, ov)


def steps(base, t, dur, spec, assets):
    """1-2-3 流程：节点依次点亮，走完打 ✓。

    规格取自 brewreel：2–4 步，标题 ≤8 字、动词开头，时长 ≈ 步数 × 1 秒 + 1.5 秒。
    """
    ov, d = _overlay(base)
    items = spec.get("items") or []
    items = items[:4]
    n = max(1, len(items))
    title = spec.get("title")

    if title:
        a = int(255 * mo.progress(t, 0.0, 0.3))
        d.text((th.TEXT_X, th.H * 0.26), title, font=th.font(50, bold=False),
               fill=th.MUTED + (a,))

    top = th.H * 0.36
    gap = min(190, (th.H * 0.42) / n)
    x_nodes = th.TEXT_X + 40
    step_len = max(0.4, (dur - 1.2) / n)

    # 竖线：随进度长出来
    grow = mo.clamp(t / max(0.3, dur - 0.6))
    d.line([(x_nodes, top), (x_nodes, top + gap * (n - 1) * grow + 1)],
           fill=(60, 66, 76, 255), width=4)

    for i, it in enumerate(items):
        start = 0.35 + i * step_len
        k = mo.ease_out_back(mo.progress(t, start, start + 0.45), 1.6)
        if k <= 0:
            continue
        done = t >= start + step_len * 0.75
        cy = top + gap * i
        r = 26 * (0.7 + 0.3 * k)

        # 节点
        fill_c = th.ACCENT + (255,) if done else (34, 38, 46, 255)
        d.ellipse([x_nodes - r, cy - r, x_nodes + r, cy + r], fill=fill_c,
                  outline=th.ACCENT + (200,), width=3)
        if done:
            d.text((x_nodes, cy), "✓", font=th.font(int(r * 1.2), bold=True),
                   fill=(18, 18, 20, 255), anchor="mm")
        else:
            d.text((x_nodes, cy), str(i + 1), font=th.font(int(r * 1.1), bold=True),
                   fill=th.INK + (220,), anchor="mm")

        # 标题与补充
        a = int(255 * mo.clamp(k))
        off = int(30 * (1 - mo.clamp(k)))
        d.text((x_nodes + 74 + off, cy - 26), str(it.get("title", ""))[:8],
               font=th.font(52, bold=True), fill=th.INK + (a,))
        if it.get("desc"):
            d.text((x_nodes + 74 + off, cy + 22), str(it["desc"])[:14],
                   font=th.font(34, bold=False), fill=th.MUTED + (a,))
    return _blend(base, ov)


def meter(base, t, dur, spec, assets):
    """仪表盘：指针从起点弹到目标值，落定后数字与判词出现。"""
    ov, d = _overlay(base)
    value = float(spec.get("value", 0))
    vmax = float(spec.get("max", 100))
    label = spec.get("label") or ""
    verdict = spec.get("verdict") or ""

    cx, cy = th.W // 2, int(th.H * 0.46)
    r = 300
    start_ang, end_ang = 150, 390     # 顺时针 240 度

    # 底弧
    d.arc([cx - r, cy - r, cx + r, cy + r], start_ang, end_ang,
          fill=(48, 52, 60, 255), width=26)

    p = mo.spring(t, freq=1.5, damping=0.62)
    frac = mo.clamp(value / vmax) * p
    ang = math.radians(start_ang + (end_ang - start_ang) * frac)
    d.arc([cx - r, cy - r, cx + r, cy + r], start_ang, start_ang + (end_ang - start_ang) * frac,
          fill=th.ACCENT + (255,), width=26)
    # 指针
    d.line([(cx, cy), (cx + math.cos(ang) * (r - 20), cy + math.sin(ang) * (r - 20))],
           fill=th.INK + (255,), width=8)
    d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=th.INK + (255,))

    shown = int(value * p)
    d.text((cx, cy + 70), str(shown), font=th.font(120, bold=True),
           fill=th.INK + (255,), anchor="mm")
    if label:
        d.text((cx, cy + 160), label, font=th.font(40, bold=False),
               fill=th.MUTED + (255,), anchor="mm")
    if verdict:
        a = int(255 * mo.progress(t, 0.9, 1.3))
        d.text((cx, cy + 230), verdict, font=th.font(46, bold=True),
               fill=th.ACCENT + (a,), anchor="mm")
    return _blend(base, ov)


def price(base, t, dur, spec, assets):
    """价格卡：原价划线，现价弹出，下面一行条件。"""
    ov, d = _overlay(base)
    now = spec.get("now", "")
    old = spec.get("old") or ""
    note = spec.get("note") or ""
    unit = spec.get("unit") or ""

    cy = th.H * 0.44
    if old:
        f_old = th.font(64, bold=False)
        a = int(255 * mo.progress(t, 0.0, 0.3))
        d.text((th.W / 2, cy - 110), old, font=f_old, fill=th.MUTED + (a,), anchor="mm")
        strike = mo.ease_out_cubic(mo.progress(t, 0.25, 0.7))
        w = f_old.getlength(old)
        if strike > 0:
            d.line([(th.W / 2 - w / 2 - 8, cy - 108),
                    (th.W / 2 - w / 2 - 8 + (w + 16) * strike, cy - 108)],
                   fill=th.ACCENT_2 + (240,), width=8)

    e = mo.spring(t, freq=1.8, damping=0.55)
    scale = 0.8 + 0.2 * e
    f_now = th.font(int(190 * scale), bold=True)
    d.text((th.W / 2, cy + 30), str(now), font=f_now, fill=th.ACCENT + (255,), anchor="mm")
    if unit:
        d.text((th.W / 2, cy + 150), unit, font=th.font(44, bold=False),
               fill=th.INK + (220,), anchor="mm")
    if note:
        a = int(255 * mo.progress(t, 0.7, 1.0))
        d.text((th.W / 2, cy + 230), note, font=th.font(38, bold=False),
               fill=th.MUTED + (a,), anchor="mm")
    return _blend(base, ov)


def quote(base, t, dur, spec, assets):
    """引用卡：大引号 + 原文 + 出处。只摘原话，不改写成更夸张的版本。"""
    ov, d = _overlay(base)
    text = spec.get("text") or ""
    who = spec.get("who") or ""

    d.text((th.TEXT_X, th.H * 0.26), "“", font=th.font(220, bold=True),
           fill=th.ACCENT + (110,))
    fnt = th.font(spec.get("size", 62), bold=True)
    lines = th.wrap(text, fnt, th.TEXT_MAX_W - 40)
    a = int(255 * mo.progress(t, 0.1, 0.5))
    y = th.H * 0.40
    for i, ln in enumerate(lines[:5]):
        d.text((th.TEXT_X + 20, y + i * int(fnt.size * 1.35)), ln, font=fnt,
               fill=th.INK + (a,))
    if who:
        wa = int(255 * mo.progress(t, 0.6, 0.9))
        yy = y + len(lines[:5]) * int(fnt.size * 1.35) + 30
        d.line([(th.TEXT_X + 20, yy), (th.TEXT_X + 100, yy)], fill=th.ACCENT + (wa,), width=5)
        d.text((th.TEXT_X + 20, yy + 26), who, font=th.font(40, bold=False),
               fill=th.MUTED + (wa,))
    return _blend(base, ov)


def cta(base, t, dur, spec, assets):
    """收尾：一句行动指令 + 账号名。慢推进制造收束感。"""
    ov, d = _overlay(base)
    main = spec.get("text") or ["关注"]
    user = spec.get("user", "")
    sub = spec.get("sub", "")

    e = mo.ease_out_cubic(mo.progress(t, 0.0, 1.0))
    y = th.H * 0.42 - int(30 * (1 - e))
    fnt = th.font(112, bold=True)
    lines = []
    for ln in main:
        lines.extend(th.wrap(ln, fnt, th.TEXT_MAX_W))
    th.draw_lines(d, lines, fnt, th.TEXT_X, int(y), th.INK, int(255 * mo.progress(t, 0, 0.4)), spacing=1.18)

    if sub:
        a = int(255 * mo.progress(t, 0.4, 0.7))
        sy = y + len(lines) * fnt.size * 1.18 + 40
        for i, ln in enumerate(th.wrap(sub, th.font(48, bold=False), th.TEXT_MAX_W)):
            d.text((th.TEXT_X, sy + i * 64), ln, font=th.font(48, bold=False), fill=th.ACCENT + (a,))

    if user:
        a = int(255 * mo.progress(t, 0.7, 1.0))
        d.line([(th.TEXT_X, th.H * 0.72), (th.TEXT_X + 120, th.H * 0.72)], fill=th.ACCENT + (a,), width=6)
        d.text((th.TEXT_X, th.H * 0.725 + 24), user, font=th.font(44, bold=False), fill=th.MUTED + (a,))
    return _blend(base, ov)


SHOTS = {
    "hook": hook,
    "number": number,
    "split": split,
    "line": line,
    "reveal": reveal,
    "bullets": bullets,
    "art": art,
    "broll": broll,
    "char": char,
    "steps": steps,
    "meter": meter,
    "price": price,
    "quote": quote,
    "cta": cta,
}


def render(base: Image.Image, shot: dict, t: float, dur: float, assets: dict) -> Image.Image:
    kind = shot.get("type", "hook")
    if kind not in SHOTS:
        raise ValueError(f"未知镜头类型：{kind}（可用：{', '.join(SHOTS)}）")
    return SHOTS[kind](base, t, dur, shot, assets)
