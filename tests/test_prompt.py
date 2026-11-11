"""结构化提示词：槽位、预设、负面压制。"""
from studio import prompt as p


def test_build_contains_all_slots():
    s = p.build("一只鲸鱼少女", action="端着不锈钢盆", scene="浅灰背景", style="flat")
    for token in ("鲸鱼少女", "端着不锈钢盆", "浅灰背景", "扁平插画", "居中", "竖版"):
        assert token in s, token


def test_style_preset_switches_wording():
    a = p.build("盆", style="product")
    b = p.build("盆", style="cute")
    assert "产品摄影" in a and "Q 版" in b
    assert a != b


def test_avoid_list_always_present():
    s = p.build("任意主体")
    assert "不要：" in s
    assert "文字" in s


def test_empty_optional_slots_do_not_leave_double_commas():
    s = p.build("主体")
    assert "，，" not in s and "，。" not in s


def test_composition_keyword_mapping():
    assert "主体偏左" in p.build("x", composition="left")
    assert "特写" in p.build("x", composition="closeup")


def test_unknown_style_falls_back_to_flat():
    s = p.build("x", style="no_such_style")
    assert "扁平插画" in s


def test_describe_shape():
    d = p.describe()
    assert "flat" in d["presets"] and d["slots"][0] == "主体"


def test_horizontal_option():
    assert "竖版构图" not in p.build("x", vertical=False)
