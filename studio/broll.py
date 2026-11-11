"""B-roll 素材库：155 段镜头，按名字或用途挑。

为什么要有这个模块：把素材全拷进来只有一半价值，
另一半是**让人（和 AI）知道有哪些、该用哪个**。
没有索引的素材库等于没有素材库。

    from studio import broll
    broll.describe()                    # 有多少、都是什么
    broll.pick("blur")                  # 按关键词找
    broll.pick("转场")                  # 按中文用途找
    broll.rebuild_index()               # 素材变了重建索引
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "assets" / "broll"
INDEX = DEFAULT_DIR / "index.json"

# 中文用途 → 文件名关键词。素材多用英文名，这里做一层翻译。
INTENT = {
    "开场": ["open", "intro", "title", "logo", "brand"],
    "转场": ["transition", "slide", "flash", "cut", "wipe", "whip", "blur"],
    "文字": ["type", "word", "text", "font", "typewriter", "dictation"],
    "数据": ["chart", "graph", "counter", "countdown", "stat", "gauge", "dash"],
    "卡片": ["card", "chip", "pill", "bento", "panel", "tile"],
    "背景": ["background", "bg", "gradient", "noise", "grid", "mesh", "wave"],
    "人物": ["avatar", "face", "person", "character"],
    "科技": ["neon", "glitch", "cyber", "hud", "tech", "circuit"],
    "光效": ["light", "glow", "bloom", "flare", "shimmer"],
    "节奏": ["beat", "pulse", "bounce", "impact", "hit"],
}


def index(dirname: Path | None = None, rebuild: bool = False) -> list[dict]:
    base = dirname or DEFAULT_DIR
    cache = base / "index.json"
    if cache.exists() and not rebuild:
        try:
            return json.loads(cache.read_text(encoding="utf-8-sig"))["items"]
        except Exception:
            pass
    return rebuild_index(base)


def rebuild_index(dirname: Path | None = None) -> list[dict]:
    from . import ff

    base = dirname or DEFAULT_DIR
    items = []
    for p in sorted(base.glob("*.mp4")):
        try:
            dur = round(ff.probe_duration(p), 2)
        except Exception:
            dur = None
        items.append({"name": p.stem, "file": p.name,
                      "kb": round(p.stat().st_size / 1024), "seconds": dur})
    base.mkdir(parents=True, exist_ok=True)
    (base / "index.json").write_text(
        json.dumps({"count": len(items), "items": items}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return items


def pick(query: str, dirname: Path | None = None, limit: int = 8) -> list[dict]:
    """按关键词找素材：先查中文用途表，再直接匹配文件名。"""
    items = index(dirname)
    q = (query or "").strip().lower()
    if not q:
        return []

    keywords = [k for intent, kws in INTENT.items() if intent in q for k in kws]
    keywords.append(q)

    hits = []
    for it in items:
        name = it["name"].lower()
        if any(k in name for k in keywords):
            hits.append(it)
        if len(hits) >= limit:
            break
    return hits


def describe(dirname: Path | None = None) -> dict:
    items = index(dirname)
    total = sum(i["kb"] for i in items) / 1024
    return {
        "dir": str(dirname or DEFAULT_DIR),
        "count": len(items),
        "total_mb": round(total, 1),
        "intents": list(INTENT),
        "sample": [i["name"] for i in items[:12]],
        "hint": "用法：broll.pick('转场') 或脚本里 broll 镜头写 \"video\": \"assets/broll/xxx.mp4\"",
    }


def pick_one(query: str, dirname: Path | None = None) -> str | None:
    hits = pick(query, dirname, limit=1)
    return str((dirname or DEFAULT_DIR) / hits[0]["file"]) if hits else None
