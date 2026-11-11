"""实验台账：每次发布记一行，供复盘做单变量对比。

为什么要有它：没有台账，改十个地方火了，你永远不知道该保留哪个。
台账的字段就是为了「一次只动一个变量」而设计的。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

LEDGER = Path(__file__).parent / "ledger.jsonl"

VARIABLES = ("hook_type", "duration", "cover_style", "bgm", "cta", "format")


def add(record: dict) -> dict:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    record.setdefault("date", time.strftime("%Y-%m-%d"))
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
    if "video_id" not in record and "title" not in record:
        raise SystemExit("至少要有 video_id 或 title")
    record.setdefault("metrics", {})
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"saved": True, "path": str(LEDGER), "variable": {k: record[k] for k in record if k in VARIABLES}}


def load() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="实验台账")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a1 = sub.add_parser("add", help="追加一条")
    a1.add_argument("--video-id", default="")
    a1.add_argument("--title", default="")
    a1.add_argument("--plays", type=int, default=0)
    a1.add_argument("--likes", type=int, default=0)
    a1.add_argument("--comments", type=int, default=0)
    a1.add_argument("--fans", type=int, default=0)
    a1.add_argument("--completion", type=float, default=None)
    a1.add_argument("--avg-watch", type=float, default=None)
    a1.add_argument("--exit2s", type=float, default=None)
    a1.add_argument("--hook-type", default="")
    a1.add_argument("--duration", type=float, default=None)
    a1.add_argument("--cover-style", default="")
    a1.add_argument("--notes", default="")

    sub.add_parser("list", help="列出全部")
    a3 = sub.add_parser("from-meta", help="从 dist 的 meta.json 建一条空记录")
    a3.add_argument("dist", type=Path)
    a = ap.parse_args(argv)

    if a.cmd == "add":
        rec = {
            "video_id": a.video_id, "title": a.title,
            "hook_type": a.hook_type, "duration": a.duration, "cover_style": a.cover_style,
            "metrics": {"plays": a.plays, "likes": a.likes, "comments": a.comments,
                        "fans_gained": a.fans, "completion_rate": a.completion,
                        "avg_watch_seconds": a.avg_watch, "two_second_exit_rate": a.exit2s},
            "notes": a.notes,
        }
        print(json.dumps({"ok": True, "data": add(rec)}, ensure_ascii=False))
    elif a.cmd == "list":
        rows = load()
        print(json.dumps({"ok": True, "data": {"count": len(rows), "rows": rows}}, ensure_ascii=False))
    else:
        meta = json.loads((a.dist / "meta.json").read_text(encoding="utf-8-sig"))
        rec = {"video_id": "", "title": meta.get("title"), "duration": meta.get("duration"),
               "hook_type": "", "cover_style": "", "metrics": {}, "notes": "待填数据"}
        print(json.dumps({"ok": True, "data": add(rec),
                          "next": f"`python -m ops.ledger add --title \"{meta.get('title')}\" --plays 0 ...`"},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
