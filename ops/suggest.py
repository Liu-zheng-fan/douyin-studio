"""从数据里给出「下一条改什么」的建议。

取自 dsh-video-pipeline 的数据复盘闭环：发布 → 回写 → 修正下一轮。
这里砍到最小：读台账和上一次的拒绝标签，算出一个唯一变量，不猜别的。

    python -m ops.suggest
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from .ledger import load

ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / "outbox"

# 拒绝标签 → 下一条该动的变量
TAG_TO_VARIABLE = {
    "topic": ("hook_type", "换开场类型，别换题材"),
    "script": ("script", "口播缩短到 18 字以内，删掉书面词"),
    "visual": ("field", "换背景 field，或给 art 镜头换 style"),
    "pace": ("drift", "提高 drift 到 0.02，或砍掉一镜"),
    "audio": ("voice", "换音色别名（anchor/warm）"),
    "product": ("topic", "换产品，旧产品进黑名单"),
}


def last_decision() -> dict | None:
    if not OUTBOX.exists():
        return None
    rows = []
    for d in sorted(OUTBOX.iterdir()):
        if not d.is_dir() or len(d.name) != 10:
            continue
        f = d / "decision.json"
        if f.exists():
            try:
                rec = json.loads(f.read_text(encoding="utf-8-sig"))
                rec["day"] = d.name
                rows.append(rec)
            except Exception:
                pass
    return rows[-1] if rows else None


def suggest() -> dict:
    rows = load()
    dec = last_decision()

    # 1) 被拒绝过：优先按标签改
    if dec and dec.get("status") == "reject" and dec.get("tags"):
        tag = dec["tags"][0]
        var, how = TAG_TO_VARIABLE.get(tag, ("script", "缩短口播"))
        return {
            "variable": var,
            "why": f"上一条因「{tag}」被拒（{dec.get('day')}）",
            "how": how,
            "confidence": "high",
        }

    # 2) 样本太少：别优化，先积累
    if len(rows) < 3:
        return {
            "variable": "hook_type",
            "why": f"台账只有 {len(rows)} 条，还看不出任何规律",
            "how": "先连发 3 条，只换开场类型，其他全不动",
            "confidence": "low",
        }

    # 3) 有数据：找差异最大的那一组
    groups: dict[str, list[float]] = {}
    for r in rows:
        key = str(r.get("hook_type") or "未标注")
        v = (r.get("metrics") or {}).get("completion_rate")
        if v is not None:
            groups.setdefault(key, []).append(float(v))
    scored = {k: statistics.median(v) for k, v in groups.items() if len(v) >= 2}

    if len(scored) >= 2:
        best = max(scored, key=scored.get)
        worst = min(scored, key=scored.get)
        return {
            "variable": "hook_type",
            "why": f"「{best}」完播 {scored[best]:.1%}，「{worst}」只有 {scored[worst]:.1%}",
            "how": f"下一条用「{best}」型开场，把「{worst}」先放一边",
            "confidence": "medium",
        }

    return {
        "variable": "hook_type",
        "why": "数据还不够分组（每组至少 2 条）",
        "how": "继续同一变量再跑 2 条",
        "confidence": "low",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="下一条改什么")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = suggest()
    print(json.dumps({"ok": True, "data": r}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
