"""单变量复盘：把台账按某个变量分组，比较中位数。

用法：
    python -m ops.review                    # 总览
    python -m ops.review --by hook_type     # 按开场类型比
    python -m ops.review --by duration --metric plays

结论只有在样本足够时才可信，脚本会自己提示「样本不足」。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict

from .ledger import load

METRICS = ("plays", "likes", "comments", "fans_gained", "completion_rate", "two_second_exit_rate")


def summarize(rows: list[dict], by: str, metric: str) -> dict:
    groups: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        key = r.get(by) or "未标注"
        val = (r.get("metrics") or {}).get(metric)
        if val is None:
            continue
        groups[str(key)].append(float(val))

    table = []
    for key, vals in sorted(groups.items(), key=lambda kv: -statistics.median(kv[1])):
        table.append({
            "value": key,
            "n": len(vals),
            "median": round(statistics.median(vals), 2),
            "mean": round(statistics.mean(vals), 2),
            "best": round(max(vals), 2),
        })

    note = None
    if sum(t["n"] for t in table) < 6:
        note = "样本不足（<6 条），先别下结论；继续按同一变量跑。"
    elif len(table) > 2:
        note = "组数偏多，控制在 2-3 组才能看清差异。"
    return {"by": by, "metric": metric, "groups": table, "note": note}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="单变量复盘")
    ap.add_argument("--by", default="hook_type", help="按哪个变量分组")
    ap.add_argument("--metric", default="plays", choices=METRICS)
    a = ap.parse_args(argv)

    rows = load()
    if not rows:
        print(json.dumps({"ok": False, "error": {
            "code": "empty", "message": "台账是空的，先发布并录入数据。"}}, ensure_ascii=False))
        return 1
    out = summarize(rows, a.by, a.metric)
    out["total_records"] = len(rows)
    print(json.dumps({"ok": True, "data": out}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
