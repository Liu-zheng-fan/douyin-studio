"""环境自检：一次性回答「这台机器现在能不能出片」。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from studio import ff, theme  # noqa: E402


def check_fonts() -> dict:
    missing = [p for p in (theme.FONT_BOLD, theme.FONT_REG) if not Path(p).exists()]
    return {"name": "中文字体", "ok": not missing, "missing": missing}


def check_ffmpeg() -> dict:
    try:
        exe = ff.ffmpeg()
        out = subprocess.run([exe, "-version"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.splitlines()
        return {"name": "ffmpeg", "ok": True, "path": exe, "version": out[0] if out else ""}
    except SystemExit as exc:
        return {"name": "ffmpeg", "ok": False, "error": str(exc)}


def check_tts() -> dict:
    # 主引擎：edge-tts（需联网）；备用：SAPI
    try:
        import edge_tts  # noqa: F401
        edge_ok = True
        edge_err = None
    except Exception as exc:
        edge_ok = False
        edge_err = str(exc)

    ps = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
($s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'zh*' } |
  ForEach-Object { $_.VoiceInfo.Name }) -join ','
"""
    import base64
    enc = base64.b64encode(ps.encode("utf-16-le")).decode()
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        sapi = [v.strip() for v in r.stdout.strip().split(",") if v.strip()]
    except Exception:
        sapi = []

    return {"name": "配音", "ok": edge_ok or bool(sapi),
            "edge_tts": edge_ok, "edge_error": edge_err,
            "sapi_voices": sapi,
            "note": "edge-tts 需联网；失败会自动降级到 SAPI"}


def check_example() -> dict:
    p = ROOT / "examples" / "script-01.json"
    if not p.exists():
        return {"name": "示例脚本", "ok": False, "error": "examples/script-01.json 缺失"}
    data = json.loads(p.read_text(encoding="utf-8"))
    types = [s.get("type") for s in data.get("shots", [])]
    from studio.shots import SHOTS
    unknown = [t for t in types if t not in SHOTS]
    return {"name": "示例脚本", "ok": not unknown, "shots": len(types), "unknown": unknown}


def check_dirs() -> dict:
    ok = True
    detail = {}
    for p in (ROOT / "dist", ROOT / "ops"):
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            detail[str(p)] = "writable"
        except Exception as exc:
            ok = False
            detail[str(p)] = f"不可写：{exc}"
    return {"name": "输出目录", "ok": ok, "detail": detail}


def main() -> int:
    checks = [check_fonts(), check_ffmpeg(), check_tts(), check_example(), check_dirs()]
    ok = all(c["ok"] for c in checks)
    print(json.dumps({"ok": ok, "root": str(ROOT), "checks": checks}, ensure_ascii=False, indent=2))
    if not ok:
        print("\n有未通过的项：按上面的 missing / error 补齐即可。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
