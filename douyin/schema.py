"""script.json 校验：从 studio/specs.json 的契约生成，不再手抄字段名。

设计照 brewreel 的 validate.mjs：**一镜一契约**，每条错误都带「怎么改」。
之前的版本只有字段名清单，0 处长度/枚举检查，超长靠 shots.py 里 `[:8]` 静默截断——
数据被吃掉还不报错，这是最坏的一种 bug。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS_PATH = ROOT / "studio" / "specs.json"

_CACHE: dict | None = None


def load_specs() -> dict:
    global _CACHE
    if _CACHE is None:
        raw = json.loads(SPECS_PATH.read_text(encoding="utf-8-sig"))
        raw.pop("_readme", None)
        _CACHE = raw
    return _CACHE


def _fields(shot: str) -> list[str]:
    spec = load_specs().get(shot) or {}
    return list(spec.get("params", {}))


# 兼容旧引用（测试与 CLI 都在用）
SHOT_FIELDS: dict[str, list[str]] = {}


def _refresh() -> None:
    SHOT_FIELDS.clear()
    for k in load_specs():
        SHOT_FIELDS[k] = _fields(k)


_refresh()

TOP_FIELDS = {
    "name": "产物目录名，默认取文件名",
    "title": "标题（≤30 字），必填",
    "desc": "简介",
    "tags": "话题数组",
    "handle": "账号名，显示在封面和结尾",
    "cover_title": "封面标题，用 \\n 手动断行，最多两行",
    "cover_kicker": "封面左上角小字",
    "cover_pill": "封面高亮胶囊，一行 ≤12 字",
    "cover_image": "封面底图路径（可选）",
    "ai_generated": "必须是 true——抖音要求 AI 生成内容显式标识",
    "hook_type": "钩子类型（反常识/数字/对比/悬念/共鸣/利益/身份）",
    "golden": "会被截图的那句金句",
    "conflict": "戏剧动作预检用：我想 X，但 Y 挡着",
    "fps": "帧率，默认 30",
    "voice": "音色：narrator / moe / warm / lively / anchor",
    "rate": "语速，如 -4%",
    "pitch": "音高，如 +10Hz",
    "bgm": "配乐情绪：calm / quirky / warm / tense / hype",
    "bg_video": "全片铺底素材（会模糊+压暗）",
    "bg_blur": "铺底模糊半径，默认 12",
    "bg_dim": "铺底压暗比例 0~1",
    "field": "程序化背景：noise / dots / particles / flow",
    "form": "在场感强度 0~1",
    "transition": "转场：crossfade / fade / wipe / push / zoom",
    "transition_dir": "方向：left / right / up / down",
    "transition_dur": "转场时长秒，默认 0.28",
    "subtitle_y": "字幕纵向位置，默认 1430",
    "characters": "形象目录，默认 characters/（里面一个角色一个文件夹）",
    "theme": "dark / light 两套配色",
    "backdrop": "底色变体，默认 dark",
    "post": "后期：{bloom, grain, vignette}，0~1。颗粒是帧间差异的来源",
    "grade": "调色：contrast/saturation/warmth/lift",
    "shots": "镜头数组，必填",
}


def _type_ok(value, t: str) -> bool:
    if t == "str":
        return isinstance(value, str)
    if t == "list":
        return isinstance(value, list)
    if t == "dict":
        return isinstance(value, dict)
    if t == "num":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "bool":
        return isinstance(value, bool)
    return True


def _check_value(value, rule: dict, where: str, errors: list) -> None:
    """单值校验：类型 → 枚举 → 范围/长度。每条错误都带 fix。"""
    t = rule.get("type")
    if t and not _type_ok(value, t):
        want = {"str": "文字", "list": "数组", "dict": "对象", "num": "数字",
                "int": "整数", "bool": "true/false"}.get(t, t)
        errors.append({"where": where, "message": f"应该是{want}，现在是 {type(value).__name__}",
                       "fix": f"把 {where} 改成{want}"})
        return

    if t == "enum" and value not in rule.get("values", []):
        errors.append({"where": where, "message": f"只能用：{'、'.join(rule['values'])}",
                       "fix": f"从 [{', '.join(rule['values'])}] 里挑一个"})
        return

    if isinstance(value, str):
        limit = rule.get("maxLen")
        if limit and len(value) > limit:
            errors.append({"where": where,
                           "message": f"{len(value)} 字，超过上限 {limit}",
                           "fix": f"删到 {limit} 字以内，或拆成两镜"})
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        lo, hi = rule.get("min"), rule.get("max")
        if lo is not None and value < lo:
            errors.append({"where": where, "message": f"不能小于 {lo}", "fix": f"改成 ≥{lo}"})
        if hi is not None and value > hi:
            errors.append({"where": where, "message": f"不能大于 {hi}", "fix": f"改成 ≤{hi}"})
    if isinstance(value, list):
        n = len(value)
        if rule.get("minItems") and n < rule["minItems"]:
            errors.append({"where": where, "message": f"至少 {rule['minItems']} 项，现在 {n}",
                           "fix": "补到下限，不够就换一个镜头类型"})
        if rule.get("maxItems") and n > rule["maxItems"]:
            errors.append({"where": where, "message": f"最多 {rule['maxItems']} 项，现在 {n}",
                           "fix": "砍掉多余的，或拆成两镜"})


def validate(path: Path | str) -> dict:
    path = Path(path)
    errors: list[dict] = []
    warnings: list[dict] = []

    def err(where, message, fix=""):
        errors.append({"where": where, "message": message, "fix": fix})

    def warn(where, message, fix=""):
        warnings.append({"where": where, "message": message, "fix": fix})

    try:
        raw = path.read_text(encoding="utf-8-sig")
        script = json.loads(raw)
    except FileNotFoundError:
        return {"ok": False, "errors": [{"where": "file", "message": "脚本不存在", "fix": "检查路径"}],
                "warnings": [], "shots": 0}
    except json.JSONDecodeError as exc:
        return {"ok": False,
                "errors": [{"where": "json", "message": f"JSON 解析失败：{exc.msg}（第 {exc.lineno} 行）",
                            "fix": "常见原因：中文引号、多余逗号、BOM"}],
                "warnings": [], "shots": 0}

    for k in script:
        if k not in TOP_FIELDS:
            warn(f"顶层.{k}", f"未知字段 {k}，不会生效", "删掉或查 python -m douyin schema")

    if not str(script.get("title") or "").strip():
        err("title", "必填，观众第一眼看到的字", "写一句 ≤30 字、能被截图的标题")
    elif len(script["title"]) > 30:
        warn("title", f"{len(script['title'])} 字，抖音标题建议 ≤30 字", "删到 30 字内")

    if script.get("ai_generated") is not True:
        err("ai_generated", "必须是 true——抖音要求 AI 生成内容显式标识",
            "顶层加 \"ai_generated\": true")

    shots = script.get("shots") or []
    if not shots:
        err("shots", "至少要有一个镜头", "至少写 3 镜：hook / 中段 / cta")

    specs = load_specs()
    for i, s in enumerate(shots):
        where = f"shots[{i}]"
        if not isinstance(s, dict):
            err(where, "每个镜头必须是对象", "写成 { \"type\": \"hook\", ... }")
            continue
        kind = s.get("type")
        if kind not in specs:
            err(f"{where}.type", f"未知镜头类型 {kind!r}，可用：{'、'.join(specs)}",
                "从列出的类型里选一个")
            continue

        spec = specs[kind]
        params = spec.get("params", {})
        for name, rule in params.items():
            if name not in s:
                if rule.get("required"):
                    err(f"{where}.{name}", f"{kind} 镜头必填 {name}", f"补上 {name}")
                continue
            _check_value(s[name], rule, f"{where}.{name}", errors)

        for name in s:
            if name in params or name.startswith("_") or name in ("type", "say", "say_dur"):
                continue
            warn(f"{where}.{name}", f"{kind} 镜头没有 {name} 这个参数，不会生效", "删掉或改对名字")

        # items 里每个对象的字段（steps / cards / layers）
        item_fields = spec.get("itemFields")
        if item_fields and isinstance(s.get("items"), list):
            for j, it in enumerate(s["items"]):
                if not isinstance(it, dict):
                    continue
                for name, rule in item_fields.items():
                    if name not in it:
                        if rule.get("required"):
                            err(f"{where}.items[{j}].{name}", f"必填 {name}", f"补上 {name}")
                        continue
                    _check_value(it[name], rule, f"{where}.items[{j}].{name}", errors)

        if not (s.get("say") or "").strip():
            warn(f"{where}.say", "没有口播文本，配音模式会失败（只适合 --silent）", "补一句 ≤18 字的口播")
        else:
            sents = [x.strip() for x in re.split(r"[。！？!?]", s["say"]) if x.strip()]
            long_ones = [x for x in sents if len(x) > 18]
            if long_ones:
                warn(f"{where}.say", f"有 {len(long_ones)} 句超过 18 字，最长 {max(len(x) for x in long_ones)} 字",
                     "按句号拆开，一镜一句话")

    if shots and (shots[0].get("type") != "hook"):
        warn("shots[0]", "第一镜不是 hook，开场会平", "把第一镜换成 hook，0.5 秒内给冲突")
    if shots and (shots[-1].get("type") != "cta"):
        warn("shots[-1]", "最后一镜不是 cta，结尾没有落点", "结尾加 cta")

    return {"ok": not errors, "errors": errors, "warnings": warnings, "shots": len(shots)}


def describe() -> str:
    """从同一份契约生成字段文档，避免 SKILL/schema/模板三处手抄漂移。"""
    specs = load_specs()
    lines = ["# script.json 字段", "", "## 顶层", ""]
    for k, v in TOP_FIELDS.items():
        lines.append(f"- `{k}`：{v}")
    lines += ["", "## 镜头（按契约生成）", ""]
    for kind, spec in specs.items():
        cap = spec.get("caption", "optional")
        lines.append(f"### `{kind}`（字幕：{cap}）")
        for name, rule in spec.get("params", {}).items():
            bits = [rule.get("type", "")]
            if rule.get("required"):
                bits.append("必填")
            if rule.get("maxLen"):
                bits.append(f"≤{rule['maxLen']} 字")
            if rule.get("values"):
                bits.append("可选：" + "/".join(rule["values"]))
            if rule.get("min") is not None or rule.get("max") is not None:
                bits.append(f"{rule.get('min', '')}~{rule.get('max', '')}")
            if rule.get("minItems") or rule.get("maxItems"):
                bits.append(f"{rule.get('minItems', '')}~{rule.get('maxItems', '')} 项")
            lines.append(f"- `{name}`：{'，'.join(b for b in bits if b)}")
        if spec.get("itemFields"):
            for name, rule in spec["itemFields"].items():
                limit = f"，≤{rule['maxLen']} 字" if rule.get("maxLen") else ""
                req = "，必填" if rule.get("required") else ""
                lines.append(f"  - items[].{name}{req}{limit}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="douyin schema", description="字段说明与校验")
    ap.add_argument("--check", metavar="SCRIPT", help="校验一个 script.json")
    a = ap.parse_args(argv)
    if a.check:
        r = validate(a.check)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    print(describe())
    return 0
