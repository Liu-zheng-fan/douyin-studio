"""统一命令行入口。

之前是十三个 `python -m xxx`，分散在 studio / ops / douyin 三个包，
新接手的 Agent 根本不知道该敲哪个。现在只有一个：

    python -m douyin status          # 当前状态：能不能跑、有没有待审、台账几条
    python -m douyin doctor          # 环境自检
    python -m douyin schema          # script.json 的字段说明
    python -m douyin build <script>  # 出片
    python -m douyin qc <mp4>        # 质检
    python -m douyin pack <dist>     # 投递审批箱
    python -m douyin serve           # 起审批页

其余命令原样透传，参数和以前完全一样。
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 子命令 → (模块, 入口函数)。参数原样转发。
DELEGATE = {
    "build": ("studio.pipeline", "main"),
    "qc": ("studio.qc", "main"),
    "pack": ("studio.outbox", "main"),
    "serve": ("studio.outbox", "main"),
    "daily": ("ops.daily", "main"),
    "gates": ("ops.gates", "main"),
    "autopsy": ("ops.autopsy", "main"),
    "ledger": ("ops.ledger", "main"),
    "review": ("ops.review", "main"),
    "suggest": ("ops.suggest", "main"),
    "publish": ("douyin.publish", "main"),
    "stats": ("douyin.stats", "main"),
    "imggen": ("studio.imggen", "main"),
}

HELP = {
    "status": "当前状态：配置、今日进度、待审队列、台账",
    "doctor": "环境自检（字体/ffmpeg/TTS/生图）",
    "schema": "script.json 的字段说明",
    "build": "出片：python -m douyin build <script.json>",
    "qc": "机器质检：python -m douyin qc <mp4>",
    "pack": "投递审批箱：python -m douyin pack <dist>",
    "serve": "起审批页：python -m douyin serve --port 8787",
    "daily": "每日编排（幂等）：python -m douyin daily",
    "gates": "脚本评分：python -m douyin gates <script.json>",
    "autopsy": "拉片：python -m douyin autopsy report",
    "ledger": "台账：python -m douyin ledger add|list",
    "review": "单变量复盘：python -m douyin review --by hook_type",
    "suggest": "下一条改什么：python -m douyin suggest",
    "publish": "发布包：python -m douyin publish package <dist>",
    "stats": "抖音数据：python -m douyin stats template",
    "imggen": "生图：python -m douyin imggen --check",
}


def status() -> dict:
    """一眼看清当前能不能干活。新 Agent 第一条该敲的就是它。"""
    from . import schema

    info: dict = {"root": str(ROOT), "ok": True}

    # 生图配置
    try:
        from studio import imggen
        cfg = imggen.config()
        info["imggen"] = {"ready": bool(cfg.get("api_key")),
                          "model": cfg.get("model")}
    except Exception as exc:
        info["imggen"] = {"ready": False, "error": str(exc)}

    # 今日进度
    try:
        from ops import daily
        st = daily.load_state() or {"status": "not_run"}
        info["today"] = {"day": daily.today(), "status": st.get("status"),
                         "script": st.get("script")}
        info["pending"] = daily.pending_days(daily.today())
    except Exception as exc:
        info["today"] = {"error": str(exc)}
        info["pending"] = []

    # 台账
    try:
        from ops import ledger
        rows = ledger.load()
        info["ledger"] = {"count": len(rows)}
    except Exception:
        info["ledger"] = {"count": 0}

    # 最近一次决定
    try:
        from ops import suggest
        dec = suggest.last_decision()
        info["last_decision"] = {k: dec.get(k) for k in ("day", "status", "tags")} if dec else None
    except Exception:
        info["last_decision"] = None

    # 下一步建议
    if info["pending"]:
        info["next"] = f"先审 {info['pending'][0]}：python -m douyin serve"
    elif info["today"].get("status") == "packed":
        info["next"] = "今天已出片，等审批；可运行 python -m douyin suggest 看下一条改什么"
    else:
        info["next"] = "今天还没出片：写 script.json → python -m douyin gates → build"
    return info


def doctor() -> int:
    sys.path.insert(0, str(ROOT))
    mod = importlib.import_module("scripts.selfcheck")
    return mod.main()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="douyin", description="抖音竖屏短视频生产线",
        epilog="子命令列表：" + "、".join(HELP),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", help="见下方子命令")
    ap.add_argument("args", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)

    if not a.cmd or a.cmd in ("-h", "--help"):
        ap.print_help()
        print()
        for k, v in HELP.items():
            print(f"  {k:9} {v}")
        return 0

    sys.path.insert(0, str(ROOT))

    if a.cmd == "status":
        print(json.dumps({"ok": True, "data": status()}, ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "doctor":
        return doctor()
    if a.cmd == "schema":
        from . import schema
        if a.args and a.args[0] == "--check":
            if len(a.args) < 2:
                print("用法：python -m douyin schema --check <script.json>")
                return 2
            res = schema.validate(Path(a.args[1]))
            print(json.dumps(res, ensure_ascii=False, indent=2))
            return 0 if res["ok"] else 1
        print(schema.describe())
        return 0

    if a.cmd in DELEGATE:
        mod_name, fn_name = DELEGATE[a.cmd]
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
        # pack/serve 是 outbox 的两个子命令，补上
        args = list(a.args)
        if a.cmd in ("pack", "serve"):
            args = [a.cmd] + args
        return fn(args)

    print(f"未知命令：{a.cmd}\n用 `python -m douyin --help` 看可用命令。", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
