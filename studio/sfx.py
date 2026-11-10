"""音效与配乐合成：把画面事件变成声音。

移植自 vibe-knowledge-film 的 engine/audio.py（1216★ 的那个项目）。
原版依赖 scipy（butter / lfilter / fftconvolve），这里改成纯 numpy：
滤波器走频域乘法，混响走 FFT 卷积。效果等价，少一个重依赖。

为什么要音效：BGM 只负责"不空"，音效才负责"节奏"。
砸字一下、转场一记、数字滚动一串——这些让观众感觉"快"，而不是让画面真的快。

事件类型（沿用原版命名）：
    tick   短促的"嗒"，配打字 / 数字
    tock   更低的"笃"
    thud   一记闷响，配砸入
    stamp  盖章，配结论
    rise   上滑音，配提问 / 蓄势
    chord  和弦，配段落开始
    bloom  闪白，配揭晓
    shimmer 微光，配结尾
    hush   静音两秒，配"说完重话"之后
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
D3 = 146.83
PENTA = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21]
CHORD = [0, 7, 12, 14, 19, 24, 26]


def hz(semi: float, base: float = D3) -> float:
    return base * 2 ** (semi / 12)


def env_exp(n: int, tau: float, attack: float = 0.004) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t / tau)


# ------------------------------------------------------------------ filters
def _fft_filter(x: np.ndarray, kind: str, fc: float, order: int = 2) -> np.ndarray:
    """频域 Butterworth。比时域 IIR 慢一点，但不需要 scipy，且对离线合成完全够用。"""
    n = x.shape[0]
    freqs = np.fft.rfftfreq(n, 1 / SR)
    f = np.maximum(freqs, 1e-9)
    if kind == "low":
        mag = 1 / np.sqrt(1 + (f / fc) ** (2 * order))
    else:
        mag = 1 / np.sqrt(1 + (fc / f) ** (2 * order))
    shape = (-1,) + (1,) * (x.ndim - 1)
    spec = np.fft.rfft(x, axis=0) * mag.reshape(shape)
    return np.fft.irfft(spec, n=n, axis=0)


def lowpass(x, fc, order=2):
    return _fft_filter(x, "low", fc, order)


def highpass(x, fc, order=2):
    return _fft_filter(x, "high", fc, order)


def pan(x: np.ndarray, p: float) -> np.ndarray:
    l, r = np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4)
    return np.stack([x * l, x * r], 1)


def add(buf: np.ndarray, x: np.ndarray, t: float) -> None:
    i = int(t * SR)
    if i >= len(buf) or i < 0:
        return
    n = min(len(x), len(buf) - i)
    buf[i:i + n] += x[:n]


def tone(f: float, dur: float, tau: float, partials=((1, 1.0),), attack=0.004, vib=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for mult, amp in partials:
        ph = 2 * np.pi * f * mult * t + (vib * np.sin(2 * np.pi * 4.3 * t) if vib else 0)
        out += amp * np.sin(ph) * np.exp(-t / (tau / (1 + 0.35 * (mult - 1))))
    return out * np.minimum(1, t / attack)


# ------------------------------------------------------------------ events
def ev_tick(rng, p):
    f = hz(PENTA[int(p.get("pitch", 0)) % len(PENTA)] + 24)
    x = tone(f, .5, .09, ((1, 1), (2.01, .28), (3.02, .1)), attack=.002)
    click = highpass(rng.standard_normal(int(.012 * SR)) * env_exp(int(.012 * SR), .003), 3000) * .25
    x[:len(click)] += click
    return pan(x * .16 * p.get("gain", 1), rng.uniform(-.35, .35))


def ev_tock(rng, p):
    f = 520 * 2 ** (int(p.get("pitch", 0)) * 2 / 12)
    n = int(.25 * SR)
    x = tone(f, .25, .04, ((1, 1), (2.7, .4), (5.1, .15)), attack=.001)
    x += highpass(rng.standard_normal(n), 2500) * env_exp(n, .006) * .3
    return pan(x * .2 * p.get("gain", 1), rng.uniform(-.5, .5))


def ev_thud(rng, p):
    n = int(.6 * SR)
    t = np.arange(n) / SR
    f = 95 * np.exp(-t * 9) + 48
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, .13, .002)
    x += lowpass(rng.standard_normal(n), 600) * env_exp(n, .04) * .5
    return pan(x * .42 * p.get("gain", 1), 0)


def ev_stamp(rng, p):
    n = int(.5 * SR)
    x = ev_thud(rng, {"gain": 1.1})[:n, 0] + highpass(rng.standard_normal(n), 1800) * env_exp(n, .02) * .35
    return pan(x * p.get("gain", 1), 0)


def ev_rise(rng, p):
    dur = p.get("dur", 1.0)
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(7) * 2 ** (t / dur * 1.0)
    ph = 2 * np.pi * np.cumsum(f) / SR
    e = np.sin(np.pi * np.minimum(1, t / dur) ** 1.6) ** 1.2
    ns = lowpass(rng.standard_normal(n), 2500) * (t / dur) ** 2 * .22
    return pan((np.sin(ph) * .1 + ns * .1) * e * p.get("gain", 1), 0)


def ev_chord(rng, p):
    root = p.get("root", 0)
    n = int(9 * SR)
    out = np.zeros((n, 2))
    for k, semi in enumerate(CHORD):
        f = hz(root + semi)
        x = tone(f, 9, 2.6 - k * .12, ((1, 1), (2.003, .32), (3.01, .14), (4.02, .06)),
                 attack=.012, vib=.6)
        out += pan(x * (.11 / (1 + k * .22)), (k % 3 - 1) * .5)
    sub = tone(hz(root - 12), 6, 2.2, ((1, 1),), attack=.02)
    out[:len(sub)] += pan(sub * .16, 0)
    return out * p.get("gain", 1)


def ev_bloom(rng, p):
    out = ev_chord(rng, {"root": p.get("root", 0), "gain": 1.15 * p.get("gain", 1)})
    n = int(1.6 * SR)
    ns = rng.standard_normal((n, 2)) * env_exp(n, .35, .01)[:, None]
    out[:n] += lowpass(highpass(ns, 500), 7000) * .12
    return out


def ev_soft(rng, p):
    return pan(tone(hz(12 + 7), 2.2, .7, ((1, 1), (2, .2)), attack=.03) * .12 * p.get("gain", 1), 0)


def ev_shimmer(rng, p):
    n = int(2.4 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k in range(7):
        out += np.sin(2 * np.pi * hz(24 + PENTA[k + 2]) * t + rng.uniform(0, 6)) * \
               np.exp(-((t - .25 - k * .06) / .5) ** 2)
    return pan(out * .035 * p.get("gain", 1), 0)


EV = dict(tick=ev_tick, tock=ev_tock, thud=ev_thud, stamp=ev_stamp,
          rise=ev_rise, chord=ev_chord, bloom=ev_bloom, soft=ev_soft, shimmer=ev_shimmer)

# 镜头类型 → 默认音效。没有就静音，不要硬加。
SHOT_SFX = {
    "hook": [("bloom", {"gain": 1.1})],
    "number": [("tock", {"gain": .9})],
    "split": [("thud", {"gain": .8})],
    "line": [("tick", {"pitch": 2})],
    "reveal": [("stamp", {"gain": 1.0})],
    "bullets": [("tick", {"pitch": 4})],
    "art": [("soft", {})],
    "broll": [("soft", {"gain": .7})],
    "cta": [("chord", {"gain": .8}), ("shimmer", {})],
}


# ------------------------------------------------------------------ synth
def reverb(x: np.ndarray, rng, t60: float = 3.2, wet: float = 0.38) -> np.ndarray:
    n = int(t60 * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-6.9 * t / t60)[:, None]
    ir = lowpass(ir, 5200)
    norm = np.sqrt((ir ** 2).sum(0)).max() or 1.0
    ir /= norm
    m = len(x) + n - 1
    wet_sig = np.stack([
        np.fft.irfft(np.fft.rfft(x[:, c], n=m) * np.fft.rfft(ir[:, c], n=m))[:len(x)]
        for c in (0, 1)
    ], 1)
    return x + wet_sig * wet


def synth(events: list[tuple], end: float, meta: dict | None = None) -> np.ndarray:
    """events: [(时刻秒, 事件名, 参数字典)]；end: 总时长秒。"""
    meta = meta or {}
    n = int((end + .05) * SR)
    rng = np.random.default_rng(20261110)
    dry = np.zeros((n, 2))
    root = meta.get("root", 0)

    for when, name, params in events:
        fn = EV.get(name)
        if fn is None:
            continue
        p = dict(params or {})
        if name in ("chord", "bloom"):
            p["root"] = p.get("root", 0) + root
        add(dry, fn(rng, p), when)

    out = reverb(dry, rng)

    # 低频铺底：两个略微失谐的正弦 + 很慢的呼吸，让静的时候不空
    t = np.arange(n) / SR
    lv = .05 * meta.get("drone", 1)
    d = (np.sin(2 * np.pi * hz(root - 24) * t)
         + .6 * np.sin(2 * np.pi * hz(root - 24 + .08) * 2 * t)
         + .25 * np.sin(2 * np.pi * hz(root - 12 + 7) * t)) * (.75 + .25 * np.sin(2 * np.pi * t / 11))
    air = lowpass(highpass(rng.standard_normal(n), 300), 1800) * .012 * (.6 + .4 * np.sin(2 * np.pi * t / 17))
    out += np.stack([d * lv + air, d * lv + np.roll(air, 4000)], 1)

    # 静音门：hush 之后真的安静下来
    g = np.ones(n)
    for when, name, p in events:
        if name == "hush":
            a, b = when, when + (p or {}).get("dur", 2.5)
            g *= 1 - np.clip((t - a) / .15, 0, 1) * (1 - np.clip((t - b) / .4, 0, 1))
    g *= np.clip(t / .6, 0, 1) * np.clip((end - t) / 1.2, 0, 1)
    out *= g[:, None]
    return out


def events_for(durations: list[float], starts: list[float], shots: list[dict]) -> list[tuple]:
    """从时间轴推出事件表：每镜开头一记，外加数字镜中途的嗒声。"""
    events: list[tuple] = []
    for i, shot in enumerate(shots):
        kind = shot.get("type", "")
        t0 = starts[i]
        for name, p in SHOT_SFX.get(kind, []):
            events.append((round(t0 + 0.02, 3), name, p))
        # 数字滚动时给一串嗒声，制造"在涨"的感觉
        if kind == "number":
            for k in range(4):
                events.append((round(t0 + 0.25 + k * 0.18, 3), "tick", {"pitch": k}))
    return events


def write_wav(path: Path, x: np.ndarray) -> Path:
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def build(durations: list[float], starts: list[float], shots: list[dict],
          out_wav: Path, drone: float = 1.0) -> dict:
    end = sum(durations)
    events = events_for(durations, starts, shots)
    x = synth(events, end, {"drone": drone})
    peak = np.abs(x).max() or 1.0
    x = x / peak * 10 ** (-3 / 20)     # 留 3 dB 余量，混音时再抬
    write_wav(out_wav, x)
    return {"file": str(out_wav), "events": len(events), "seconds": round(end, 2)}
