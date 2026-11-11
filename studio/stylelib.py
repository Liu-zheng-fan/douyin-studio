"""341 风格库的索引与检索。

库的结构（每个 .md 一个风格）：
    # K13 美漫网点
    - 分类：K 卡通画风 · 画面风格
    - 长什么样：粗线条，网点，速度线，对比强
    - 适合：讲"卖课的人"这种带点讽刺的段落
    ## 风格提示词
    粗线条，网点，速度线，对比强

库路径解析顺序：参数 > 环境变量 FY_STYLE_LIBRARY_ROOT > 常见默认位置。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

DEFAULT_ROOTS = [
    Path(__file__).resolve().parent.parent / "assets" / "stylelib",   # 随项目走，优先
    Path.home() / "Documents" / "风格提示词",
    Path("C:/Users/Root/Documents/风格提示词"),
]
CACHE = Path(__file__).parent / ".style_index.json"


def resolve_root(root: str | Path | None = None) -> Path:
    for cand in ([Path(root)] if root else []) + \
                ([Path(os.environ["FY_STYLE_LIBRARY_ROOT"])] if os.environ.get("FY_STYLE_LIBRARY_ROOT") else []) + \
                DEFAULT_ROOTS:
        if cand and cand.exists() and any(cand.rglob("*.md")):
            return cand
    raise SystemExit("找不到风格库。传 --root，或设 FY_STYLE_LIBRARY_ROOT，或放到 ~/Documents/风格提示词")


def _parse(md: Path) -> dict:
    text = md.read_text(encoding="utf-8", errors="replace")
    title = ""
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        title = m.group(1).strip()

    def field(name: str) -> str:
        mm = re.search(rf"^-\s*{name}\s*[：:]\s*(.+)$", text, re.M)
        return mm.group(1).strip() if mm else ""

    prompt = ""
    mp = re.search(r"##\s*风格提示词\s*\n+(.+?)(?:\n##|\Z)", text, re.S)
    if mp:
        prompt = " ".join(mp.group(1).split())

    return {
        "id": md.stem,
        "title": title or md.stem,
        "category": field("分类"),
        "look": field("长什么样"),
        "fit": field("适合"),
        "prompt": prompt,
        "path": str(md),
    }


def index(root: str | Path | None = None, rebuild: bool = False) -> list[dict]:
    base = resolve_root(root)
    if not rebuild and CACHE.exists():
        try:
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            if data.get("root") == str(base):
                return data["entries"]
        except Exception:
            pass
    entries = [_parse(p) for p in sorted(base.rglob("*.md"))]
    try:
        CACHE.write_text(json.dumps({"root": str(base), "entries": entries}, ensure_ascii=False),
                         encoding="utf-8")
    except OSError:
        pass
    return entries


def search(keyword: str, root: str | Path | None = None, limit: int = 8) -> list[dict]:
    kw = (keyword or "").strip()
    if not kw:
        return []
    needle = kw.lower()
    hits = []
    for e in index(root):
        blob = " ".join([e["id"], e["title"], e["category"], e["look"], e["fit"], e["prompt"]]).lower()
        if needle in blob:
            hits.append(e)
    return hits[:limit]


def treatment_for(entry: dict) -> str:
    """把风格名映射到本机能实现的算法处理。映射不了就 none——不假装。"""
    blob = " ".join([entry.get("title", ""), entry.get("look", ""), entry.get("prompt", "")])
    rules = [
        ("halftone", ["网点", "美漫", "漫画", "半调"]),
        ("pop", ["波普", "丝网", "海报", "撞色"]),
        ("ink", ["线稿", "黑白", "剪影", "钢笔", "素描"]),
        ("chalk", ["粉笔", "黑板"]),
        ("duotone", ["双色", "单色", "胶片", "复古"]),
    ]
    for style, keys in rules:
        if any(k in blob for k in keys):
            return style
    return "none"


def example_for(entry: dict) -> str | None:
    """风格同目录下若有同名 .jpg，就是它的示例图。"""
    p = Path(entry["path"]).with_suffix(".jpg")
    return str(p) if p.exists() else None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法：python -m studio.stylelib <关键词>")
        raise SystemExit(1)
    for e in search(sys.argv[1]):
        print(f"{e['id']:22} {e['title']:14} → 处理 {treatment_for(e):8} | {e['look'][:28]}")
