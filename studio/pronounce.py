"""中文 TTS 读音校正。

移植自 dsh-video-pipeline 的 skills/chinese-tts/scripts/pinyin_fix.py。
原理：TTS 按语言模型概率念多音字，风格指令纠不了读音；
**唯一可靠的办法是把词组换成同音字**（行业→航业、还价→环价），
发音必然正确，而字幕仍用原文。

三条铁律：
1. 只做**同音**替换，绝不换词义（"千载"不许改成"千年"）
2. 长词优先匹配，避免短词误伤
3. 覆盖不到的高危字只**告警**，不擅自改——交给人裁决
"""
from __future__ import annotations

import re

# 词组级替换：只在确认安全的语境下替换。
# 每条都必须"听感与正确读音完全一致"。
RULES: list[dict] = [
    # 还 huán（默认常念 hái）
    {"phrase": "还价", "repl": "环价", "why": "讲价义"},
    {"phrase": "还款", "repl": "环款", "why": "归还义"},
    {"phrase": "还清", "repl": "环清", "why": "归还义"},
    {"phrase": "归还", "repl": "归环", "why": "归还义"},
    {"phrase": "退还", "repl": "退环", "why": "归还义"},
    # 重 chóng（默认常念 zhòng）
    {"phrase": "重新", "repl": "虫新", "why": "再一次义"},
    {"phrase": "重复", "repl": "虫复", "why": "再一次义"},
    {"phrase": "重来", "repl": "虫来", "why": "再一次义"},
    {"phrase": "重启", "repl": "虫启", "why": "再一次义"},
    {"phrase": "重做", "repl": "虫做", "why": "再一次义"},
    # 行 háng（默认常念 xíng）
    {"phrase": "行业", "repl": "航业", "why": "行业义"},
    {"phrase": "行情", "repl": "航情", "why": "行情义"},
    {"phrase": "行家", "repl": "航家", "why": "内行义"},
    {"phrase": "银行", "repl": "银航", "why": "机构名"},
    {"phrase": "同行", "repl": "同航", "why": "同业义"},
    # 长 zhǎng（默认常念 cháng）
    {"phrase": "涨价", "repl": "掌价", "why": "上涨义"},
    {"phrase": "增长", "repl": "增掌", "why": "增加义"},
    {"phrase": "长大", "repl": "掌大", "why": "成长义"},
    {"phrase": "长辈", "repl": "掌辈", "why": "辈分义"},
    # 涨 zhǎng（默认有时念 zhàng）
    {"phrase": "涨粉", "repl": "掌粉", "why": "增加义"},
    {"phrase": "上涨", "repl": "上掌", "why": "增加义"},
    # 着 zháo（默认常念 zhe）
    {"phrase": "着急", "repl": "招急", "why": "焦急义"},
    {"phrase": "着火", "repl": "招火", "why": "燃烧义"},
    {"phrase": "睡着", "repl": "睡招", "why": "入睡义"},
    # 差 chà / chāi
    {"phrase": "差评", "repl": "岔评", "why": "不好义"},
    {"phrase": "差不多", "repl": "岔不多", "why": "近似义"},
    {"phrase": "出差", "repl": "出拆", "why": "公差义"},
    # 弹 dàn（默认常念 tán）
    {"phrase": "弹幕", "repl": "谈幕", "why": "弹幕义"},
    {"phrase": "子弹", "repl": "子蛋", "why": "弹药义"},
    # 铺 pù（默认常念 pū）
    {"phrase": "店铺", "repl": "店瀑", "why": "店面义"},
    {"phrase": "铺面", "repl": "瀑面", "why": "店面义"},
    # 率 shuài（默认常念 lǜ）
    {"phrase": "率领", "repl": "帅领", "why": "带领义"},
    {"phrase": "轻率", "repl": "轻帅", "why": "草率义"},
    # 结 jiē（默认常念 jié）
    {"phrase": "结实", "repl": "街实", "why": "牢固义"},
    # 角 jué（默认常念 jiǎo）
    {"phrase": "角色", "repl": "决色", "why": "人物义"},
    {"phrase": "主角", "repl": "主决", "why": "人物义"},
    # 模 mú（默认常念 mó）
    {"phrase": "模样", "repl": "母样", "why": "样子义"},
    # 省 xǐng（默认常念 shěng）
    {"phrase": "反省", "repl": "反醒", "why": "自省义"},
    # 供 gòng（默认常念 gōng）
    {"phrase": "供品", "repl": "贡品", "why": "祭祀义"},
    # 挑 tiǎo（默认常念 tiāo）
    {"phrase": "挑战", "repl": "窕战", "why": "挑战义"},
    # 当 dàng（默认常念 dāng）
    {"phrase": "当作", "repl": "荡作", "why": "作为义"},
    {"phrase": "上当", "repl": "上荡", "why": "受骗义"},
    # 数 shǔ（默认常念 shù）
    {"phrase": "数一数", "repl": "属一属", "why": "清点义"},
    {"phrase": "数不清", "repl": "属不清", "why": "清点义"},
    # 系 jì（默认常念 xì）
    {"phrase": "系鞋带", "repl": "记鞋带", "why": "打结义"},
    # 传 zhuàn（默认常念 chuán）
    {"phrase": "传记", "repl": "篆记", "why": "文体义"},
    # 参 shēn（默认常念 cān）
    {"phrase": "人参", "repl": "人深", "why": "药材义"},
    {"phrase": "海参", "repl": "海深", "why": "食材义"},
    # 薄 báo（默认常念 bó）
    {"phrase": "薄饼", "repl": "雹饼", "why": "厚度义"},
    {"phrase": "薄片", "repl": "雹片", "why": "厚度义"},
    # 落 là（默认常念 luò）
    {"phrase": "落枕", "repl": "烙枕", "why": "口语义"},
    # 宁 nìng（默认常念 níng）
    {"phrase": "宁可", "repl": "泞可", "why": "宁愿义"},
    # 更 gēng（默认常念 gèng）
    {"phrase": "更新", "repl": "耕新", "why": "更换义"},
]

