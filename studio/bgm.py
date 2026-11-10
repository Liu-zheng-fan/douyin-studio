"""BGM：按文案情绪自动选型，再用 numpy 现场合成一段。

为什么不下载现成音乐：
1. **版权**——抖音的曲库识别很敏感，随手用的 BGM 是限流和投诉的高发区。
2. **匹配度**——通用素材库的曲子是给人听的整体作品，压到 0.15 音量后只剩「糊」。
3. **可复现**——同一个 mood + 时长，合成结果逐样本一致，方便做 A/B。

合成出来的东西很朴素：pad + 低音 + 一个脉冲。但它在人声下面只承担
「不空」和「定情绪」两件事，够用，而且绝对不会被版权系统拦。

mood 判定：关键词打分 + 镜头结构 + 语速，取最高分。
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SR = 44100

SHAPES = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "sus2": [0, 2, 7],
}

MOODS = {
    # 冷静陈述：只有 pad 和低音，适合数据、复盘、说明
    "calm": dict(bpm=70, roots=[48, 45, 41, 43], shapes=["maj7", "min7", "maj7", "maj"],
                 pulse=0.0, arp=False),
    # 温和：带一点点心跳，适合「我为什么做这件事」
    "warm": dict(bpm=78, roots=[53, 48, 45, 55], shapes=["maj7", "maj7", "min7", "maj"],
                 pulse=0.20, arp=False),
    # 紧张：小调 + 稳定脉冲，适合「但是」「结果」「没人看」
    "tense": dict(bpm=96, roots=[45, 41, 48, 43], shapes=["min7", "maj", "maj7", "maj"],
                  pulse=0.55, arp=False),
    # 推进：快一点 + 八分音符琶音，适合「开始」「上链接」「关注」
    "drive": dict(bpm=112, roots=[48, 43, 45, 41], shapes=["maj", "maj", "min7", "maj"],
                  pulse=0.65, arp=True),
    # 俏皮：大调 + 轻琶音 + 弹性低音，适合自嘲、整活、日常记录
    "quirky": dict(bpm=100, roots=[48, 50, 53, 48], shapes=["maj", "sus2", "maj7", "maj"],
                   pulse=0.30, arp=True),
}

# 平局时的优先级：先要「能看下去」，再要「准确」
PRIORITY = {"drive": 5, "quirky": 4, "tense": 3, "warm": 2, "calm": 1}

# 情绪词：只用两字以上的词，避免「家底」被当成「家」、「走」被当成行动。
# 宁可漏判走 calm，也不要误判——错误的 BGM 比没有 BGM 更伤。
LEXICON = {
    "tense": ["但是", "可是", "却要", "结果", "问题", "失败", "亏了", "踩坑", "风险",
              "没人", "不会", "撑不", "崩了", "掉了", "不行", "退步", "错了", "太难"],
    "drive": ["开始", "干一", "赚到", "赚口", "上链接", "冲一", "现在就", "关注我",
              "点个", "搞起", "试一试", "第一笔", "第一天"],
    "warm": ["手工", "做饭", "回家", "家里", "吃饭", "陪着", "日常", "温度", "慢慢",
             "其实", "简单", "喜欢", "认真", "老实", "装饭", "过日子"],
    "calm": ["数据", "复盘", "原因", "因为", "所以", "比例", "统计", "记录", "结论",
             "现在", "目前", "一共", "合计"],
    "quirky": ["零收入", "白饭", "不会吃", "撑几", "卖一", "自己管", "试试看", "居然",
               "没想到", "整活", "自嘲"],
}

# 自谦/自嘲信号：出现两个以上，说明这是「小人物叙事」，配乐别太正经
SELF_DEPRECATING = ["零", "不会", "撑", "白饭", "第一", "穷", "没"]


def infer_mood(script: dict) -> tuple[str, dict]:
    """返回 (mood, 打分明细)。明细要能解释「为什么是这个 BGM」。"""
    text = " ".join(
        [script.get("title", ""), script.get("desc", "")]
        + [str(s.get("say") or "") for s in script.get("shots", [])]
        + [str(s.get("sub") or "") for s in script.get("shots", [])]
    )
    scores = {m: 0.0 for m in MOODS}

    for mood, words in LEXICON.items():
        hits = sum(text.count(w) for w in words)
        # 封顶：同一个情绪最多加 4 分，避免某个词重复出现把判定带偏
        scores[mood] += min(hits, 4)

    types = [s.get("type") for s in script.get("shots", [])]
    if any(t in ("number", "split") for t in types):
        scores["tense"] += 2.0
    if "line" in types:
        scores["tense"] += 1.0
    if "reveal" in types:
        scores["warm"] += 1.0
    if "cta" in types:
        scores["drive"] += 1.5

    # 自嘲信号：这是「小人物叙事」，配乐别太正经
    dep = sum(1 for w in SELF_DEPRECATING if w in text)
    if dep >= 2:
        scores["quirky"] += 2.0

    # 语速：字/秒。读得快 → 推进；读得慢 → 冷静
    chars = sum(len(str(s.get("say") or "")) for s in script.get("shots", []))
    total = float(script.get("_total_seconds") or 0) or 25.0
    cps = chars / total
    if cps > 5.2:
        scores["drive"] += 1.5
    elif cps < 3.6:
        scores["calm"] += 1.5

    mood = max(scores, key=lambda k: (scores[k], PRIORITY.get(k, 0)))
    return mood, {"scores": {k: round(v, 2) for k, v in scores.items()},
                  "chars_per_second": round(cps, 2), "self_deprecating_hits": dep}


# ------------------------------------------------------------------ synth
def freq(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _env(n: int, attack: float, release: float) -> np.ndarray:
    a = max(1, int(attack * SR))
    r = max(1, int(release * SR))
    e = np.ones(n, dtype=np.float32)
    a = min(a, n)
    e[:a] = np.linspace(0, 1, a, dtype=np.float32)
    r = min(r, n)
    if r > 1:
        e[-r:] *= np.linspace(1, 0, r, dtype=np.float32)
    return e


def _lowpass(x: np.ndarray, width: int = 48) -> np.ndarray:
    """短路箱型滤波，够用且快（不引入 scipy）。"""
    if width <= 1:
        return x
    k = np.ones(width, dtype=np.float32) / width
    return np.convolve(x, k, mode="same").astype(np.float32)


def _tone(midi: float, dur: float, amp: float, harmonics=(1, 0.42, 0.18)) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    base = freq(midi)
    out = np.zeros(n, dtype=np.float32)
    for i, h in enumerate(harmonics, start=1):
        # 轻微失谐让 pad 不呆板
        det = 1.0 + 0.0012 * (i - 1)
        out += (h * np.sin(2 * math.pi * base * i * det * t)).astype(np.float32)
    return out * amp


def compose(mood: str, seconds: float, out_wav: Path) -> dict:
    cfg = MOODS[mood]
    bpm = cfg["bpm"]
    beat = 60.0 / bpm
    bars = max(1, int(math.ceil(seconds / (beat * 4))))
    total = max(seconds + 1.0, bars * beat * 4)

    n = int(total * SR)
    mix = np.zeros(n, dtype=np.float32)

    roots, shapes = cfg["roots"], cfg["shapes"]
    for bar in range(bars):
        root = roots[bar % len(roots)]
        shape = SHAPES[shapes[bar % len(shapes)]]
        t0 = bar * beat * 4
        dur = beat * 4
        start = int(t0 * SR)
        seg_n = min(int(dur * SR), n - start)
        if seg_n <= 0:
            break
        # pad：整小节的和弦铺底
        pad = np.zeros(seg_n, dtype=np.float32)
        for k, interval in enumerate(shape):
            pad += _tone(root + interval, seg_n / SR, 0.16 / len(shape))[:seg_n]
        pad *= _env(seg_n, attack=min(0.9, dur * 0.35), release=min(0.8, dur * 0.3))
        mix[start:start + seg_n] += pad

        # 低音：每小节第一拍
        bass_n = min(int(beat * 2.2 * SR), n - start)
        if bass_n > 0:
            bass = _tone(root - 12, bass_n / SR, 0.22, harmonics=(1, 0.15))[:bass_n]
            bass *= _env(bass_n, attack=0.02, release=min(0.5, bass_n / SR * 0.4))
            mix[start:start + bass_n] += bass

    # 脉冲：稳定的心跳，定住节奏
    if cfg["pulse"] > 0:
        for b in range(int(total / beat) + 1):
            t0 = b * beat
            start = int(t0 * SR)
            kn = int(0.13 * SR)
            if start + kn >= n:
                break
            tt = np.arange(kn, dtype=np.float32) / SR
            f = 110 * np.exp(-tt * 18) + 45
            kick = np.sin(2 * math.pi * np.cumsum(f) / SR).astype(np.float32)
            kick *= np.exp(-tt * 26).astype(np.float32) * 0.30 * cfg["pulse"]
            mix[start:start + kn] += kick

    # 琶音：八分音符，给推进感
    if cfg["arp"]:
        eighth = beat / 2
        steps = int(total / eighth)
        for i in range(steps):
            bar = int(i * eighth // (beat * 4)) % len(roots)
            root = roots[bar]
            shape = SHAPES[shapes[bar % len(shapes)]]
            note = root + shape[i % len(shape)] + 12
            start = int(i * eighth * SR)
            an = int(eighth * 1.4 * SR)
            if start + an >= n:
                break
            a = _tone(note, an / SR, 0.07, harmonics=(1, 0.2))[:an]
            a *= _env(an, attack=0.006, release=an / SR * 0.8)
            mix[start:start + an] += a

    mix = _lowpass(mix, 48)

    # 淡入淡出
    fi = min(int(1.0 * SR), n)
    fo = min(int(2.0 * SR), n)
    mix[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)
    mix[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)

    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak * 0.55).astype(np.float32)

    # 立体声：右声道轻微延时，做出宽度
    delay = int(0.008 * SR)
    right = np.concatenate([np.zeros(delay, dtype=np.float32), mix[:-delay]]) * 0.96
    stereo = np.stack([mix, right], axis=1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())

    return {
        "mood": mood,
        "bpm": bpm,
        "seconds": round(total, 2),
        "file": str(out_wav),
        "chords": [f"{roots[i % len(roots)]}:{shapes[i % len(shapes)]}" for i in range(min(bars, 8))],
    }


def for_script(script: dict, seconds: float, out_wav: Path) -> dict:
    mood, why = infer_mood(script)
    info = compose(mood, seconds, out_wav)
    info["reason"] = why
    return info


if __name__ == "__main__":
    # 只看判定、不出音频：python -m studio.bgm examples/script-01.json
    import json
    import sys

    if len(sys.argv) > 1:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        mood, why = infer_mood(data)
        print(json.dumps({"mood": mood, "bpm": MOODS[mood]["bpm"], **why},
                         ensure_ascii=False, indent=2))
    else:
        print("用法：python -m studio.bgm <script.json>")
