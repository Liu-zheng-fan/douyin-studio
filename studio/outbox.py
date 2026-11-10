"""审批箱：把成片推到「你早上看一眼，点通过或拒绝」的那个界面。

设计约束（来自真实使用场景）：
- 早上 10 秒耐心 → 一屏看完视频、封面、文案、质检
- 只有两个动作 → 通过 / 拒绝，拒绝必须带理由标签
- 不需要装任何东西 → 一个本地网页，手机连同一 WiFi 就能开
- 决定要落盘 → decision.json，后续流程读它

命令：
    python -m studio.outbox pack dist/demo-03-gen
    python -m studio.outbox serve --port 8787
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import qc

ROOT = Path(__file__).resolve().parent.parent
OUTBOX = ROOT / "outbox"

# 拒绝理由 → 次日该改什么。没有这张表，拒绝就只是一次情绪。
REJECT_TAGS = {
    "topic": ("选题不喜欢", "换题材；次日优先从「产品/幕后/观点」里配额最低的一类挑"),
    "script": ("文案不像人", "缩短句子、去掉书面词、加一个具体细节；口播每句 ≤ 18 字"),
    "visual": ("画面丑", "换构图/换风格处理；生图提示词加材质与光线限定"),
    "pace": ("太慢", "砍掉一个镜头；总时长压到 25 秒内；开场提前到 0.3 秒"),
    "audio": ("音频难听", "换音色别名（anchor/warm）；BGM 降一档音量或换 mood"),
    "product": ("不想发这个产品", "从选题池移除该产品，记入黑名单"),
}


def _day_dir(day: str | None) -> Path:
    return OUTBOX / (day or time.strftime("%Y-%m-%d"))


def pack(dist: Path, day: str | None = None, note: str = "") -> dict:
    meta_path = dist / "meta.json"
    if not meta_path.exists():
        raise SystemExit(f"{dist} 里没有 meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    video = Path(meta["video"])
    if not video.is_absolute():
        video = dist / video.name

    result = qc.inspect(video)
    if not result["ok"]:
        # 质检不过就不进审批队列，避免占用你的注意力
        return {"packed": False, "reason": "qc_blocked", "qc": result}

    d = _day_dir(day)
    d.mkdir(parents=True, exist_ok=True)
    for src, name in ((video, "video.mp4"),
                      (Path(meta["cover_3x4"]), "cover.png"),
                      (dist / "script.json", "script.json")):
        if src.exists():
            shutil.copy2(src, d / name)
    if not (d / "script.json").exists():
        # 脚本可能在别处，不影响审批
        (d / "script.json").write_text("{}", encoding="utf-8")

    review = {
        "day": d.name,
        "title": meta.get("title"),
        "desc": meta.get("desc"),
        "tags": meta.get("tags", []),
        "duration": meta.get("duration"),
        "voice": meta.get("voice"),
        "bgm": (meta.get("bgm") or {}).get("mood"),
        "qc": {"verdict": result["verdict"], "metrics": result["metrics"],
               "issues": result["issues"]},
        "status": "pending",
        "note": note,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (d / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "review.html").write_text(_render_page(review), encoding="utf-8")
    if not (d / "decision.json").exists():
        (d / "decision.json").write_text(json.dumps({"status": "pending"}, ensure_ascii=False), encoding="utf-8")
    return {"packed": True, "dir": str(d), "qc": result["verdict"], "url": f"/{d.name}/"}


def _render_page(review: dict) -> str:
    tags = "".join(
        f'<button class="tag" data-tag="{k}">{html.escape(v[0])}</button>'
        for k, v in REJECT_TAGS.items()
    )
    issues = review["qc"]["issues"]
    issue_html = "".join(
        f'<li class="{i["level"]}">[{i["level"]}] {html.escape(i["message"])}</li>' for i in issues
    ) or "<li class='ok'>质检无异常</li>"
    m = review["qc"]["metrics"]

    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>审批 · {html.escape(str(review['day']))}</title>
<style>
 body{{background:#0d0e11;color:#eee;font:15px/1.6 -apple-system,"Segoe UI",sans-serif;margin:0;padding:16px}}
 .wrap{{max-width:520px;margin:0 auto}}
 video{{width:100%;border-radius:14px;display:block;background:#000}}
 h1{{font-size:18px;margin:14px 0 6px}} .meta{{color:#8d939c;font-size:13px}}
 .box{{background:#16181d;border-radius:12px;padding:12px;margin:12px 0}}
 ul{{margin:0;padding-left:18px}} li{{margin:2px 0;font-size:13px}}
 li.warn{{color:#ffd166}} li.block{{color:#ff6b6b}} li.ok{{color:#7bd88f}}
 .tag{{background:#22252b;color:#ddd;border:1px solid #333;border-radius:999px;
       padding:8px 12px;margin:4px 4px 0 0;font-size:13px}}
 .tag.on{{background:#ffd166;color:#151515;border-color:#ffd166}}
 .row{{display:flex;gap:10px;margin-top:14px}}
 button.main{{flex:1;padding:16px;border:0;border-radius:12px;font-size:16px;font-weight:600}}
 #ok{{background:#7bd88f;color:#0b1a10}} #no{{background:#ff6b6b;color:#2a0b0b}}
 #st{{margin-top:12px;font-size:14px;color:#8d939c}}
</style></head><body><div class="wrap">
<video src="video.mp4" controls playsinline poster="cover.png"></video>
<h1>{html.escape(str(review['title']))}</h1>
<div class="meta">{review['duration']}s · {review['voice'] or ''} · BGM {review['bgm'] or '无'}</div>
<div class="box"><b>文案</b><div class="meta">{html.escape(str(review.get('desc') or ''))}</div>
<div class="meta">#{' #'.join(review.get('tags') or [])}</div></div>
<div class="box"><b>机器质检 · {review['qc']['verdict']}</b>
 <div class="meta">黑帧 {m.get('black_ratio')} · 开场变化 {m.get('open_motion')} · 响度 {m.get('lufs')} LUFS</div>
 <ul>{issue_html}</ul></div>
<div class="box"><b>拒绝理由（选了才能拒绝）</b><div>{tags}</div></div>
<div class="row"><button class="main" id="no">拒绝</button><button class="main" id="ok">通过</button></div>
<div id="st">等待决定</div>
<script>
let picked=null;
document.querySelectorAll('.tag').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('.tag').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); picked=b.dataset.tag;
}});
async function send(decision){{
  const r=await fetch('/decide',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{day:'{review['day']}',decision,tags:picked?[picked]:[],note:''}})}});
  const j=await r.json();
  document.getElementById('st').textContent=j.ok?('已记录：'+decision):('失败：'+j.error);
}}
document.getElementById('ok').onclick=()=>send('approve');
document.getElementById('no').onclick=()=>{{ if(!picked){{alert('先选一个拒绝理由');return;}} send('reject'); }};
</script></div></body></html>"""


