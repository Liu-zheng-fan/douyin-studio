"""拉片：把爆款拆成可复刻的结构，而不是抄内容。

方法论来自 guozhi-video-breakdown 的十字段框架（见 docs/autopsy.md）：
选题 / 标题封面 / 前3秒 / 结构 / 留存节点 / 金句 / 素材 / 剪辑 / 转化 / 复刻边界。

这里做的是「记录 + 聚合」：一条条填进去，攒够 6 条以上再看共性。
没有样本就生造内容，是这套系统之前最大的问题——这个模块就是补这个的。

    python -m ops.autopsy add --id d1 --engine pain --hook 冲突 \
        --duration 28 --cuts 14 --beats 5 --cta follow --note "开头甩结果"
    python -m ops.autopsy list
    python -m ops.autopsy report
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

STORE = Path(__file__).parent / "autopsy.jsonl"

ENGINES = ["pain", "identity", "contradiction", "result", "gap", "proof",
           "confession", "blame", "checklist"]
HOOKS = ["冲突", "悬念", "反常识", "共鸣", "数据震撼", "身份代入", "对比", "时间压迫"]
CTAS = ["follow", "comment", "save", "dm", "link", "none"]


def add(rec: dict) -> dict:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
    missing = [k for k in ("id", "hook", "duration", "cuts") if not rec.get(k)]
    if missing:
        raise SystemExit(f"缺少字段：{', '.join(missing)}")
    with STORE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"saved": True, "path": str(STORE), "count": len(load())}


def load() -> list[dict]:
    if not STORE.exists():
        return []
    out = []
    for line in STORE.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def report() -> dict:
    rows = load()
    if not rows:
        return {"ok": False, "error": "还没有样本。先 add 几条再 report。"}

    durs = [float(r["duration"]) for r in rows]
    cuts = [int(r["cuts"]) for r in rows]
    # 切镜间隔 = 时长 / 切数，越小越密
    intervals = [d / max(1, c) for d, c in zip(durs, cuts)]
    beats = [int(r.get("beats") or 0) for r in rows]
    # 留存节点密度：每 10 秒给几次刺激
    density = [b / d * 10 for b, d in zip(beats, durs) if d]

    hooks = Counter(r.get("hook") or "未标注" for r in rows)
    engines = Counter(r.get("engine") or "未标注" for r in rows)
    ctas = Counter(r.get("cta") or "none" for r in rows)

    def med(xs):
        return round(statistics.median(xs), 2) if xs else None

    verdict = []
    if med(durs) and med(durs) > 40:
        verdict.append("样本中位时长偏长，注意这不是你该学的时长")
    if med(intervals) and med(intervals) > 3.5:
        verdict.append(f"中位切镜间隔 {med(intervals)}s 偏慢，爆款通常在 1.5–2.5s")
    if med(intervals) and med(intervals) < 1.0:
        verdict.append("切镜过密，可能靠剪辑硬撑，注意内容是否撑得住")

    return {
        "ok": True,
        "samples": len(rows),
        "duration_median": med(durs),
        "cuts_median": med(cuts),
        "cut_interval_median": med(intervals),
        "retention_beats_per_10s": med(density),
        "hook_distribution": dict(hooks.most_common()),
        "engine_distribution": dict(engines.most_common()),
        "cta_distribution": dict(ctas.most_common()),
        "notes": verdict,
        "enough": len(rows) >= 6,
        "hint": "样本 <6 时结论不可信，继续攒。" if len(rows) < 6 else "可以按这个结构写一条了。",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="爆款拉片")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="记录一条样本")
    a.add_argument("--id", required=True)
    a.add_argument("--engine", choices=ENGINES, default="pain")
    a.add_argument("--hook", choices=HOOKS, default="冲突")
    a.add_argument("--duration", type=float, required=True, help="秒")
    a.add_argument("--cuts", type=int, required=True, help="全片切点数量")
    a.add_argument("--beats", type=int, default=0, help="留存节点数（每 8-12 秒一次）")
    a.add_argument("--cta", choices=CTAS, default="none")
    a.add_argument("--golden", default="", help="黄金 3 秒里最有效的一句/一帧")
    a.add_argument("--note", default="")

    sub.add_parser("list")
    sub.add_parser("report")
    args = ap.parse_args(argv)

    if args.cmd == "add":
        rec = {k: v for k, v in vars(args).items() if k != "cmd"}
        print(json.dumps({"ok": True, "data": add(rec)}, ensure_ascii=False))
    elif args.cmd == "list":
        rows = load()
        print(json.dumps({"ok": True, "data": {"count": len(rows), "rows": rows}},
                         ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"ok": True, "data": report()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
