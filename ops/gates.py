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

    return {
        "score": total,
        "max": MAX_SCORE,
        "pass": total >= PASS_SCORE,
        "threshold": PASS_SCORE,
        "detail": detail,
        "fails": [f"{d['item']}（{d['note']}）" if d["note"] else d["item"] for d in fails],
        "verdict": "pass" if total >= PASS_SCORE else "rewrite",
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
