"""形象库：把「透明背景的角色图」组织成可按动作调用的资产。

用法约定（很重要，写错就不会被识别）：

    characters/
      xiaojingyu/            ← 一个角色一个文件夹
        端盆.png             ← 文件名就是动作名
        挥手.png
        思考-歪头.png
        生气.png

图片必须是**透明背景 PNG**。渲染时按高度缩放、贴底居中、加一层柔影。

为什么用文件名当动作名：不需要额外的索引文件，
你往文件夹里丢一张 `端着盆.png`，脚本里写 `"action": "端盆"` 就能用。
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "characters"

_STRIP = re.compile(r"[\s_\-—]+")


def _norm(s: str) -> str:
    return _STRIP.sub("", s.lower())


def resolve_dir(name: str | Path | None = None) -> Path:
    if name is None:
        return DEFAULT_DIR
    p = Path(name)
    return p if p.is_absolute() else ROOT / p


def actions(dirname: str | Path | None = None) -> dict[str, Path]:
    """返回 {动作名: 图片路径}。动作名取文件名（去掉扩展名）。"""
    base = resolve_dir(dirname)
    out: dict[str, Path] = {}
    if not base.exists():
        return out
    for p in sorted(base.rglob("*.png")):
        out[p.stem.strip()] = p
    return out


def pick(action: str, dirname: str | Path | None = None) -> Path | None:
    """按动作名找图：精确 → 互相包含 → 字面重合度最高。"""
    pool = actions(dirname)
    if not pool:
        return None
    if not action:
        return None
    want = _norm(action)

    for name, path in pool.items():
        if _norm(name) == want:
            return path

    for name, path in pool.items():
        n = _norm(name)
        if want in n or n in want:
            return path

    best, best_score = None, 0.0
    wset = set(want)
    for name, path in pool.items():
        n = _norm(name)
        score = len(wset & set(n)) / max(1, len(wset | set(n)))
        if score > best_score:
            best, best_score = path, score
    return best if best_score >= 0.34 else None


def describe(dirname: str | Path | None = None) -> dict:
    pool = actions(dirname)
    return {
        "dir": str(resolve_dir(dirname)),
        "exists": resolve_dir(dirname).exists(),
        "count": len(pool),
        "actions": list(pool)[:40],
        "hint": ("放透明背景 PNG 进去，文件名就是动作名，脚本里写 \"action\": \"端盆\""
                 if pool else "目录是空的：把透明 PNG 放进去，文件名当动作名"),
    }


def place(frame: Image.Image, path: Path, t: float = 0.0,
          height_ratio: float = 0.56, bottom: int = 0,
          bob: float = 3.0, shadow: bool = True, sway: float = 2.0) -> Image.Image:
    """把角色图贴到画面底部居中，带轻微浮动 + 摇摆 + 呼吸缩放 + 柔影。

    只做上下浮动会像贴纸；加一点摇摆和呼吸，才像"站在那儿"。
    """
    sprite = Image.open(path).convert("RGBA")
    target_h = max(1, int(frame.height * height_ratio))
    scale = target_h / sprite.height
    breathe = 1.0 + 0.012 * math_sin(t * 2.1)
    sprite = sprite.resize((max(1, int(sprite.width * scale * breathe)), int(target_h * breathe)),
                           Image.LANCZOS)
    if sway:
        sprite = sprite.rotate(math_sin(t * 1.3) * sway, resample=Image.BICUBIC,
                               expand=True, fillcolor=(0, 0, 0, 0))

    dy = int(math_sin(t * 1.7) * bob)
    x = (frame.width - sprite.width) // 2
    y = frame.height - sprite.height - bottom + dy

    base = frame.convert("RGBA")
    if shadow:
        sh = Image.new("L", (sprite.width + 120, 90), 0)
        ImageDraw.Draw(sh).ellipse([60, 12, sprite.width + 60, 78], fill=105)
        sh = sh.filter(ImageFilter.GaussianBlur(22))
        shadow_img = Image.new("RGBA", sh.size, (0, 0, 0, 0))
        shadow_img.putalpha(sh)
        base.alpha_composite(shadow_img, (x - 60, min(frame.height - 60,
                                                      y + sprite.height - 46)))
    base.alpha_composite(sprite, (x, y))
    return base.convert("RGB")


def math_sin(x: float) -> float:
    import math
    return math.sin(x)
