"""合规检查：该拦的拦，不该拦的别误伤。"""
from studio import compliance as cc


def _script(**kw):
    base = {"title": "", "desc": "", "tags": [], "ai_generated": True, "shots": []}
    base.update(kw)
    return base


def test_absolute_claim_blocks():
    ok, findings = cc.report(_script(title="全网最好的不锈钢盆"))
    assert not ok
    assert any(f.severity == "block" and f.category == "绝对化用语" for f in findings)


def test_efficacy_claim_blocks():
    ok, findings = cc.report(_script(shots=[{"type": "hook", "say": "这个盆能抑菌杀菌"}]))
    assert not ok
    assert any(f.category == "功效宣称" for f in findings)


def test_missing_ai_flag_blocks():
    ok, findings = cc.report(_script(ai_generated=False, title="普通标题"))
    assert not ok
    assert any(f.category == "AI 标识" for f in findings)


def test_clean_script_passes():
    ok, findings = cc.report(_script(
        title="我不吃饭，但我卖装饭的盆",
        desc="第一条正式视频，零条作品，第一个产品是不锈钢盆。",
        shots=[{"type": "hook", "say": "我不吃饭，但我卖装饭的盆。"}],
    ))
    assert ok, [f.as_dict() for f in findings]


def test_first_product_not_flagged():
    """「第一个产品」不是绝对化用语，不能被误伤。"""
    ok, _ = cc.report(_script(title="第一个产品：不锈钢盆"))
    assert ok


def test_offsite_warns_not_blocks():
    ok, findings = cc.report(_script(desc="想买的加微信"))
    assert ok  # warn 不阻断
    assert any(f.category == "站外导流" and f.severity == "warn" for f in findings)
