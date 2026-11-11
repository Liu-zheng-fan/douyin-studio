"""结构化提示词：把「一句话」拼成能出好图的完整描述。

取自 dsh-directorx 的 video-prompt-builder 思路（9 参数 + 风格预设 + 分级模板），
砍到静帧需要的六个槽位：

    主体 · 动作 · 场景 · 构图 · 光线 · 画风

为什么需要：自由写的提示词每次质量飘。固定槽位之后，
「换个主体」不会把画风也换掉——这才是能复现的前提。
"""
from __future__ import annotations

# 画风预设：每个都写清「必须做 / 禁止做」，避免模型自由发挥
PRESETS = {
    "flat": {
        "name": "扁平插画",
        "prompt": "扁平插画风格，粗描边，纯色块，无渐变，干净简洁",
        "avoid": "照片写实、复杂纹理、渐变光晕",
    },
    "product": {
        "name": "产品摄影",
        "prompt": "产品摄影，柔光箱照明，浅灰无缝背景，金属与亚光质感清晰，四十五度俯视",
        "avoid": "卡通、手绘、夸张透视",
    },
    "cute": {
        "name": "Q 版卡通",
        "prompt": "Q 版卡通风格，圆润造型，明亮配色，柔和阴影",
        "avoid": "写实比例、暗色调",
    },
    "photo": {
        "name": "实拍感",
        "prompt": "实拍照片，自然光，浅景深，真实质感",
        "avoid": "插画、卡通、塑料感",
    },
    "ink": {
        "name": "黑白线稿",
        "prompt": "黑白线稿，网点阴影，高对比，留白多",
        "avoid": "彩色、渐变",
    },
    "3d": {
        "name": "3D 渲染",
        "prompt": "3D 渲染，黏土质感，柔和环境光，圆润倒角",
        "avoid": "平面插画、锐利边缘",
    },
}

# 老是出问题的东西，统一压住
ALWAYS_AVOID = "画面里的文字、水印、logo、多余的手指、扭曲的脸"

COMPOSITIONS = {
    "center": "主体居中，四周留白",
    "left": "主体偏左，右侧留白",
    "bottom": "主体在下半部分，上方留白给文字",
    "closeup": "特写，主体占满画面",
}


def build(subject: str, action: str | None = None, scene: str | None = None,
          style: str = "flat", composition: str = "center",
          light: str = "柔和光线", extra: str | None = None,
          vertical: bool = True) -> str:
    """按固定槽位拼提示词。槽位顺序固定，方便 diff。"""
    preset = PRESETS.get(style, PRESETS["flat"])
    parts = [
        preset["prompt"],
        subject.strip(),
        (action or "").strip(),
        (scene or "").strip(),
        COMPOSITIONS.get(composition, composition),
        light,
        "干净简洁",
        "竖版构图" if vertical else "",
        (extra or "").strip(),
    ]
    body = "，".join(p for p in parts if p)
    # 负面用「不要」写在最后：Seedream 没有独立 negative 字段，只能正向压制
    avoid = [preset["avoid"], ALWAYS_AVOID]
    return f"{body}。不要：{'；'.join(a for a in avoid if a)}"


def from_keyword(keyword: str, subject: str, **kw) -> str:
    """用风格库里的画风提示词作为 extra，再套槽位。"""
    try:
        from . import stylelib
        hits = stylelib.search(keyword)
        if hits:
            extra = hits[0].get("prompt") or hits[0].get("look") or ""
            kw.setdefault("extra", extra)
            kw.setdefault("style", "flat")
    except Exception:
        pass
    return build(subject, **kw)


def describe() -> dict:
    return {
        "presets": {k: v["name"] for k, v in PRESETS.items()},
        "compositions": list(COMPOSITIONS),
        "slots": ["主体", "动作", "场景", "构图", "光线", "画风"],
        "example": build("一只鲸鱼少女", action="双手端着不锈钢盆，盆里装满白米饭",
                         scene="纯色浅灰背景", style="flat"),
    }
