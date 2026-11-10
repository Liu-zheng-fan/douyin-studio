"""抖音数据：能拿到接口就自动取，拿不到就留人工录入的口子。

抖音的「完播率 / 2 秒跳出 / 流量来源」比 B 站细，但基本只在创作者中心里，
没有稳定公开接口。所以这里只有两件事：
1. `fetch`：如果开通了数据权限，走开放平台拉最近作品
2. `template`：打印一条可以直接粘进台账的模板，人工抄完再喂给 review
"""
from __future__ import annotations

import argparse
import json
import sys

import httpx

from .publish import API, _token, config

LIST_URL = f"{API}/api/douyin/v1/video/list/"

TEMPLATE = {
    "date": "2026-11-09",
    "video_id": "<发布后的作品 id>",
    "title": "<标题>",
    "metrics": {
        "plays": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "fans_gained": 0,
        "completion_rate": None,
        "avg_watch_seconds": None,
        "two_second_exit_rate": None,
    },
}


def fetch(days: int = 7) -> dict:
    cfg = config()
    missing = [k for k in ("client_key", "client_secret", "open_id") if not cfg.get(k)]
    if missing:
        return {"mode": "fetch", "available": False, "missing": missing,
                "next": "没有开放平台凭据。用 `template` 人工录入，或去 open.douyin.com 申请。"}
    token = _token(cfg)
    r = httpx.get(LIST_URL, params={"open_id": cfg["open_id"], "access_token": token,
                                    "cursor": 0, "count": 20}, timeout=30)
    body = r.json()
    items = ((body.get("data") or {}).get("list") or [])
    return {"mode": "fetch", "available": True, "count": len(items), "raw": items}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="抖音数据")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--days", type=int, default=7)
    sub.add_parser("template")
    a = ap.parse_args(argv)

    if a.cmd == "template":
        print(json.dumps(TEMPLATE, ensure_ascii=False, indent=2))
        return 0
    try:
        out = fetch(getattr(a, "days", 7))
        print(json.dumps({"ok": True, "data": out}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"code": "fetch_failed", "message": str(exc)}},
                         ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
