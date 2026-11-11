"""读音校正：同音替换、数字读法、高危字告警。"""
from studio import pronounce as p


def test_fix_replaces_polyphone_phrase():
    safe, applied = p.fix("这个行业不好做")
    assert safe == "这个航业不好做"
    assert applied and applied[0]["phrase"] == "行业"


def test_fix_keeps_original_meaning_words():
    """只换同音字，不换词义。"""
    safe, _ = p.fix("我重新做一遍")
    assert "虫新" in safe and "重" not in safe


def test_fix_percent_to_chinese():
    safe, _ = p.fix("完播率 36%")
    assert "百分之三十六" in safe


def test_fix_multiple_rules_in_one_sentence():
    safe, applied = p.fix("行业里的人都在还价")
    assert "航业" in safe and "环价" in safe
    assert len(applied) >= 2


def test_fix_no_rule_returns_same_text():
    safe, applied = p.fix("今天天气不错")
    assert safe == "今天天气不错"
    assert applied == []


def test_check_reports_rules_and_risks():
    items = p.check("这个行业的行长")
    kinds = {i["type"] for i in items}
    assert "rule" in kinds


def test_check_clean_text():
    assert p.check("今天天气不错") == []


def test_num_cn_basics():
    assert p._num_cn(0) == "零"
    assert p._num_cn(10) == "十"
    assert p._num_cn(36) == "三十六"
    assert p._num_cn(1712) == "一千七百一十二"
    assert p._num_cn(1000) == "一千"
    assert p._num_cn(10000) == "一万"


def test_describe_shape():
    d = p.describe()
    assert d["rules"] > 20 and d["risk_chars"] > 0
