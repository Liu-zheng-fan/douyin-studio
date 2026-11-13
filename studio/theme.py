"""竖屏视觉系统：画布、安全区、配色、字体、中文断行与字幕样式。

抖音的关键约束都集中在这里：
- 9:16，1080x1920
- 上下各留出被 App UI 遮挡的区域（标题、简介、按钮）
- 字幕必须在安全区内、单行不超过 ~13 个汉字
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ------------------------------------------------------------------ canvas
W, H = 1080, 1920
FPS = 30

# 抖音界面会在底部压住「音乐、文案、按钮」，顶部压住返回和搜索。
SAFE_TOP = 300
SAFE_BOTTOM = 1620
TEXT_X = 84                      # 左边界
TEXT_MAX_W = W - TEXT_X * 2      # 右侧同样留 84

# ------------------------------------------------------------------ palette
BG = (10, 11, 13)
BG_SOFT = (22, 24, 28)
INK = (246, 244, 239)            # 主文字，暖白
MUTED = (140, 146, 154)
ACCENT = (255, 214, 102)         # 抖音感的暖黄，用于强调与数字
ACCENT_2 = (255, 92, 92)         # 警示/对比
STEEL_HI = (233, 237, 240)
STEEL_LO = (86, 93, 101)

# 浅色主题：参照片（大肥鱼那类图解视频）用的就是浅底 + 深字 + 彩色卡片
LIGHT = {
    "BG": (247, 245, 239),
    "BG_SOFT": (255, 255, 255),
    "INK": (26, 26, 28),
    "MUTED": (108, 112, 120),
    "ACCENT": (255, 138, 61),
    "ACCENT_2": (226, 74, 74),
    "CARD": (255, 255, 255),
    "BORDER": (223, 218, 208),
}
DARK = {
    "BG": (10, 11, 13), "BG_SOFT": (22, 24, 28),
    "INK": (246, 244, 239), "MUTED": (140, 146, 154),
    "ACCENT": (255, 214, 102), "ACCENT_2": (255, 92, 92),
    "CARD": (24, 26, 31), "BORDER": (52, 56, 64),
}

CURRENT = "dark"


def use(name: str = "dark") -> None:
    """切换整套配色。渲染开始前调用一次，之后所有 th.XXX 都跟着变。"""
    global BG, BG_SOFT, INK, MUTED, ACCENT, ACCENT_2, CARD, BORDER, CURRENT
    pal = LIGHT if name == "light" else DARK
    BG = pal["BG"]
    BG_SOFT = pal["BG_SOFT"]
    INK = pal["INK"]
    MUTED = pal["MUTED"]
    ACCENT = pal["ACCENT"]
    ACCENT_2 = pal["ACCENT_2"]
    CARD = pal["CARD"]
    BORDER = pal["BORDER"]
    CURRENT = "light" if name == "light" else "dark"


CARD = DARK["CARD"]
BORDER = DARK["BORDER"]

FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
FONT_REG = "C:/Windows/Fonts/msyh.ttc"


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


# ------------------------------------------------------------------ backdrop
def backdrop(variant: str = "dark") -> Image.Image:
    """纯色底 + 极轻的中心光晕。不做渐变噪点，保证编码后干净。"""
    base = Image.new("RGB", (W, H), BG)
    if variant == "flat":
        return base
    if CURRENT == "light":
        # 纸感：极淡的斜纹 + 中心微亮，避免大块死白
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for y in range(-H, H * 2, 64):
            d.line([(0, y), (W, y + W * 0.35)], fill=(0, 0, 0, 6), width=2)
        glow = Image.new("L", (W, H), 0)
        gd = ImageDraw.Draw(glow)
        gd.ellipse([-W * 0.2, H * 0.1, W * 1.2, H * 0.9], fill=90)
        glow = glow.filter(ImageFilter.GaussianBlur(200))
        paper = Image.new("RGB", (W, H), (255, 253, 246))
        base = Image.composite(paper, base, glow)
        return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")

    glow = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(glow)
    d.ellipse([-W * 0.3, H * 0.18, W * 1.3, H * 0.95], fill=58)
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    warm = Image.new("RGB", (W, H), (28, 28, 32))
    return Image.composite(warm, base, glow)


# ------------------------------------------------------------------ text
def is_wide(ch: str) -> bool:
    """粗略判断是否中文/全角，用于按「汉字宽度」断行。"""
    return ord(ch) > 0x2E7F


def wrap(text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """按实际像素宽度断行；中文可在任意字间断，英文尽量在空格断。"""
    lines: list[str] = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + ch
        if fnt.getlength(trial) <= max_w:
            cur = trial
            continue
        # 需要断行
        if ch == " " or (not is_wide(ch) and " " in cur):
            cut = cur.rfind(" ")
            if cut > 0:
                lines.append(cur[:cut])
                cur = cur[cut + 1:] + ("" if ch == " " else ch)
                continue
        lines.append(cur)
        cur = "" if ch == " " else ch
    if cur:
        lines.append(cur)
    return lines


def draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    fnt: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    fill: tuple,
    alpha: int = 255,
    spacing: float = 1.22,
    anchor: str = "la",
    stroke: int = 0,
    stroke_fill=(0, 0, 0, 255),
) -> int:
    """逐行绘制，返回下一行的 y。alpha 用于淡入，stroke 用于字幕。"""
    color = tuple(fill[:3]) + (alpha,)
    cy = y
    for line in lines:
        draw.text((x, cy), line, font=fnt, fill=color, anchor=anchor,
                  stroke_width=stroke, stroke_fill=stroke_fill if stroke else None)
        cy += int(fnt.size * spacing)
    return cy


def measure_block(lines: list[str], fnt: ImageFont.FreeTypeFont, spacing: float = 1.22) -> tuple[int, int]:
    w = max((fnt.getlength(l) for l in lines), default=0)
    h = int(fnt.size * spacing * max(1, len(lines)))
    return int(w), h


# ------------------------------------------------------------------ subtitle
def draw_subtitle(canvas: Image.Image, text: str, y: int = 1430) -> None:
    """字幕：粗白字 + 黑描边，两行上限，居中。抖音基本静音观看，字幕不是可选项。"""
    if not text:
        return
    fnt = font(58, bold=True)
    if CURRENT == "light":
        fnt = font(56, bold=True)
    lines = wrap(text, fnt, TEXT_MAX_W)
    if len(lines) > 2:
        lines = [lines[0], "".join(lines[1:])]
        lines = wrap(lines[1], fnt, TEXT_MAX_W) if len(lines[1]) else lines
        lines = lines[:2]
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    lh = int(fnt.size * 1.28)
    top = y - (len(lines) - 1) * lh // 2
    # 浅色底上用深字 + 白描边，深色底上反过来——否则字幕直接看不见
    ink = (18, 18, 20, 255) if CURRENT == "light" else (255, 255, 255, 255)
    stroke = (255, 255, 255, 235) if CURRENT == "light" else (0, 0, 0, 235)
    for i, line in enumerate(lines):
        d.text((W // 2, top + i * lh), line, font=fnt, fill=ink,
               anchor="mm", stroke_width=6, stroke_fill=stroke)
    merged = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    canvas.paste(merged, (0, 0))


# ------------------------------------------------------------------ utils
def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def grade(img: Image.Image, spec: dict | None) -> Image.Image:
    """轻量调色（取自 EAC 的 grade 思路，砍到本机能做的部分）。

    spec: {"contrast": 1.08, "saturation": 1.05, "warmth": 0.02, "lift": 4}
    """
    if not spec:
        return img
    from PIL import ImageEnhance

    if spec.get("contrast"):
        img = ImageEnhance.Contrast(img).enhance(float(spec["contrast"]))
    if spec.get("saturation"):
        img = ImageEnhance.Color(img).enhance(float(spec["saturation"]))
    warmth = float(spec.get("warmth", 0))
    lift = int(spec.get("lift", 0))
    if warmth or lift:
        r, g, b = img.split()
        if warmth:
            r = r.point(lambda v: min(255, int(v * (1 + warmth))))
            b = b.point(lambda v: max(0, int(v * (1 - warmth))))
        if lift:
            f = lambda v: min(255, v + lift)
            r, g, b = r.point(f), g.point(f), b.point(f)
        img = Image.merge("RGB", (r, g, b))
    return img


_BAND: Image.Image | None = None


def _band() -> Image.Image:
    """一条柔和的竖向光带，全片缓慢横移。没有它，暗背景在手机上像「没加载出来」。"""
    global _BAND
    if _BAND is None:
        w = 460
        img = Image.new("RGBA", (w, H), (0, 0, 0, 0))
        px = img.load()
        for x in range(w):
            k = math.sin(math.pi * x / w) ** 2
            a = int(16 * k)
            for y in range(H):
                px[x, y] = (255, 250, 240, a)
        _BAND = img
    return _BAND


def ambient(canvas: Image.Image, t: float) -> Image.Image:
    """全局氛围层：光带横移 + 极轻的扫描线。确定性，任意帧可重现。"""
    band = _band()
    x = int((t * 46) % (W + band.width)) - band.width
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.alpha_composite(band, (x, 0))
    merged = Image.alpha_composite(canvas.convert("RGBA"), layer)
    return merged.convert("RGB")
