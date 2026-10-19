"""校验引擎单元测试：必答、多选数量限制、字数、数字范围与整数约束、
以及"只校验实际到达的题目"（跳过的必答题不报错）。"""
from app.services.validator import validate_answer, validate_answers


def q(qtype, **kw):
    base = {"qid": "q1", "type": qtype, "title": "t", "required": False}
    base.update(kw)
    return base


class TestSingle:
    def test_ok(self):
        assert validate_answer(q("single", options=["男", "女"]), ["男"]) is None

    def test_must_choose_one(self):
        assert "1 个选项" in validate_answer(q("single", options=["男"]), ["男", "女"])

    def test_invalid_option(self):
        assert "不在允许范围" in validate_answer(q("single", options=["男"]), ["外星人"])

    def test_required_empty(self):
        assert validate_answer(q("single", required=True, options=["男"]), []) is not None
        assert validate_answer(q("single", required=False, options=["男"]), []) is None


class TestMultiple:
    def test_min_max(self):
        qq = q("multiple", options=["a", "b", "c"], min_select=2, max_select=2)
        assert validate_answer(qq, ["a"]) == "至少选择 2 个"
        assert validate_answer(qq, ["a", "b", "c"]) == "最多选择 2 个"
        assert validate_answer(qq, ["a", "b"]) is None

    def test_invalid_option(self):
        qq = q("multiple", options=["a", "b"], min_select=1)
        assert "无效选项" in validate_answer(qq, ["a", "z"])


class TestText:
    def test_length_limits(self):
        qq = q("text", text_min_len=2, text_max_len=5)
        assert "至少输入 2 个字" == validate_answer(qq, "好")
        assert "最多输入 5 个字" == validate_answer(qq, "一二三四五六")
        assert validate_answer(qq, "不错哦") is None


class TestNumber:
    def test_range_and_integer(self):
        qq = q("number", num_min=0, num_max=120, integer_only=True)
        assert "不能小于 0" == validate_answer(qq, "-5")
        assert "不能大于 120" == validate_answer(qq, "121")
        assert "必须为整数" == validate_answer(qq, "3.5")
        assert validate_answer(qq, "20") is None

    def test_not_a_number(self):
        assert "请输入数字" == validate_answer(q("number"), "abc")

    def test_float_allowed_when_not_integer_only(self):
        assert validate_answer(q("number", num_min=0), "3.5") is None


class TestVisitedFilter:
    def test_skipped_required_question_not_checked(self):
        """跳转导致 q2 被跳过：即使 q2 是必答题且没答案，也不报错。"""
        qs = [
            q("single", qid="q1", options=["a"], required=True),
            q("text", qid="q2", required=True),
            q("text", qid="q3"),
        ]
        errors = validate_answers(qs, {"q1": ["a"], "q3": "ok"}, {"q1", "q3"})
        assert errors == []

    def test_visited_required_missing_reported(self):
        qs = [
            q("single", qid="q1", options=["a"], required=True),
            q("text", qid="q2", required=True),
        ]
        errors = validate_answers(qs, {"q1": []}, {"q1", "q2"})
        assert len(errors) == 2
        assert {e["question_id"] for e in errors} == {"q1", "q2"}
