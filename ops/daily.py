"""每日编排：一次跑完「渲染 → 质检 → 投递审批」。

设计成幂等：同一天重复触发只会跑一次，避免开机补跑和手动触发撞车。
判断层（选题、写脚本）不在这里——那是模型在会话里做的事。
这个脚本只负责确定性的那一段。

    python -m ops.daily                 # 今天跑一次，跑过就跳过
    python -m ops.daily --force         # 强制重跑
    python -m ops.daily --script x.json # 指定用哪份脚本
    python -m ops.daily --status        # 只看状态
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "ops" / "state"
QUEUE = ROOT / "ops" / "today.json"


def today() -> str:
    return time.strftime("%Y-%m-%d")


def state_path(day: str | None = None) -> Path:
    return STATE / f"{day or today()}.json"


def load_state(day: str | None = None) -> dict | None:
    p = state_path(day)
    if p.exists():
        try:
            # utf-8-sig：PowerShell 写出来的 JSON 常带 BOM
            return json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            return None
    return None


def save_state(data: dict, day: str | None = None) -> Path:
    STATE.mkdir(parents=True, exist_ok=True)
    p = state_path(day)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def resolve_script(explicit: Path | None) -> tuple[Path, str]:
    """优先级：命令行 > ops/today.json 的 script 字段 > 默认示例。"""
    if explicit:
        return explicit, "cli"
    if QUEUE.exists():
        try:
            q = json.loads(QUEUE.read_text(encoding="utf-8-sig"))
            if q.get("script"):
                p = Path(q["script"])
                if not p.is_absolute():
                    p = ROOT / p
                return p, "queue"
        except Exception:
            pass
    return ROOT / "examples" / "script-03-gen.json", "default"


def pending_days(today_str: str) -> list[str]:
    """今天之前还没审批的日期。有一条没审，就不要生产新的。"""
    out: list[str] = []
    box = ROOT / "outbox"
    if not box.exists():
        return out
    for d in sorted(box.iterdir()):
        if not d.is_dir() or len(d.name) != 10:   # 跳过 -rerun- 备份目录
            continue
        if d.name >= today_str:
            continue
        dec = d / "decision.json"
        status = None
        if dec.exists():
            try:
                status = json.loads(dec.read_text(encoding="utf-8-sig")).get("status")
            except Exception:
                status = None
        if status == "pending":
            out.append(d.name)
    return out


def run(force: bool = False, script: Path | None = None, day: str | None = None) -> dict:
    day = day or today()

    waiting = pending_days(day)
    if waiting and not force:
        return {
            "skipped": True,
            "reason": "还有片子没审批，先处理这些再做新的",
            "pending": waiting,
            "hint": f"打开 outbox/<日期>/review.html 看片，或直接回一句「过」/「拒：理由」",
        }

    prev = load_state(day)
    if prev and prev.get("status") == "packed" and not force:
        return {"skipped": True, "reason": "今天已经跑过", "state": prev}

    if prev and prev.get("status") == "packed" and force:
        # 重跑时把旧的审批包挪开，避免覆盖掉已经做出的决定
        old = ROOT / "outbox" / day
        if old.exists():
            backup = old.with_name(f"{day}-rerun-{time.strftime('%H%M%S')}")
            old.rename(backup)

    script_path, source = resolve_script(script)
    if not script_path.exists():
        rec = {"day": day, "status": "failed", "error": f"脚本不存在：{script_path}",
               "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_state(rec, day)
        return {"ok": False, "state": rec}

    from studio import outbox, pipeline, qc

    try:
        mp4 = pipeline.build(script_path)
    except SystemExit as exc:
        rec = {"day": day, "status": "failed", "stage": "render",
               "error": str(exc), "script": str(script_path),
               "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_state(rec, day)
        return {"ok": False, "state": rec}

    check = qc.inspect(mp4)
    if not check["ok"]:
        rec = {"day": day, "status": "blocked", "stage": "qc", "qc": check,
               "script": str(script_path), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_state(rec, day)
        return {"ok": False, "state": rec}

    packed = outbox.pack(mp4.parent, day=day)
    rec = {
        "day": day, "status": "packed" if packed.get("packed") else "failed",
        "stage": "outbox", "script": script_path.name, "script_source": source,
        "video": str(mp4), "qc": check["verdict"],
        "outbox": packed.get("dir"), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    save_state(rec, day)
    return {"ok": rec["status"] == "packed", "state": rec}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="每日编排：渲染→质检→投递审批")
    ap.add_argument("--force", action="store_true", help="今天跑过也重跑")
    ap.add_argument("--script", type=Path, default=None)
    ap.add_argument("--day", default=None, help="指定日期（默认今天）")
    ap.add_argument("--status", action="store_true", help="只看今天状态")
    a = ap.parse_args(argv)

    if a.status:
        st = load_state(a.day) or {"status": "not_run"}
        print(json.dumps({"ok": True, "day": a.day or today(), "state": st},
                         ensure_ascii=False, indent=2))
        return 0

    out = run(a.force, a.script, a.day)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") or out.get("skipped") else 1


if __name__ == "__main__":
    sys.exit(main())
