"""音效合成：事件映射、非静音、时长对齐。"""
import wave

import numpy as np

from studio import sfx


def test_events_for_maps_shot_types():
    shots = [{"type": "hook"}, {"type": "number"}, {"type": "cta"}]
    starts = [0.0, 3.0, 8.0]
    durs = [3.0, 5.0, 2.0]
    ev = sfx.events_for(durs, starts, shots)
    names = [e[1] for e in ev]
    assert "bloom" in names          # hook
    assert "tock" in names           # number
    assert "chord" in names          # cta
    assert all(0 <= e[0] <= sum(durs) + 0.01 for e in ev)


def test_synth_is_audible_and_bounded():
    events = [(0.5, "thud", {"gain": 1.0}), (1.5, "tick", {"pitch": 3})]
    x = sfx.synth(events, 3.0)
    assert x.shape[1] == 2
    assert np.abs(x).max() > 0.01
    assert np.abs(x).max() <= 1.0


def test_synth_length_matches_duration():
    x = sfx.synth([], 2.0)
    assert abs(len(x) / sfx.SR - 2.05) < 0.1


def test_unknown_event_is_ignored():
    x = sfx.synth([(0.2, "no_such_event", {})], 1.0)
    assert np.abs(x).max() <= 1.0


def test_hush_creates_silence(tmp_path):
    loud = [(0.1, "thud", {"gain": 1.0})]
    quiet = loud + [(0.8, "hush", {"dur": 1.2})]
    a = sfx.synth(quiet, 2.2)
    i = int(1.4 * sfx.SR)
    assert np.abs(a[i:i + int(0.3 * sfx.SR)]).max() < np.abs(sfx.synth(loud, 2.2)[i:i + int(0.3 * sfx.SR)]).max()


def test_build_writes_playable_wav(tmp_path):
    out = tmp_path / "sfx.wav"
    info = sfx.build([2.0, 3.0], [0.0, 2.0], [{"type": "hook"}, {"type": "cta"}], out)
    assert out.exists()
    assert info["events"] >= 2
    with wave.open(str(out)) as w:
        assert w.getnchannels() == 2
        assert w.getframerate() == sfx.SR
        assert w.getnframes() > 0
