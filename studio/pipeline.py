"""一条命令：script.json → 成片。

    python -m studio.pipeline examples/script-01.json

产物在 dist/<脚本名>/：
    video.mp4     1080x1920 / 30fps / H.264 / AAC
    cover_3x4.png 封面
    bgm.wav       自动合成的配乐（若启用）
    manifest.json 时间轴与字幕（给复盘和二次剪辑用）
    meta.json     标题、简介、话题、AI 标识、BGM 情绪
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from . import audio, bgm as bgm_mod, compliance, cover as cover_mod, ff, render, sfx as sfx_mod, stylelib, theme as th


def _prepare_assets(shots: list[dict], out: Path, fps: int) -> dict:
    """预处理 art / broll 的素材：裁切、风格化、抽帧。结果缓存在 assets 里。"""
    from PIL import Image

    from . import art as art_mod

    assets: dict = {}
    for s in shots:
        kind = s.get("type")

        # art 镜头可以只写 prompt，由即梦生成后再套风格
        if kind == "art" and not s.get("image") and s.get("prompt"):
            from . import imggen
            prompt = s["prompt"]
            # 风格库注入：把 341 条风格里的「风格提示词」拼进生图 prompt
            kw = s.get("style_keyword")
            if kw:
                hits = stylelib.search(kw)
                if hits:
                    extra = hits[0].get("prompt") or hits[0].get("look") or ""
                    if extra:
                        prompt = f"{prompt}。画风：{extra}"
                        print(f"风格注入：{hits[0]['title']} → {extra[:28]}…")
            try:
                paths = imggen.generate(prompt, s.get("gen_size", "720x1280"), 1,
                                        out_dir=out / "gen")
                s["image"] = str(paths[0])
                print(f"生图：{Path(paths[0]).name}")
            except SystemExit as exc:
                print(f"[警告] 生图失败，`art` 将退回占位框：{exc}")

        if kind == "art" and s.get("image"):
            p = Path(s["image"])
            if not p.exists():
                print(f"[警告] 图片不存在：{p}")
                continue
            style = s.get("style", "none")
            if style == "auto":
                kw = s.get("style_keyword")
                hits = stylelib.search(kw) if kw else []
                style = stylelib.treatment_for(hits[0]) if hits else "none"
                if hits:
                    print(f"风格：{hits[0]['title']} → 处理 {style}")
            key = f"art::{p}::{style}"
            if key not in assets:
                img = art_mod.cover_fit(Image.open(p), int(th.W * 1.08), int(th.H * 1.08),
                                        float(s.get("focus", 0.5)))
                assets[key] = art_mod.stylize(img, style)
            s["_asset_key"] = key

        elif kind == "broll" and s.get("video"):
            p = Path(s["video"])
            if not p.exists():
                print(f"[警告] 视频不存在：{p}")
                continue
            key = f"vid::{p}"
            if key not in assets:
                assets[key] = art_mod.extract_frames(p, out / "broll", (th.W, th.H), fps)
            s["_asset_key"] = key
    return assets


def _bgm_filter(total: float) -> str:
    fade_out = max(0.5, total - 2.0)
    return (f"volume=0.16,lowpass=f=5200,"
            f"afade=t=in:st=0:d=1.2,afade=t=out:st={fade_out:.2f}:d=2")


def build(
    script_path: Path,
    out_root: Path | None = None,
    silent: bool = False,
    keep_frames: bool = False,
    force: bool = False,
    no_bgm: bool = False,
    voice: str | None = None,
) -> Path:
    t_start = time.time()
    script = render.load_script(script_path)
    name = script.get("name") or script_path.stem
    out = (out_root or script_path.parent.parent / "dist") / name

    # 1) 合规检查（先做，避免白渲染）
    ok, findings = compliance.report(script)
    blocks = [f for f in findings if f.severity == "block"]
    warns = [f for f in findings if f.severity == "warn"]
    for f in findings:
        mark = "阻断" if f.severity == "block" else "提醒"
        print(f"[{mark}] {f.category} · {f.match} @ {f.where}\n        {f.advice}")
    if blocks and not force:
        raise SystemExit(f"\n有 {len(blocks)} 处阻断项，未渲染。确认要发就加 --force，并自行承担平台风险。")

    # 1.5) 脚本闸门（内容分，不达标默认只告警）
    gate = None
    try:
        from ops import gates as gate_mod
        gate = gate_mod.check(script)
        print(f"脚本评分：{gate['score']}/{gate['max']}"
              + ("" if gate["pass"] else f"（低于 {gate['threshold']}，建议重写）"))
        if gate["fails"]:
            print("  待改：" + "；".join(gate["fails"]))
    except Exception as exc:  # 没装 ops 包也不该挡住渲染
        print(f"[跳过] 脚本闸门不可用：{exc}")

    if gate and not gate["pass"] and (force or script.get("strict_gates")):
        raise SystemExit(f"\n脚本评分 {gate['score']}/{gate['max']} 未达阈值，未渲染。"
                         f"改完再跑，或加 --force 强行出片。")

    out.mkdir(parents=True, exist_ok=True)
    frames_dir = out / "frames"
    audio_dir = out / "audio"

    # 2) 配音
    shots = script["shots"]
    engine = script.get("tts_engine", "auto")
    if silent:
        speech = [max(1.2, len(s.get("say") or "") * 0.16) for s in shots]
        used_engine = "silent"
        print(f"静音模式：按字数估算时长 {sum(speech):.1f}s")
    else:
        texts = [(s.get("say") or "").strip() for s in shots]
        missing = [i + 1 for i, t in enumerate(texts) if not t]
        if missing:
            raise SystemExit(f"第 {missing} 镜没有 say（口播文本），配音模式需要它；或用 --silent")
        speech, used_engine = audio.durations(
            texts, audio_dir,
            voice or script.get("voice", audio.DEFAULT_VOICE),
            script.get("rate", audio.DEFAULT_RATE),
            script.get("pitch", audio.DEFAULT_PITCH),
            engine,
        )
        print(f"配音引擎：{used_engine}")

    durations, starts, subs = render.plan_timeline(script, speech, audio.LEAD, audio.TAIL)
    total = sum(durations)
    print(f"时长 {total:.2f}s / {len(shots)} 镜")

    # 3) BGM：默认 auto，按文案情绪合成
    bgm_path: Path | None = None
    bgm_info: dict | None = None
    spec = script.get("bgm", "auto")
    if no_bgm or spec in (None, False, "none", "off"):
        pass
    elif spec == "auto" or spec is True:
        bgm_info = bgm_mod.for_script({**script, "_total_seconds": total}, total, out / "bgm.wav")
        bgm_path = Path(bgm_info["file"])
        print(f"BGM：{bgm_info['mood']} @ {bgm_info['bpm']} BPM（{bgm_info['reason']['scores']}）")
    elif isinstance(spec, str) and spec in bgm_mod.MOODS:
        # 直接指定情绪：不猜了，按名字合成
        bgm_info = bgm_mod.compose(spec, total, out / "bgm.wav")
        bgm_info["reason"] = {"forced": True}
        bgm_path = Path(bgm_info["file"])
        print(f"BGM：{spec} @ {bgm_info['bpm']} BPM（手动指定）")
    else:
        cand = Path(spec)
        if cand.exists():
            bgm_path = cand
            bgm_info = {"mood": "custom", "file": str(cand)}
        else:
            print(f"[警告] bgm 指定的文件不存在：{cand}，本次不配乐")

    # 4) 渲染帧（先预处理图片/视频素材）
    fps = int(script.get("fps", th.FPS))
    assets = _prepare_assets(shots, out, fps)
    n = render.render_frames(script, durations, starts, subs, frames_dir, assets)
    print(f"渲染 {n} 帧，用时 {time.time() - t_start:.0f}s")

    # 5) 音轨：人声 + 音效（+ 可选 BGM）
    track = None if silent else audio.build_track(durations, audio_dir, out / "voice.wav")

    sfx_path: Path | None = None
    sfx_info: dict | None = None
    if script.get("sfx", True) and not silent:
        sfx_info = sfx_mod.build(durations, starts, shots, out / "sfx.wav",
                                 drone=float(script.get("sfx_drone", 1.0)))
        sfx_path = Path(sfx_info["file"])
        print(f"音效：{sfx_info['events']} 个事件")

    # 6) 合成
    mp4 = out / "video.mp4"
    args = [ff.ffmpeg(), "-y", "-loglevel", "error",
            "-framerate", str(script.get("fps", th.FPS)), "-i", str(frames_dir / "%05d.png")]
    idx = 1
    voice_idx = bgm_idx = sfx_idx = None
    if track:
        args += ["-i", str(track)]
        voice_idx = idx
        idx += 1
    if bgm_path:
        args += ["-i", str(bgm_path)]
        bgm_idx = idx
        idx += 1
    if sfx_path:
        args += ["-i", str(sfx_path)]
        sfx_idx = idx
        idx += 1

    args += ["-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart"]

    # 分层混音：人声做 loudnorm，BGM 压低并低通，音效保持清晰
    layers: list[str] = []
    if voice_idx is not None:
        layers.append(f"[{voice_idx}:a]{audio.loudnorm_args()}[v]")
    if bgm_idx is not None:
        layers.append(f"[{bgm_idx}:a]{_bgm_filter(total)}[bg]")
    if sfx_idx is not None:
        layers.append(f"[{sfx_idx}:a]volume=0.9[fx]")

    if len(layers) >= 2:
        labels = "".join("[" + n_ + "]" for n_ in ("v", "bg", "fx")[:len(layers)])
        fc = ";".join(layers) + (
            f";{labels}amix=inputs={len(layers)}:duration=first:dropout_transition=0:"
            f"normalize=0,alimiter=limit=0.95[a]")
        args += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]"]
    elif voice_idx is not None:
        args += ["-af", audio.loudnorm_args(), "-map", "0:v", "-map", f"{voice_idx}:a"]
    elif bgm_idx is not None:
        args += ["-af", "volume=0.35", "-map", "0:v", "-map", f"{bgm_idx}:a"]
    elif sfx_idx is not None:
        args += ["-af", "volume=0.55", "-map", "0:v", "-map", f"{sfx_idx}:a"]
    else:
        args += ["-map", "0:v"]

    args += ["-c:a", "aac", "-b:a", "160k", "-ar", "44100", str(mp4)]
    ff.run(args)

    # 7) 封面与元数据
    covers = cover_mod.build(script, out)
    manifest = render.write_manifest(out / "manifest.json", script, durations, starts, subs, n)
    meta = {
        "title": script.get("title"),
        "desc": script.get("desc", ""),
        "tags": script.get("tags", []),
        "ai_generated": script.get("ai_generated", True),
        "duration": round(total, 3),
        "size": [th.W, th.H],
        "fps": script.get("fps", th.FPS),
        "tts_engine": used_engine,
        "voice": audio.resolve_voice(voice or script.get("voice", audio.DEFAULT_VOICE)),
        "bgm": bgm_info,
        "sfx": sfx_info,
        "video": str(mp4.resolve()),
        "cover_3x4": str(Path(covers["cover_3x4"]).resolve()),
        "cover_9x16": str(Path(covers["cover_9x16"]).resolve()),
        "manifest": str(manifest.resolve()),
        "compliance": {"blocked": bool(blocks), "warnings": len(warns),
                       "items": [f.as_dict() for f in findings]},
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    mp = out / "meta.json"
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    if not keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)

    dur = ff.probe_duration(mp4)
    print(f"\n完成：{mp4}")
    print(f"  {mp4.stat().st_size / 1024 / 1024:.1f} MB · {dur:.2f}s · {th.W}x{th.H}")
    print(f"  封面：{covers['cover_3x4']}")
    print(f"  元数据：{mp}")
    return mp4


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="竖屏短视频渲染器")
    ap.add_argument("script", type=Path, help="script.json 路径")
    ap.add_argument("--out", type=Path, default=None, help="产物根目录（默认 script 同级 dist/）")
    ap.add_argument("--silent", action="store_true", help="跳过 TTS，按字数估时长（快速看画面）")
    ap.add_argument("--keep-frames", action="store_true", help="保留 PNG 帧，便于检查")
    ap.add_argument("--force", action="store_true", help="忽略合规阻断项")
    ap.add_argument("--no-bgm", action="store_true", help="不配乐")
    ap.add_argument("--voice", default=None, help="覆盖音色：narrator / anchor / warm / lively / passion")
    a = ap.parse_args(argv)
    build(a.script, a.out, a.silent, a.keep_frames, a.force, a.no_bgm, a.voice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