# 没有替换规则但容易念错的高危字：只告警，不改
RISK_CHARS = "朝还重行长着差弹铺率结角模省供挑当数系传参薄落宁更"

# 阿拉伯数字 → 中文读法（TTS 对百分比、单位常读错）
_DIGITS = "零一二三四五六七八九"


def _tens(n: int, lead_one: bool = False) -> str:
    """10..99。lead_one=True 时 10–19 读作「一十二」（用于「七百一十二」）。"""
    if 10 <= n < 20:
        rest = n % 10
        return ("一" if lead_one else "") + "十" + (_DIGITS[rest] if rest else "")
    return _DIGITS[n // 10] + "十" + (_DIGITS[n % 10] if n % 10 else "")


def _num_cn(n: int) -> str:
    if n < 0:
        return "负" + _num_cn(-n)
    if n < 10:
        return _DIGITS[n]
    if n < 100:
        return _tens(n)
    if n < 1000:
        rest = n % 100
        head = _DIGITS[n // 100] + "百"
        if rest == 0:
            return head
        if rest < 10:
            return head + "零" + _DIGITS[rest]
        return head + _tens(rest, True)
    if n < 10000:
        rest = n % 1000
        head = _DIGITS[n // 1000] + "千"
        if rest == 0:
            return head
        if rest < 10:
            return head + "零" + _DIGITS[rest]
        if rest < 100:
            return head + "零" + _tens(rest, True)
        return head + _num_cn(rest)
    if n < 100000000:
        rest = n % 10000
        head = _num_cn(n // 10000) + "万"
        if rest == 0:
            return head
        if rest < 1000:
            return head + "零" + _num_cn(rest)
        return head + _num_cn(rest)
    return str(n)


def _spoken_numbers(text: str) -> str:
    """百分比与常见单位换成中文读法；纯数字保留（TTS 一般能读对）。"""
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", lambda m: "百分之" + _num_cn(int(float(m.group(1)))), text)
    text = re.sub(r"(\d+)\s*℃", lambda m: _num_cn(int(m.group(1))) + "度", text)
    return text


def fix(text: str) -> tuple[str, list[dict]]:
    """返回 (TTS 安全文本, 应用的替换)。

    长词优先：先把规则按 length 降序排，逐一 replace。
    """
    applied: list[dict] = []
    out = text
    for rule in sorted(RULES, key=lambda r: -len(r["phrase"])):
        if rule["phrase"] in out:
            out = out.replace(rule["phrase"], rule["repl"])
            applied.append({"phrase": rule["phrase"], "repl": rule["repl"], "why": rule["why"]})
    out = _spoken_numbers(out)
    return out, applied


def check(text: str) -> list[dict]:
    """只诊断：返回命中的规则 + 未覆盖的高危字。"""
    applied = [r for r in RULES if r["phrase"] in text]
    covered = "".join(r["phrase"] for r in applied)
    risk = []
    for ch in RISK_CHARS:
        if ch in text and ch not in covered:
            risk.append({"char": ch, "hint": "多音字，可能有更精确的读法；没把握就换个词"})
    return [{"type": "rule", **r} for r in applied] + [{"type": "risk", **r} for r in risk]


def describe() -> dict:
    return {
        "rules": len(RULES),
        "risk_chars": len(RISK_CHARS),
        "sample": [f'{r["phrase"]}→{r["repl"]}' for r in RULES[:6]],
    }
