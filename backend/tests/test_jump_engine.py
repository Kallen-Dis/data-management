"""跳转引擎单元测试（纯函数，不依赖数据库）。

覆盖任务书要求：根据单选结果跳转、根据多选结果跳转、根据数字填空内容跳转、
无命中顺序走、环检测、死题目检测。
"""
from app.services.jump_engine import (
    find_cycles,
    find_unreachable,
    next_question,
    simulate_flow,
    validate_structure,
)


def make_q(qid, qtype="single", order=None, options=None, rules=None):
    return {
        "qid": qid,
        "type": qtype,
        "title": qid,
        "required": False,
        "order": order or int(qid[1:]),
        "options": options or [],
        "jump_rules": rules or [],
    }


class TestNextQuestion:
    def test_single_eq_jump(self):
        qs = [
            make_q("q1", options=["男", "女"],
                   rules=[{"when": {"op": "eq", "value": "男"}, "goto": "q3"},
                          {"when": {"op": "eq", "value": "女"}, "goto": "q2"}]),
            make_q("q2"), make_q("q3"),
        ]
        assert next_question(qs, "q1", {"q1": ["男"]}) == "q3"
        assert next_question(qs, "q1", {"q1": ["女"]}) == "q2"

    def test_no_match_goes_next(self):
        qs = [make_q("q1"), make_q("q2"), make_q("q3")]
        assert next_question(qs, "q1", {"q1": ["男"]}) == "q2"
        assert next_question(qs, "q3", {"q3": ["x"]}) is None

    def test_multiple_contains(self):
        qs = [
            make_q("q1", "multiple", options=["苹果", "香蕉"],
                   rules=[{"when": {"op": "contains", "value": "苹果"}, "goto": "q5"}]),
            make_q("q2"), make_q("q3"), make_q("q4"), make_q("q5"),
        ]
        assert next_question(qs, "q1", {"q1": ["苹果", "香蕉"]}) == "q5"
        assert next_question(qs, "q1", {"q1": ["香蕉"]}) == "q2"

    def test_multiple_count_gt(self):
        qs = [
            make_q("q1", "multiple", options=["a", "b", "c"],
                   rules=[{"when": {"op": "count_gt", "value": 2}, "goto": "q4"}]),
            make_q("q2"), make_q("q3"), make_q("q4"),
        ]
        assert next_question(qs, "q1", {"q1": ["a", "b", "c"]}) == "q4"
        assert next_question(qs, "q1", {"q1": ["a"]}) == "q2"

    def test_number_range_jump(self):
        qs = [
            make_q("q1", "number",
                   rules=[{"when": {"op": "gt", "value": 18}, "goto": "q4"},
                          {"when": {"op": "range", "value": [0, 18]}, "goto": "q2"}]),
            make_q("q2"), make_q("q3"), make_q("q4"),
        ]
        assert next_question(qs, "q1", {"q1": "20"}) == "q4"
        assert next_question(qs, "q1", {"q1": "10"}) == "q2"


class TestSimulateFlow:
    def test_visited_skips_jumped_questions(self):
        """选男：q1 → q3（跳过 q2）→ q4。"""
        qs = [
            make_q("q1", options=["男", "女"],
                   rules=[{"when": {"op": "eq", "value": "男"}, "goto": "q3"}]),
            make_q("q2"), make_q("q3"), make_q("q4"),
        ]
        visited = simulate_flow(qs, {"q1": ["男"], "q3": ["x"], "q4": ["y"]})
        assert visited == ["q1", "q3", "q4"]

    def test_cycle_protection(self):
        """人为构造循环规则，simulate 必须在重复访问时终止，不死循环。"""
        qs = [
            make_q("q1", options=["a"], rules=[{"when": {"op": "eq", "value": "a"}, "goto": "q2"}]),
            make_q("q2", options=["b"], rules=[{"when": {"op": "eq", "value": "b"}, "goto": "q1"}]),
        ]
        visited = simulate_flow(qs, {"q1": ["a"], "q2": ["b"]})
        assert visited == ["q1", "q2"]


class TestStaticAnalysis:
    def test_find_cycles_two_nodes(self):
        qs = [
            make_q("q1", options=["a"], rules=[{"when": {"op": "eq", "value": "a"}, "goto": "q2"}]),
            make_q("q2", options=["b"], rules=[{"when": {"op": "eq", "value": "b"}, "goto": "q1"}]),
        ]
        assert find_cycles(qs) == [["q1", "q2", "q1"]]

    def test_find_self_cycle(self):
        qs = [make_q("q1", options=["a"], rules=[{"when": {"op": "eq", "value": "a"}, "goto": "q1"}]),
              make_q("q2")]
        assert find_cycles(qs) == [["q1", "q1"]]

    def test_find_unreachable_dead_question(self):
        """单选覆盖全部选项且都跳走 → 顺序边失效 → 中间题永远不可达。"""
        qs = [
            make_q("q1", options=["a", "b"],
                   rules=[{"when": {"op": "eq", "value": "a"}, "goto": "q3"},
                          {"when": {"op": "eq", "value": "b"}, "goto": "q3"}]),
            make_q("q2"),  # 死题目
            make_q("q3"),
        ]
        assert find_unreachable(qs) == ["q2"]

    def test_no_dead_question_when_partial_jump(self):
        """只覆盖部分选项 → 顺序边仍有效 → 无死题目。"""
        qs = [
            make_q("q1", options=["a", "b"],
                   rules=[{"when": {"op": "eq", "value": "a"}, "goto": "q3"}]),
            make_q("q2"),
            make_q("q3"),
        ]
        assert find_unreachable(qs) == []

    def test_validate_structure(self):
        bad = [make_q("q1", rules=[{"when": {"op": "eq", "value": "a"}, "goto": "qX"}]),
               make_q("q2")]
        errs = validate_structure(bad)
        assert any("qX" in e for e in errs)
        assert validate_structure([make_q("q1"), make_q("q2")]) == []

    def test_validate_string_eq_and_numeric_eq_rules(self):
        questions = [
            make_q("q1", options=["男", "女"],
                   rules=[{"when": {"op": "eq", "value": "男"}, "goto": "q2"}]),
            make_q("q2", "number",
                   rules=[{"when": {"op": "eq", "value": 18}, "goto": "q3"}]),
            make_q("q3"),
        ]
        assert validate_structure(questions) == []
