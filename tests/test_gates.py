"""脚本闸门：分数要能反映真实问题，不能什么都给过。"""
from ops import gates


def _script(**kw):
    base = {
        "hook_type": "反常识",
        "golden": "我不吃饭，但我卖装饭的盆",
        "shots": [
            {"type": "hook", "say": "我不吃饭，但我卖装饭的盆。", "text": ["我不吃饭"]},
            {"type": "number", "say": "到现在，一条作品都没发。", "value": 0},
            {"type": "line", "say": "我不会吃饭，所以得靠它吃饭。", "a": "A", "b": "B"},
            {"type": "cta", "say": "关注我，看我第几天开张。", "text": ["看我能撑几天"]},
            {"type": "split", "say": "不给谁打工，自己挣口白饭。", "a": "上班", "b": "自己干"},
        ],
    }
    base.update(kw)
    return base


def test_good_script_passes():
    r = gates.check(_script())
    assert r["pass"] is True, r["fails"]
    assert r["score"] >= gates.PASS_SCORE


def test_missing_hook_fails():
    s = _script()
    s["shots"][0]["type"] = "bullets"
    r = gates.check(s)
    assert r["score"] < gates.check(_script())["score"]
    assert any("hook" in f for f in r["fails"])


def test_banal_sentence_penalised():
    s = _script()
    s["shots"][1]["say"] = "在这个时代，让我们一起看看。"
    r = gates.check(s)
    assert not r["pass"] or r["score"] < gates.check(_script())["score"]
    assert any("万能句" in f for f in r["fails"])


def test_long_sentences_penalised():
    s = _script()
    s["shots"][1]["say"] = "这是一个特别特别长的口播句子它应该被扣分因为它超过了十八个字的限制"
    r = gates.check(s)
    item = next(d for d in r["detail"] if d["item"].startswith("口播句"))
    assert item["score"] < item["max"]
    assert "超长" in item["note"]
    assert r["score"] < gates.check(_script())["score"]


def test_missing_golden_penalised():
    s = _script()
    del s["golden"]
    r = gates.check(s)
    assert any("金句" in f for f in r["fails"])


def test_unknown_hook_type_rejected():
    s = _script(hook_type="随便写的")
    r = gates.check(s)
    assert any("钩子类型" in f for f in r["fails"])


def test_score_never_exceeds_max():
    r = gates.check(_script())
    assert 0 <= r["score"] <= gates.MAX_SCORE