def _decide(payload: dict) -> dict:
    day = payload.get("day")
    decision = payload.get("decision")
    if decision not in ("approve", "reject"):
        return {"ok": False, "error": "decision 必须是 approve 或 reject"}
    d = _day_dir(day)
    if not d.exists():
        return {"ok": False, "error": f"没有这一天的审批包：{day}"}
    rec = {
        "status": decision,
        "tags": payload.get("tags") or [],
        "note": payload.get("note") or "",
        "decided_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (d / "decision.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "decision": decision, "next": _next_step(rec)}


def _next_step(rec: dict) -> str:
    if rec["status"] == "approve":
        return "发布：python -m douyin.publish package <dist>，或接官方接口自动发。"
    tags = [REJECT_TAGS[t][0] for t in rec["tags"] if t in REJECT_TAGS]
    fixes = [REJECT_TAGS[t][1] for t in rec["tags"] if t in REJECT_TAGS]
    return f"已拒绝（{', '.join(tags) or '未标注'}）。次日调整：{'；'.join(fixes) or '记录原因即可'}。"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].strip("/")
        if not path:
            return self._index()
        target = OUTBOX / path
        if target.is_dir():
            page = target / "review.html"
            if page.exists():
                return self._send(200, page.read_bytes())
        if target.is_file() and target.resolve().is_relative_to(OUTBOX.resolve()):
            ctype = {"mp4": "video/mp4", "png": "image/png", "json": "application/json"}.get(
                target.suffix[1:], "application/octet-stream")
            return self._send(200, target.read_bytes(), ctype)
        self._send(404, b"not found")

    def _index(self):
        rows = []
        for d in sorted(OUTBOX.glob("*"), reverse=True):
            if not d.is_dir():
                continue
            dec = d / "decision.json"
            status = json.loads(dec.read_text(encoding="utf-8")).get("status") if dec.exists() else "pending"
            color = {"approve": "#7bd88f", "reject": "#ff6b6b"}.get(status, "#ffd166")
            rows.append(f'<li><a href="/{d.name}/" style="color:#eee">{d.name}</a> '
                        f'<span style="color:{color}">{status}</span></li>')
        body = ("<h2>审批箱</h2><ul>" + ("".join(rows) or "<li>还没有待审内容</li>") + "</ul>").encode()
        self._send(200, body)

    def do_POST(self):
        if self.path.split("?")[0] != "/decide":
            return self._send(404, b"not found")
        n = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, json.dumps({"ok": False, "error": "bad json"}).encode(), "application/json")
        out = _decide(payload)
        self._send(200 if out.get("ok") else 400,
                   json.dumps(out, ensure_ascii=False).encode(), "application/json")

    def log_message(self, *a):
        pass


def serve(port: int = 8787) -> None:
    if not OUTBOX.exists():
        OUTBOX.mkdir(parents=True)
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"审批箱：http://127.0.0.1:{port}/  （手机用本机局域网 IP 访问）")
    srv.serve_forever()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="审批箱")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("dist", type=Path)
    p.add_argument("--day", default=None)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8787)
    a = ap.parse_args(argv)

    if a.cmd == "pack":
        print(json.dumps(pack(a.dist, a.day), ensure_ascii=False, indent=2))
    else:
        serve(a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
