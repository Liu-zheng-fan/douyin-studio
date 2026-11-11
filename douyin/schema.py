"""script.json 的字段说明与校验。

新 Agent 最容易犯的错是"字段写错但程序不报错，最后渲染出一堆黑卡片"。
所以这里做两件事：说清楚有哪些字段，和**逐条指出哪里错了**。
"""
from __future__ import annotations

import json
from pathlib import Path

SHOT_FIELDS = {
    "hook": ["text", "sub", "fx", "size"],
    "number": ["label", "value", "to", "from", "prefix", "unit", "suffix",
               "note", "sub", "showFrom", "decimals"],
    "steps": ["items", "title"],
    "meter": ["value", "max", "label", "verdict"],
    "price": ["now", "old", "note", "unit"],
    "quote": ["text", "who", "size"],
    "split": ["a", "b", "tag"],
    "line": ["a", "b"],
    "reveal": ["name", "image", "labels", "placeholder"],
    "bullets": ["title", "items"],
    "art": ["image", "prompt", "prompt_spec", "gen_size", "style", "style_keyword",
            "focus", "caption_y", "kicker", "text", "sub"],
    "broll": ["video", "kicker", "text", "sub", "scrim"],
    "char": ["action", "characters", "height", "bottom", "caption_y", "kicker", "text", "sub", "band"],
    "cta": ["text", "sub", "user"],
}

TOP_FIELDS = {
    "name": "产物目录名，默认取文件名",
    "title": "标题（≤30 字），必填",
    "desc": "简介",
    "tags": "话题数组",
    "handle": "账号名，显示在封面和结尾",
    "cover_title": "封面大字，\\n 换行",
    "cover_kicker": "封面角标，如「第 1 天」",
    "cover_image": "封面用图路径",
    "ai_generated": "必须 true（抖音要求 AI 标识）",
    "hook_type": "八型之一，用于评分",
    "golden": "会被截图的那句金句",
    "conflict": "戏剧动作预检用：我想 X，但 Y 挡着",
    "cover_pill": "封面高亮胶囊，一行 ≤12 字",
    "fps": "默认 30",
    "voice": "narrator/anchor/warm/lively/passion",
    "rate": "语速，如 -4%",
    "pitch": "音高，如 -2Hz",
    "bgm": "auto | 情绪名 | none | 本地文件",
    "field": "背景：noise/dots/particles/flow",
    "transition": "crossfade/fade/wipe/push/zoom/none",
    "transition_dir": "left/right/up/down",
    "transition_dur": "转场秒数，默认 0.28",
    "drift": "整镜推近幅度，默认 0.012，0 关闭",
    "grade": "调色：{contrast, saturation, warmth, lift}",
    "subtitle_y": "字幕纵向位置，默认 1430",
    "characters": "形象目录，默认 characters/（里面一个角色一个文件夹）",
    "sfx": "是否配音效，默认 true",
    "strict_gates": "true 时脚本评分不足直接拒绝渲染",
    "shots": "镜头数组，必填",
}


def describe() -> str:
    from studio.shots import SHOTS

    lines = ["# script.json 字段", "", "## 顶层", ""]
    for k, v in TOP_FIELDS.items():
        lines.append(f"- `{k}`：{v}")

    lines += ["", "## 镜头（shots[]）", "", f"可用类型：{'、'.join(SHOTS)}", ""]
    for kind, fields in SHOT_FIELDS.items():
        lines.append(f"- `{kind}`：{', '.join('`'+f+'`' for f in fields)}")

    lines += [
        "", "## 最小可用示例", "", "```json",
        json.dumps({"title": "标题", "ai_generated": True, "shots": [
            {"type": "hook", "say": "第一句", "text": ["大字"]},
            {"type": "cta", "say": "最后一句", "text": ["关注"]}]}, ensure_ascii=False, indent=2),
        "```",
    ]
    return "\n".join(lines)


def validate(path: Path) -> dict:
    from studio.shots import SHOTS

    errors: list[dict] = []
    warnings: list[dict] = []

    def err(where: str, msg: str):
        errors.append({"where": where, "message": msg})

    def warn(where: str, msg: str):
        warnings.append({"where": where, "message": msg})

    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return {"ok": False, "errors": [{"where": str(path), "message": f"读不到文件：{exc}"}],
                "warnings": []}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {"ok": False, "errors": [{"where": f"第 {exc.lineno} 行",
                                         "message": f"JSON 语法错误：{exc.msg}"}],
                "warnings": []}

    # 顶层必填
    if not data.get("title"):
        err("title", "必填，观众第一眼看到的字")
    if data.get("ai_generated") is not True:
        err("ai_generated", "必须是 true——抖音要求 AI 生成内容显式标识")

    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        return {"ok": False, "errors": errors + [{"where": "shots", "message": "必须是非空数组"}],
                "warnings": warnings}

    for i, s in enumerate(shots):
        where = f"shots[{i}]"
        if not isinstance(s, dict):
            err(where, "必须是对象")
            continue
        kind = s.get("type")
        if kind not in SHOTS:
            err(f"{where}.type", f"未知镜头类型 {kind!r}，可用：{'、'.join(SHOTS)}")
            continue
        if not (s.get("say") or "").strip():
            warn(f"{where}.say", "没有口播文本，配音模式会失败（只适合 --silent）")
        else:
            # 按句号切分后再量长度——整段长不代表每句都长，TTS 是按句读的
            import re as _re
            sents = [x.strip() for x in _re.split(r"[。！？!?]", s["say"]) if x.strip()]
            long_ones = [x for x in sents if len(x) > 18]
            if long_ones:
                warn(f"{where}.say", f"有 {len(long_ones)} 句超过 18 字，最长 {max(len(x) for x in long_ones)} 字")

        if kind == "art" and not (s.get("image") or s.get("prompt")):
            err(where, "art 镜头需要 image 或 prompt 之一")
        if kind == "art" and s.get("image"):
            p = Path(s["image"])
            if not p.is_absolute():
                p = path.parent / p
            if not p.exists():
                warn(f"{where}.image", f"图片不存在：{s['image']}")
        if kind == "broll" and not s.get("video"):
            err(where, "broll 镜头需要 video")

        extra = set(s) - set(SHOT_FIELDS.get(kind, [])) - {"type", "say", "_asset_key"}
        if extra:
            warn(where, f"这些字段该镜头没用：{', '.join(sorted(extra))}")

    if shots[0].get("type") != "hook":
        warn("shots[0]", "第一镜不是 hook——开场没有钩子，完播率会掉")
    if not any(s.get("type") == "cta" for s in shots):
        warn("shots", "没有 cta 收尾")

    known_top = set(TOP_FIELDS)
    unknown = set(data) - known_top
    if unknown:
        warn("顶层", f"未知字段：{', '.join(sorted(unknown))}")

    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "shots": len(shots), "file": str(path)}
