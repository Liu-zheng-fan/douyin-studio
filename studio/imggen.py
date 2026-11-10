"""生图：火山引擎方舟（即梦 / Seedream）文生图客户端。

为什么是即梦（Seedream）：
- 中文提示词理解最好，写「端着不锈钢盆的鲸鱼娘」这类古怪组合不容易跑偏
- 国内直连，不用翻墙；本机实测 ark.cn-beijing.volces.com 可达
- 按张计费，几毛钱一张，试错成本低

配置（三选一，优先级从高到低）：
    环境变量   IMGGEN_API_KEY / ARK_API_KEY
                IMGGEN_MODEL（默认 doubao-seedream-3-0-t2i-250415）
                IMGGEN_BASE（默认 https://ark.cn-beijing.volces.com/api/v3）
    配置文件   ~/.douyin-studio/config.json  {"imggen": {"api_key": "...", "model": "..."}}

命令行：
    python -m studio.imggen --check                     # 只检查配置和连通性
    python -m studio.imggen "提示词" --size 720x1280    # 出一张
    python -m studio.imggen "提示词" --n 2 --out 某目录

缓存：同 prompt + size + model 只生成一次，落在 assets/gen/ 下，重跑不重复花钱。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx

DEFAULT_BASE = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedream-5-0-flash-260915"

# Seedream 3.0 支持的尺寸；竖屏用 720x1280
SIZES = ["1024x1024", "864x1152", "1152x864", "1280x720", "720x1280",
         "832x1248", "1248x832", "1512x648"]

CONFIG_PATH = Path.home() / ".douyin-studio" / "config.json"
CACHE_DIR = Path(__file__).resolve().parent.parent / "assets" / "gen"


def _file_cfg() -> dict:
    if CONFIG_PATH.exists():
        try:
            # utf-8-sig：PowerShell 的 Set-Content 会写 BOM，普通 utf-8 解析会失败
            raw = CONFIG_PATH.read_text(encoding="utf-8-sig")
            return (json.loads(raw).get("imggen") or {})
        except Exception:
            return {}
    return {}


def config() -> dict:
    fc = _file_cfg()
    return {
        "api_key": os.environ.get("IMGGEN_API_KEY") or os.environ.get("ARK_API_KEY") or fc.get("api_key"),
        "model": os.environ.get("IMGGEN_MODEL") or fc.get("model") or DEFAULT_MODEL,
        "base": (os.environ.get("IMGGEN_BASE") or fc.get("base") or DEFAULT_BASE).rstrip("/"),
    }


def _emit(ok: bool, data=None, error: dict | None = None) -> dict:
    payload = {"ok": ok}
    if ok:
        payload["data"] = data
    else:
        payload["error"] = error or {"code": "unknown", "message": "未知错误"}
    print(json.dumps(payload, ensure_ascii=False))
    return payload


def _key_or_die() -> str:
    cfg = config()
    if not cfg["api_key"]:
        raise SystemExit(json.dumps({"ok": False, "error": {
            "code": "no_api_key",
            "message": "没有配置生图 API Key",
            "hint": ("去火山方舟控制台开通 Seedream 文生图 → 创建 API Key → "
                     "设置环境变量 IMGGEN_API_KEY，或写进 ~/.douyin-studio/config.json "
                     "的 imggen.api_key"),
        }}, ensure_ascii=False))
    return cfg["api_key"]


def _cache_path(prompt: str, size: str, model: str, index: int) -> Path:
    h = hashlib.sha1(f"{prompt}|{size}|{model}|{index}".encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{h}.png"


def _save_png(raw: bytes, path: Path) -> None:
    """Seedream 返回的通常是 JPEG 字节，扩展名却是 .png，直接落盘会读不出来。"""
    from io import BytesIO

    from PIL import Image

    try:
        Image.open(BytesIO(raw)).convert("RGB").save(path, "PNG")
    except Exception:
        path.write_bytes(raw)


def generate(
    prompt: str,
    size: str = "720x1280",
    n: int = 1,
    watermark: bool = False,
    out_dir: Path | None = None,
    retries: int = 2,
) -> list[Path]:
    """返回本地 PNG 路径列表。命中缓存则不发请求。"""
    cfg = config()
    key = _key_or_die()
    if size not in SIZES:
        raise SystemExit(json.dumps({"ok": False, "error": {
            "code": "bad_size", "message": f"不支持的尺寸 {size}",
            "hint": f"可用：{', '.join(SIZES)}"}}, ensure_ascii=False))

    out_dir = out_dir or CACHE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []

    for i in range(n):
        cached = _cache_path(prompt, size, cfg["model"], i)
        if cached.exists():
            results.append(cached)
            continue

        body = {
            "model": cfg["model"],
            "prompt": prompt,
            "size": size,
            "response_format": "b64_json",
            "watermark": watermark,
            "seed": int(hashlib.sha1(f"{prompt}{i}".encode()).hexdigest()[:8], 16) % 2**31,
        }
        last = None
        for attempt in range(retries + 1):
            try:
                r = httpx.post(f"{cfg['base']}/images/generations",
                               headers={"Authorization": f"Bearer {key}",
                                        "Content-Type": "application/json"},
                               json=body, timeout=180)
                data = r.json()
                if r.status_code != 200 or data.get("error"):
                    err = data.get("error") or {}
                    raise RuntimeError(f"HTTP {r.status_code}: {err.get('code')} {err.get('message')}")
                item = (data.get("data") or [])[0]
                if item.get("b64_json"):
                    raw = base64.b64decode(item["b64_json"])
                elif item.get("url"):
                    raw = httpx.get(item["url"], timeout=120, follow_redirects=True).content
                else:
                    raise RuntimeError(f"响应里没有图片：{str(data)[:300]}")
                cached.write_bytes(raw)
                results.append(cached)
                last = None
                break
            except Exception as exc:
                last = exc
                time.sleep(2 + attempt * 3)
        if last is not None:
            msg = str(last)
            if "ModelNotOpen" in msg:
                hint = (f"模型 {cfg['model']} 存在但未开通。去方舟控制台「模型广场」搜 Seedream "
                        f"点开通，或用 --models 看账号能访问哪些生图模型。")
            elif "InvalidEndpointOrModel" in msg:
                hint = "这个模型对当前账号不可见。用 --models 列出清单，再用 IMGGEN_MODEL 指定。"
            elif any(k in msg for k in ("QuotaExceeded", "InsufficientBalance", "Overdue")):
                hint = "鉴权没问题，是余额/额度不足，去方舟控制台充值。"
            else:
                hint = "检查 Key 是否有效、是否已开通 Seedream、账户余额是否充足。"
            raise SystemExit(json.dumps({"ok": False, "error": {
                "code": "imggen_failed", "message": msg, "hint": hint}},
                ensure_ascii=False))
    return results


def list_image_models() -> list[dict]:
    """账号能看到的生图模型。用于确认「该开通哪个」。"""
    cfg = config()
    key = _key_or_die()
    r = httpx.get(f"{cfg['base']}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
    out = []
    for m in r.json().get("data", []):
        api = m.get("api_supported") or {}
        if m.get("domain") == "ImageGeneration" or api.get("images/generations"):
            out.append({"id": m.get("id"), "domain": m.get("domain"),
                        "supports_api": bool(api.get("images/generations"))})
    return out


def check() -> dict:
    cfg = config()
    hosts = [cfg["base"]]
    reach = []
    for h in hosts:
        try:
            r = httpx.get(h + "/", timeout=15)
            reach.append({"host": h, "status": r.status_code, "reachable": True})
        except Exception as exc:
            reach.append({"host": h, "status": None, "reachable": False, "error": str(exc)})
    return {
        "api_key": bool(cfg["api_key"]),
        "api_key_preview": (cfg["api_key"][:6] + "…" + cfg["api_key"][-4:]) if cfg["api_key"] else None,
        "model": cfg["model"],
        "base": cfg["base"],
        "reachable": reach,
        "cache_dir": str(CACHE_DIR),
        "ready": bool(cfg["api_key"]) and all(x["reachable"] for x in reach),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="即梦（Seedream）文生图")
    ap.add_argument("prompt", nargs="?", help="提示词")
    ap.add_argument("--size", default="720x1280", choices=SIZES)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check", action="store_true", help="只检查配置与连通性")
    ap.add_argument("--models", action="store_true", help="列出账号可访问的生图模型")
    a = ap.parse_args(argv)

    if a.models:
        try:
            print(json.dumps({"ok": True, "data": list_image_models()}, ensure_ascii=False, indent=2))
        except SystemExit as exc:
            print(exc)
            return 1
        return 0

    if a.check or not a.prompt:
        info = check()
        print(json.dumps({"ok": info["ready"], "data": info,
                          "hint": "未就绪时按 data 里的缺失项补齐"}, ensure_ascii=False, indent=2))
        return 0 if info["ready"] else 1
    try:
        paths = generate(a.prompt, a.size, a.n, out_dir=a.out)
    except SystemExit as exc:
        print(exc) if str(exc).strip() else None
        return 1
    print(json.dumps({"ok": True, "data": {"files": [str(p) for p in paths]}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

