"""确定性动画内核。

移植自 fy-code-animation 的 `implementations/motion-core.mjs`，改写成 Python，
保留它的核心约束：**纯函数、无状态、任意帧可重现**。

所有函数只依赖传入的 t（秒）与参数，不读时钟、不用随机数。
这样同一份脚本重复渲染，逐帧一致——这是能对成片做 A/B 的前提。
"""
from __future__ import annotations

import math

__all__ = [
    "clamp", "lerp", "inv_lerp", "progress", "fps_frame",
    "linear", "ease_in_cubic", "ease_out_cubic", "ease_in_out_cubic",
    "ease_out_expo", "ease_out_back", "ease_in_quad", "ease_out_quad",
    "bezier", "spring", "stagger", "pulse", "swing", "track",
]


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if lo > hi:
        raise ValueError("reversed clamp")
    return max(lo, min(hi, x))


def lerp(a: float, b: float, p: float) -> float:
    return a + (b - a) * p


def inv_lerp(a: float, b: float, x: float) -> float:
    if a == b:
        raise ValueError("empty range")
    return clamp((x - a) / (b - a))


def progress(t: float, start: float, end: float) -> float:
    """t 在 [start, end] 区间内的归一化进度，越界自动夹紧。"""
    if end <= start:
        raise ValueError("empty time range")
    return clamp((t - start) / (end - start))


def fps_frame(t: float, fps: int = 30) -> int:
    return int(round(t * fps))


# ------------------------------------------------------------------ easing
def linear(p: float) -> float:
    return clamp(p)


def ease_in_quad(p: float) -> float:
    p = clamp(p)
    return p * p


def ease_out_quad(p: float) -> float:
    p = clamp(p)
    return 1 - (1 - p) ** 2


def ease_in_cubic(p: float) -> float:
    p = clamp(p)
    return p ** 3


def ease_out_cubic(p: float) -> float:
    p = clamp(p)
    return 1 - (1 - p) ** 3


def ease_in_out_cubic(p: float) -> float:
    p = clamp(p)
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out_expo(p: float) -> float:
    p = clamp(p)
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def ease_out_back(p: float, overshoot: float = 1.70158) -> float:
    """回弹：略微冲过头再落回，适合“砸入”类动作。"""
    p = clamp(p)
    c3 = overshoot + 1
    return 1 + c3 * (p - 1) ** 3 + overshoot * (p - 1) ** 2


def bezier(x1: float, y1: float, x2: float, y2: float):
    """CSS 风格 cubic-bezier 求值器，返回 p -> value 的闭包。"""
    for v in (x1, y1, x2, y2):
        if not math.isfinite(v):
            raise ValueError("bezier control must be finite")

    def q(u, a, b):
        return 3 * (1 - u) ** 2 * u * a + 3 * (1 - u) * u * u * b + u ** 3

    def fn(p: float) -> float:
        p = clamp(p)
        if p in (0.0, 1.0):
            return p
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if q(mid, x1, x2) < p:
                lo = mid
            else:
                hi = mid
        return q((lo + hi) / 2, y1, y2)

    return fn


def spring(t: float, freq: float = 1.6, damping: float = 0.55, start: float = 0.0) -> float:
    """阻尼弹簧，返回 0→1 的位移，带自然过冲。

    freq    ：振动频率（Hz），越大越快
    damping ：阻尼比，0.3 抖得厉害，1.0 不过冲
    """
    tau = max(0.0, t - start)
    if tau <= 0:
        return 0.0
    omega = 2 * math.pi * freq
    zeta = clamp(damping, 0.05, 1.0)
    wd = omega * math.sqrt(max(1e-9, 1 - zeta ** 2))
    env = math.exp(-zeta * omega * tau)
    return 1 - env * (math.cos(wd * tau) + (zeta * omega / wd) * math.sin(wd * tau))


def stagger(index: int, delay: float = 0.08, base: float = 0.0) -> float:
    """错峰：第 index 个元素的起始时间。"""
    return base + index * delay


def pulse(t: float, period: float = 1.2, low: float = 0.0, high: float = 1.0) -> float:
    """周期呼吸，返回 low..high。"""
    if period <= 0:
        raise ValueError("period must be positive")
    phase = (t % period) / period
    return lerp(low, high, 0.5 - 0.5 * math.cos(2 * math.pi * phase))


def swing(t: float, freq: float = 0.7, amp: float = 1.0, phase: float = 0.0) -> float:
    return amp * math.sin(2 * math.pi * freq * t + phase)


def track(t: float, keys: list[tuple[float, float]], ease=ease_in_out_cubic) -> float:
    """关键帧插值：keys = [(t0, v0), (t1, v1), ...]，必须按时间升序。

    这是镜头动作的主力——镜头运动、位置、透明度都用它描述。
    """
    if not keys:
        raise ValueError("empty keyframe list")
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            if t1 == t0:
                return v1
            return lerp(v0, v1, ease((t - t0) / (t1 - t0)))
    return keys[-1][1]
