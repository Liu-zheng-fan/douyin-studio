"""发布前合规检查：广告法红线 + AI 标识。

抖音企业号违规罚的是**营业执照主体**，不是「AI 说错了」。
所以这道检查是硬性卡点，默认阻断发布。

只做「能机器判定的部分」：绝对化用语、功效/医疗宣称、价格诱导、绝对承诺。
判断不了的（是否虚假、是否超范围经营）留给人。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict


@dataclass
class Finding:
    severity: str      # block | warn
    category: str
    match: str
    where: str
    advice: str

    def as_dict(self):
        return asdict(self)


# 绝对化用语（《广告法》第九条）
ABSOLUTE = [
    "国家级", "世界级", "最高级", "最佳", "最好", "最强", "最大", "最便宜", "最低价",
    "第一品牌", "全网第一", "销量第一", "行业第一", "排名第一", "唯一", "独家",
    "顶级", "顶尖", "极致", "极品", "王牌", "冠军", "史无前例", "前所未有",
    "万能", "100%", "百分百", "永久", "绝对", "首选", "遥遥领先", "天花板",
]

# 功效 / 医疗宣称（食品、日用品最容易踩）
EFFICACY = [
    "治疗", "治愈", "疗效", "医治", "抗癌", "防癌", "降血压", "降血糖", "降血脂",
    "消炎", "杀菌", "抑菌", "抗菌", "抗病毒", "增强免疫", "提高免疫力", "排毒",
    "补肾", "壮阳", "补血", "补气", "祛湿", "养生", "调理", "药效",
    "无副作用", "纯天然无添加", "食品级",
]

# 价格/促销诱导
PRICE = [
    "全网最低", "史上最低", "亏本清仓", "最后一天", "仅此一次", "错过不再",
    "限时秒杀", "免费送", "0元购",
]

# 抖音对「导流站外」敏感
OFFSITE = [
    "加微信", "加vx", "加VX", "私信我发链接", "扫码加", "淘宝搜", "拼多多",
]

RULES = [
    ("绝对化用语", ABSOLUTE, "block", "《广告法》第九条禁止使用绝对化用语，换成可验证的具体描述。"),
    ("功效宣称", EFFICACY, "block", "普通商品不得宣称医疗/保健功效；如确有检测报告，改为「检测报告编号 xxx」。"),
    ("价格诱导", PRICE, "warn", "促销类表述需与实际一致，且需保留活动记录。"),
    ("站外导流", OFFSITE, "warn", "抖音限制站外导流，可能限流；建议用平台内组件。"),
]

FIELDS = {
    "title": "标题",
    "desc": "简介",
    "tags": "话题",
    "say": "口播",
    "subtitle": "字幕",
}


def _collect(script: dict) -> list[tuple[str, str]]:
    """把脚本里所有会被观众看到/听到的文字摊平。"""
    items: list[tuple[str, str]] = []
    for key in ("title", "desc"):
        if script.get(key):
            items.append((FIELDS[key], script[key]))
    if script.get("tags"):
        items.append((FIELDS["tags"], " ".join(script["tags"])))
    for i, shot in enumerate(script.get("shots", []), start=1):
        say = shot.get("say")
        if say:
            items.append((f"{FIELDS['say']}/{i}", say))
        texts = []
        for key in ("text", "sub", "note", "name", "a", "b", "label", "title", "tag"):
            v = shot.get(key)
            if isinstance(v, str):
                texts.append(v)
            elif isinstance(v, list):
                texts.extend(str(x) for x in v)
        if shot.get("items"):
            texts.extend(str(x) for x in shot["items"])
        if texts:
            items.append((f"{FIELDS['subtitle']}/{i}", " ".join(texts)))
    return items


def check(script: dict) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[str, str, str]] = set()
    for where, text in _collect(script):
        for category, words, severity, advice in RULES:
            for w in words:
                for m in re.finditer(re.escape(w), text):
                    key = (where, w, category)
                    if key in seen:
                        continue
                    seen.add(key)
                    ctx = text[max(0, m.start() - 12): m.end() + 12]
                    findings.append(Finding(severity, category, w, where, f"{advice}（上下文：…{ctx}…）"))
    return findings


def ai_declaration_ok(script: dict) -> bool:
    """脚本里必须显式承认含 AI 生成内容，否则发布端要打标并被提醒。"""
    return bool(script.get("ai_generated", True))


def report(script: dict) -> tuple[bool, list[Finding]]:
    findings = check(script)
    blocked = any(f.severity == "block" for f in findings)
    if not ai_declaration_ok(script):
        findings.append(Finding("block", "AI 标识", "未声明", "script", "抖音要求 AI 生成内容显式标识；把 ai_generated 设为 true 并在发布时打标。"))
        blocked = True
    return (not blocked), findings
