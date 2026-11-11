"""统一 CLI：新 Agent 的第一道门，必须稳。"""
import json

from douyin import cli, schema


def test_status_shape(monkeypatch):
    st = cli.status()
    assert st["root"]
    assert "imggen" in st and "pending" in st and "ledger" in st
    assert isinstance(st["pending"], list)
    assert st["next"]


def test_schema_describe_mentions_all_shots():
    from studio.shots import SHOTS
    text = schema.describe()
    for kind in SHOTS:
        assert f"`{kind}`" in text


def test_validate_good_example():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    r = schema.validate(root / "examples" / "script-04.json")
    assert r["ok"] is True, r["errors"]


def test_validate_reports_precise_errors(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"title": "", "shots": [{"type": "art"}, {"type": "nope"}]},
                              ensure_ascii=False), encoding="utf-8")
    r = schema.validate(bad)
    assert r["ok"] is False
    wheres = {e["where"] for e in r["errors"]}
    assert "title" in wheres
    assert "ai_generated" in wheres
    assert "shots[1].type" in wheres


def test_validate_broken_json(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{ not json", encoding="utf-8")
    r = schema.validate(p)
    assert r["ok"] is False
    assert "JSON" in r["errors"][0]["message"]


def test_cli_help_exits_zero(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "status" in out and "build" in out


def test_cli_unknown_command():
    assert cli.main(["nope"]) == 2
