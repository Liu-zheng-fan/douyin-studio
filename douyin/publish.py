"""发布与数据：抖音开放平台客户端。

设计契约沿用 bili-cli：**stdout 只输出一个 JSON**，退出码非 0 表示失败，
写操作必须先能 `--dry-run` 预览。

官方接口需要「视频发布」权限，个人号大多拿不到；拿不到时用 `package`
生成人工发布包，30 秒手动发完，风险为零。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import httpx

API = "https://open.douyin.com"
TOKEN_URL = f"{API}/oauth/client_token/"
UPLOAD_URL = f"{API}/api/douyin/v1/video/upload_video/"
CREATE_URL = f"{API}/api/douyin/v1/video/create_video/"

CONFIG_PATH = Path.home() / ".douyin-studio" / "config.json"


def _emit(ok: bool, data=None, error: dict | None = None) -> dict:
    payload = {"ok": ok}
    if ok:
        payload["data"] = data
    else:
        payload["error"] = error or {"code": "unknown", "message": "未知错误"}
    print(json.dumps(payload, ensure_ascii=False))
    return payload


def config() -> dict:
    cfg = {}
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    for key, env in (("client_key", "DOUYIN_CLIENT_KEY"),
                     ("client_secret", "DOUYIN_CLIENT_SECRET"),
                     ("open_id", "DOUYIN_OPEN_ID")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    return cfg


def _load_meta(dist: Path) -> dict:
    mp = dist / "meta.json"
    if not mp.exists():
        raise SystemExit(json.dumps({"ok": False, "error": {
            "code": "no_meta", "message": f"{dist} 里没有 meta.json"}}, ensure_ascii=False))
    return json.loads(mp.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ package
CHECKLIST = """# 手动发布清单（抖音企业号）

1. 打开抖音 App → 创作者中心 → 发布作品
2. 上传：`{video}`
3. 封面：选 `{cover}`（3:4，主页网格用）
4. 标题/文案（直接复制 `caption.txt`）
5. 话题：`{tags}`
6. **高级设置 → 内容由 AI 生成**：打开
7. 公开范围、位置、合集按需设置
8. 发布后 10 分钟，把 4 个数字填进台账：播放、点赞、评论、粉丝

> 合规提示：`meta.json` 里的 compliance 若为 blocked，先改文案再发。
"""


def _resolve_video(dist: Path, meta: dict) -> Path:
    raw = Path(meta["video"])
    if raw.is_absolute() and raw.exists():
        return raw
    if raw.exists():
        return raw.resolve()
    # meta 里可能是相对 cwd 的路径，退化成按文件名在 dist 里找
    cand = dist / raw.name
    if cand.exists():
        return cand
    raise SystemExit(json.dumps({"ok": False, "error": {
        "code": "no_video", "message": f"找不到成片：{raw}（也不是 {cand}）"}}, ensure_ascii=False))


def package(dist: Path) -> dict:
    meta = _load_meta(dist)
    video = _resolve_video(dist, meta)

    out = dist / "publish"
    out.mkdir(exist_ok=True)
    shutil.copy2(video, out / "video.mp4")
    cover = Path(meta["cover_3x4"])
    if cover.exists():
        shutil.copy2(cover, out / "cover_3x4.png")

    caption = (meta.get("title") or "").strip() + "\n\n" + (meta.get("desc") or "").strip()
    (out / "caption.txt").write_text(caption.strip(), encoding="utf-8")
    (out / "tags.txt").write_text(" ".join(f"#{t}" for t in meta.get("tags", [])), encoding="utf-8")
    (out / "checklist.md").write_text(
        CHECKLIST.format(video=video.name, cover="cover_3x4.png",
                         tags=" ".join(meta.get("tags", []))), encoding="utf-8")
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"mode": "package", "dir": str(out), "files": sorted(p.name for p in out.iterdir()),
            "ai_declare": bool(meta.get("ai_generated", True)),
            "duration": meta.get("duration"),
            "next": "照 checklist.md 手动发；发完用 ops.ledger 记一条。"}


# ------------------------------------------------------------------ api
def _token(cfg: dict) -> str:
    r = httpx.post(TOKEN_URL, json={"client_key": cfg["client_key"],
                                    "client_secret": cfg["client_secret"],
                                    "grant_type": "client_credential"}, timeout=20)
    body = r.json()
    data = body.get("data") or {}
    if body.get("data", {}).get("error_code") not in (0, None):
        raise RuntimeError(f"取 token 失败：{data}")
    tok = data.get("access_token")
    if not tok:
        raise RuntimeError(f"取 token 失败：{body}")
    return tok


def _upload(video: Path, cfg: dict, token: str) -> str:
    url = f"{UPLOAD_URL}?open_id={cfg['open_id']}&access_token={token}"
    with open(video, "rb") as fh:
        r = httpx.post(url, files={"video": (video.name, fh, "video/mp4")}, timeout=300)
    body = r.json()
    vid = ((body.get("data") or {}).get("video") or {}).get("video_id")
    if not vid:
        raise RuntimeError(f"上传失败：{body}")
    return vid


def _create(video_id: str, text: str, cfg: dict, token: str) -> dict:
    url = f"{CREATE_URL}?open_id={cfg['open_id']}&access_token={token}"
    r = httpx.post(url, json={"video_id": video_id, "text": text}, timeout=60)
    return r.json()


def publish_api(dist: Path, dry_run: bool) -> dict:
    meta = _load_meta(dist)
    cfg = config()
    missing = [k for k in ("client_key", "client_secret", "open_id") if not cfg.get(k)]
    text = (meta.get("title") or "").strip() + "\n" + " ".join(f"#{t}" for t in meta.get("tags", []))
    payload = {"text": text[:1000], "video": meta.get("video"), "ai_generated": meta.get("ai_generated")}

    if dry_run or missing:
        return {
            "mode": "api",
            "dry_run": True,
            "payload": payload,
            "missing": missing,
            "next": ("补齐 client_key / client_secret / open_id 后去掉 --dry-run。"
                     "没开通发布权限就用 `package` 走人工。"),
        }

    token = _token(cfg)
    video = _resolve_video(dist, meta)
    vid = _upload(video, cfg, token)
    resp = _create(vid, payload["text"], cfg, token)
    return {"mode": "api", "video_id": vid, "response": resp}


# ------------------------------------------------------------------ cli
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="抖音发布：人工包 / 官方接口")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("package", help="生成人工发布包（推荐）")
    p1.add_argument("dist", type=Path)
    p2 = sub.add_parser("api", help="走开放平台接口（需权限）")
    p2.add_argument("dist", type=Path)
    p2.add_argument("--dry-run", action="store_true", default=True)
    p2.add_argument("--yes", action="store_true", help="真的发出去")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "package":
            _emit(True, package(a.dist))
        else:
            _emit(True, publish_api(a.dist, dry_run=not a.yes))
    except SystemExit:
        raise
    except Exception as exc:
        _emit(False, error={"code": "publish_failed", "message": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
