"""竖屏封面：3:4（1080x1440，主页网格用）与 9:16 两版。

封面的唯一任务是「让人点」。所以：
- 主标题占上半屏，字号自动撑满但不溢出
- 顶部一条斜切色带定住视线
- 产品图放右下，不与标题抢位置
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import shots as sh
from . import theme as th

COVER_W, COVER_H = 1080, 1440
PAD = 64


def build(script: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    title = script.get("cover_title") or script.get("title") or ""
    kicker = script.get("cover_kicker", "")
    handle = script.get("handle", "")
    image = script.get("cover_image")

    img = Image.new("RGB", (COVER_W, COVER_H), th.BG)
    ov = Image.new("RGBA", (COVER_W, COVER_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # 顶部斜切色带
    d.polygon([(0, 0), (COVER_W, 0), (COVER_W, 170), (0, 250)], fill=th.ACCENT + (255,))
    if kicker:
        d.text((PAD, 78), kicker, font=th.font(44, bold=True), fill=(18, 18, 20, 255), anchor="la")

    # 标题：字号从 132 往下降，直到 ≤2 行且每行不超宽（2 行是手机首屏能读完的上限）
    max_w = COVER_W - PAD * 2
    size = 132
    lines: list[str] = []
    while size >= 64:
        fnt = th.font(size, bold=True)
        lines = []
        for raw in title.split("\n"):
            lines.extend(th.wrap(raw, fnt, max_w))
        if len(lines) <= 2 and all(fnt.getlength(l) <= max_w for l in lines):
            break
        size -= 8
    fnt = th.font(size, bold=True)
    top = 330
    lh = int(size * 1.24)
    for i, ln in enumerate(lines):
        d.text((PAD, top + i * lh), ln, font=fnt, fill=th.INK + (255,), anchor="la")

    # 高亮胶囊：一句话说清卖点（brewreel 的 caption 规则：一行、≤12 字）
    pill = script.get("cover_pill")
    if pill:
        pf = th.font(38, bold=True)
        pw = int(pf.getlength(pill)) + 52
        py = top + len(lines) * lh + 40
        d.rounded_rectangle([PAD, py, PAD + pw, py + 66], radius=33, fill=th.ACCENT + (255,))
        d.text((PAD + 26, py + 33), pill, font=pf, fill=(18, 18, 20, 255), anchor="lm")

    # 产品：右下，控制在 440 以内，避免压到标题
    box = 440
    if image and Path(image).exists():
        sprite = sh._fit_image(Path(image), box, box)
    else:
        sprite = sh._placeholder(box, box, script.get("cover_placeholder", "产品图"))
    sprite = sh._sweep(sprite, 0.6, 120)

    cx = COVER_W - PAD - sprite.width // 2
    cy = COVER_H - 300 - sprite.height // 2

    shadow_h = 120
    sh_layer = Image.new("L", (sprite.width + 80, shadow_h), 0)
    ImageDraw.Draw(sh_layer).ellipse([40, 0, sprite.width + 40, shadow_h - 10], fill=110)
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(28))
    shadow = Image.new("RGBA", sh_layer.size, (0, 0, 0, 0))
    shadow.putalpha(sh_layer)
    ov.alpha_composite(shadow, (cx - sh_layer.width // 2, cy + sprite.height // 2 - 50))
    ov.alpha_composite(sprite, (cx - sprite.width // 2, cy - sprite.height // 2))

    if handle:
        d.text((PAD, COVER_H - 92), handle, font=th.font(40, bold=False),
               fill=th.MUTED + (255,), anchor="la")

    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    p34 = out_dir / "cover_3x4.png"
    img.save(p34)
    p916 = out_dir / "cover_9x16.png"
    img.resize((th.W, th.H), Image.LANCZOS).save(p916)
    return {"cover_3x4": str(p34), "cover_9x16": str(p916)}
