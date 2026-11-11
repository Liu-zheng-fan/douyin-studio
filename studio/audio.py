"""配音：默认用 edge-tts 的神经音色，离线兜底用 Windows SAPI。

为什么要换代：
- SAPI 的 Microsoft Huihui 是 2010 年代的拼接式音色，断句机械、声调平，
  在抖音这种「前三秒定生死」的场景里，一开口就把完播率让掉了。
- edge-tts 走的是微软 Edge 朗读的神经网络音色（晓晓/云希/云扬…），
  音质接近商业配音，且免费、无需 API Key、单条几秒返回。

代价：必须联网。所以保留 SAPI 作为兜底，断网时自动降级并明确告警。

音色别名（写进 script.json 的 voice 字段即可）：
    narrator → 云希（年轻男声，对话感，适合第一人称自述）
    anchor   → 云扬（播音腔，冷面，反差感强）
    warm     → 晓晓（最自然的女声）
    lively   → 晓依（活泼女声）
    passion  → 云健（激昂男声）
"""
from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import wave
from pathlib import Path

from . import ff

LEAD = 0.18
TAIL = 0.30

VOICES = {
    "narrator": "zh-CN-YunxiNeural",
    "anchor": "zh-CN-YunyangNeural",
    "warm": "zh-CN-XiaoxiaoNeural",
    "lively": "zh-CN-XiaoyiNeural",
    "passion": "zh-CN-YunjianNeural",
}

DEFAULT_VOICE = "narrator"
DEFAULT_RATE = "-4%"       # 略慢，压住「念稿感」
DEFAULT_PITCH = "-2Hz"     # 略低沉，增加可信度

SAPI_VOICE = "Microsoft Huihui Desktop"
SAPI_RATE = -1

_PS = r"""
$ErrorActionPreference = 'Stop'
$job = Get-Content -Raw -Encoding UTF8 $jobPath | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try { $synth.SelectVoice($job.voice) } catch { }
$synth.Rate = [int]$job.rate
$synth.Volume = 100
foreach ($item in $job.items) {
  $synth.SetOutputToWaveFile($item.path)
  $synth.Speak($item.text)
  $synth.SetOutputToNull()
}
$synth.Dispose()
Write-Output "ok"
"""


def _ps_encoded(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def resolve_voice(name: str | None) -> str:
    if not name:
        return VOICES[DEFAULT_VOICE]
    if name in VOICES:
        return VOICES[name]
    if "Neural" in name or name.startswith("zh-"):
        return name
    raise SystemExit(f"未知音色：{name}。可用别名：{', '.join(VOICES)}，或直接写完整名如 zh-CN-YunxiNeural")


# ------------------------------------------------------------------ edge
async def _edge_batch(texts: list[str], voices: list[str], rate: str, pitch: str,
                      mp3_dir: Path, proxies: dict | None = None) -> None:
    import edge_tts

    async def one(i: int, text: str, voice: str):
        out = mp3_dir / f"line{i}.mp3"
        comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, proxy=proxies)
        await comm.save(str(out))

    tasks = [one(i, t, v) for i, (t, v) in enumerate(zip(texts, voices), start=1)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    errs = [r for r in results if isinstance(r, Exception)]
    if errs:
        raise RuntimeError(f"edge-tts 失败：{errs[0]}")


def _edge(texts: list[str], out_dir: Path, voice: str, rate: str, pitch: str) -> list[Path]:
    mp3_dir = out_dir / "mp3"
    mp3_dir.mkdir(parents=True, exist_ok=True)
    for old in mp3_dir.glob("*.mp3"):
        old.unlink()

    last = None
    for attempt in range(3):
        try:
            asyncio.run(_edge_batch(texts, [voice] * len(texts), rate, pitch, mp3_dir))
            last = None
            break
        except Exception as exc:   # 网络抖动时重试，三次都失败才降级
            last = exc
            import time
            time.sleep(1.5)
    if last is not None:
        raise RuntimeError(str(last))

    wavs: list[Path] = []
    for i in range(1, len(texts) + 1):
        src = mp3_dir / f"line{i}.mp3"
        dst = out_dir / f"line{i}.wav"
        ff.run([ff.ffmpeg(), "-y", "-loglevel", "error", "-i", str(src),
                "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(dst)])
        wavs.append(dst)
    return wavs


# ------------------------------------------------------------------ sapi
def _sapi(texts: list[str], out_dir: Path) -> list[Path]:
    items = []
    for i, text in enumerate(texts, start=1):
        p = out_dir / f"line{i}.wav"
        if p.exists():
            p.unlink()
        items.append({"text": text, "path": str(p)})

    job = out_dir / "tts_job.json"
    job.write_text(json.dumps({"voice": SAPI_VOICE, "rate": SAPI_RATE, "items": items},
                              ensure_ascii=False), encoding="utf-8")
    script = f"$jobPath = '{str(job).replace(chr(39), chr(39) * 2)}'\n" + _PS
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", _ps_encoded(script)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"SAPI 合成失败：{proc.stderr[-800:] or proc.stdout[-800:]}")
    return [Path(it["path"]) for it in items]


# ------------------------------------------------------------------ public
def synthesize(
    texts: list[str],
    out_dir: Path,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    engine: str = "auto",
) -> tuple[list[Path], str]:
    """返回 (wav 列表, 实际使用的引擎)。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved = resolve_voice(voice)

    # 读音校正：只改送进 TTS 的文本，字幕仍用 script.json 里的原文
    from . import pronounce
    fixed = []
    hits = 0
    for t in texts:
        safe, applied = pronounce.fix(t)
        fixed.append(safe)
        hits += len(applied)
        for a in applied:
            print(f"  读音：{a['phrase']} → {a['repl']}（{a['why']}）")
    texts = fixed
    if hits:
        print(f"读音校正 {hits} 处")

    if engine in ("auto", "edge"):
        try:
            return _edge(texts, out_dir, resolved, rate, pitch), "edge"
        except Exception as exc:
            if engine == "edge":
                raise
            print(f"[降级] edge-tts 不可用（{exc}），改用 SAPI。音质会明显下降。")
    return _sapi(texts, out_dir), "sapi"


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / float(w.getframerate())


def durations(texts: list[str], out_dir: Path, voice: str = DEFAULT_VOICE,
              rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH,
              engine: str = "auto") -> tuple[list[float], str]:
    paths, used = synthesize(texts, out_dir, voice, rate, pitch, engine)
    return [wav_seconds(p) for p in paths], used


def build_track(shot_durations: list[float], audio_dir: Path, out_wav: Path) -> Path:
    """每镜一段语音，补齐到镜头时长后顺序拼接。"""
    parts: list[Path] = []
    for i, dur in enumerate(shot_durations, start=1):
        src = audio_dir / f"line{i}.wav"
        dst = audio_dir / f"pad{i}.wav"
        ff.run([
            ff.ffmpeg(), "-y", "-loglevel", "error", "-i", str(src),
            "-af", f"adelay={int(LEAD * 1000)}:all=1,apad",
            "-t", f"{dur:.3f}", "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(dst),
        ])
        parts.append(dst)

    lst = audio_dir / "concat.txt"
    # concat 列表里的相对路径是相对 list 文件所在目录解析的，必须写绝对路径
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    ff.run([ff.ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(lst), "-c:a", "pcm_s16le", str(out_wav)])
    return out_wav


def loudnorm_args() -> str:
    """抖音推荐约 -14 LUFS；给一个保守的归一化，避免忽大忽小。"""
    return "loudnorm=I=-14:TP=-1.5:LRA=11"
