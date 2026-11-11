"""脚本闸门：渲染之前的最后一道内容关。

灵感来自 douyin-script-pro 的 HOOK-X + 反平庸闸门 + 300 分评分。
区别：这里是**纯规则、可测试、离线**，不依赖任何模型。

为什么要在渲染前卡：
渲染一条 30 秒的片子要 2 分钟 + 几毛钱生图。脚本不过关，后面全是沉没成本。

    python -m ops.gates examples/script-04.json
    python -m ops.gates examples/script-04.json --strict   # 低于阈值直接 exit 1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# HOOK-X 八型
HOOKS = ["冲突", "悬念", "反常识", "共鸣", "数据震撼", "身份代入", "对比", "时间压迫"]

# 万能句黑名单：出现即扣分，因为它们可以塞进任何视频，说明没写具体东西
BANAL = [
    "在这个时代", "让我们一起", "你是否也曾", "相信很多人", "不得不说",
    "不得不说", "众所周知", "毋庸置疑", "毫无疑问", "大家都知道",
    "今天给大家", "话不多说", "废话不多说", "接下来", "首先我们",
]

PASS_SCORE = 200       # 240 是原版阈值，这里放宽，先让流程跑起来
MAX_SCORE = 300

# ---- 三道预检（取自 douyin-script-pro）
SAYING = ["你应该", "必须", "一定要", "相信我", "保证", "毫无疑问", "不容置疑"]
EMOTION_LABEL = ["很伤心", "很难过", "非常开心", "特别感动", "很生气", "超级激动"]
GROUP_HARM = ["女人就是", "男人都", "穷人就", "农村人都", "外地人都是", "老年人就是"]


def precheck(script: dict) -> list[dict]:
    """三道预检：复审生存 / 戏剧动作 / 潜台词。

    返回 [{gate, level, message}]，level=block|warn。
    """
    out: list[dict] = []
    text = " ".join(
        [script.get("title", ""), script.get("desc", ""), script.get("golden", "")]
        + [str(s.get("say") or "") for s in script.get("shots", [])]
        + [str(s.get("sub") or "") for s in script.get("shots", [])]
    )

    # 1) 复审生存：不能消费特定群体
    for w in GROUP_HARM:
        if w in text:
            out.append({"gate": "复审生存", "level": "block",
                        "message": f"出现群体贬损表述「{w}」，平台会限流，换成具体处境"})

    # 2) 戏剧动作：每场戏要能写成「想 X，但 Y」
    if not script.get("conflict"):
        out.append({"gate": "戏剧动作", "level": "warn",
                    "message": "没写 conflict。补一句「我想要 X，但 Y 挡着」，否则容易变成流水账"})

    # 3) 潜台词：情绪不能说破，不能写拍不出来的东西
    for w in EMOTION_LABEL:
        if w in text:
            out.append({"gate": "潜台词", "level": "warn",
                        "message": f"「{w}」把情绪说破了，让画面和动作承载它"})
    for w in SAYING:
        if w in text:
            out.append({"gate": "潜台词", "level": "warn",
                        "message": f"「{w}」是说教口吻，删掉或改成陈述"})

    return out


def _say_text(script: dict) -> str:
    return " ".join(str(s.get("say") or "") for s in script.get("shots", []))


def _sentences(script: dict) -> list[str]:
    out = []
    for s in script.get("shots", []):
        for part in re.split(r"[。！？!?]", str(s.get("say") or "")):
            part = part.strip("，,、 ")
            if part:
                out.append(part)
    return out


def check(script: dict) -> dict:
    """返回分数、逐项明细、以及不通过的原因。"""
    shots = script.get("shots") or []
    types = [s.get("type") for s in shots]
    says = [str(s.get("say") or "") for s in shots]
    sents = _sentences(script)
    text = _say_text(script)
    detail: list[dict] = []

    def add(name: str, score: int, max_score: int, note: str = ""):
        detail.append({"item": name, "score": score, "max": max_score, "note": note})

    # ---- 结构（80）
    has_hook = types and types[0] == "hook"
    add("首镜是 hook", 30 if has_hook else 0, 30, "" if has_hook else "第一镜必须是 hook")
    add("有收尾 cta", 20 if "cta" in types else 0, 20)
    add("有因果/对比镜", 30 if ({"line", "split"} & set(types)) else 0, 30,
        "" if ({"line", "split"} & set(types)) else "缺 line 或 split，容易变成并列事实")

    # ---- 开场（70）
    first_say = says[0] if says else ""
    first_text = str((shots[0].get("text") if shots else "") or "")
    add("开场口播 ≤18 字", 30 if len(first_say) <= 18 else 15, 30,
        f"当前 {len(first_say)} 字")
    add("开场有字幕", 20 if first_text and first_text != "[]" else 0, 20)
    hook_type = script.get("hook_type") or (shots[0].get("hook") if shots else None)
    add("声明钩子类型", 20 if hook_type in HOOKS else 0, 20,
        f"可选：{'/'.join(HOOKS)}")

    # ---- 节奏（70）
    n = len(shots)
    add("镜头数 5–9", 30 if 5 <= n <= 9 else 10, 30, f"当前 {n} 镜")
    long_sents = [s for s in sents if len(s) > 18]
    very_long = [s for s in sents if len(s) > 28]
    penalty = 10 * len(long_sents) + 10 * len(very_long)
    add("口播句 ≤18 字", max(0, 40 - penalty), 40,
        f"超长 {len(long_sents)} 句" + (f"（其中 {len(very_long)} 句严重超长）" if very_long else "")
        if long_sents else "")

    # ---- 具体性（40）
    has_number = "number" in types
    add("有数字镜", 20 if has_number else 0, 20)
    digits = len(re.findall(r"\d+", text))
    add("有具体数字", 20 if digits >= 2 else (10 if digits == 1 else 0), 20,
        f"正文出现 {digits} 处数字")

    # ---- 反平庸（40）
    hits = [w for w in BANAL if w in text]
    add("无万能句", 20 if not hits else 0, 20, f"命中：{'、'.join(hits)}" if hits else "")
    golden = script.get("golden") or ""
    add("有金句", 20 if len(golden) >= 6 else 0, 20,
        "" if golden else "script.json 里加 golden 字段，写那句会被截图的话")

    total = sum(d["score"] for d in detail)
    fails = [d for d in detail if d["score"] == 0]

    # 三道预检：block 直接判不过，warn 只提示
    pre = precheck(script)
    blocked = any(p["level"] == "block" for p in pre)
    total -= 15 * sum(1 for p in pre if p["level"] == "warn")

    return {
        "score": max(0, total),
        "max": MAX_SCORE,
        "pass": (total >= PASS_SCORE) and not blocked,
        "threshold": PASS_SCORE,
        "detail": detail,
        "precheck": pre,
        "fails": [f"{d['item']}（{d['note']}）" if d["note"] else d["item"] for d in fails]
                 + [p["message"] for p in pre if p["level"] == "block"],
        "verdict": "pass" if (total >= PASS_SCORE and not blocked) else "rewrite",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="脚本闸门：渲染前的内容自检")
    ap.add_argument("script", type=Path)
    ap.add_argument("--strict", action="store_true", help="不达标就返回非 0")
    a = ap.parse_args(argv)

    script = json.loads(a.script.read_text(encoding="utf-8-sig"))
    r = check(script)
    print(json.dumps({"ok": r["pass"], "data": r}, ensure_ascii=False, indent=2))
    if a.strict and not r["pass"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
