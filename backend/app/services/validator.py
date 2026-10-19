"""校验引擎：声明式约束 + 统一校验器。

约束全部来自题目文档字段（options/min_select/text_min_len/num_min...），
校验器只"解释"规则，不写死任何业务 —— 新题型只需增加规则条目。
只校验实际到达的题目（visited），被跳过的必答题不报错。
"""
import re
from math import isfinite
from typing import Any

_NUMBER_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def _num(text: Any) -> float | None:
    if isinstance(text, bool):
        return None
    if isinstance(text, str) and not _NUMBER_PATTERN.fullmatch(text.strip()):
        return None
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _is_integer_form(text: Any) -> bool:
    if isinstance(text, bool):
        return False
    if isinstance(text, str) and not _NUMBER_PATTERN.fullmatch(text.strip()):
        return False
    try:
        value = float(text)
    except (TypeError, ValueError):
        return False
    return isfinite(value) and value.is_integer()


def validate_answer(question: dict, answer: Any) -> str | None:
    """校验单个答案；合法返回 None，否则返回中文错误消息。"""
    qtype = question["type"]
    required = question.get("required", False)
    empty = answer is None or answer == "" or answer == []
    if empty:
        return "此题为必答题" if required else None

    if qtype == "single":
        if not isinstance(answer, list) or len(answer) != 1:
            return "单选题必须选择 1 个选项"
        if answer[0] not in question.get("options", []):
            return "选项不在允许范围内"

    elif qtype == "multiple":
        if not isinstance(answer, list):
            return "多选题答案格式错误"
        opts = question.get("options", [])
        if any(o not in opts for o in answer):
            return "包含无效选项"
        if len(answer) != len(set(answer)):
            return "不能重复选择同一选项"
        n = len(answer)
        mn = question.get("min_select", 1)
        mx = question.get("max_select")
        if n < mn:
            return f"至少选择 {mn} 个"
        if mx is not None and n > mx:
            return f"最多选择 {mx} 个"

    elif qtype == "text":
        if not isinstance(answer, str):
            return "填空题答案格式错误"
        n = len(answer)
        mn = question.get("text_min_len", 0)
        mx = question.get("text_max_len")
        if n < mn:
            return f"至少输入 {mn} 个字"
        if mx is not None and n > mx:
            return f"最多输入 {mx} 个字"

    elif qtype == "number":
        if not isinstance(answer, str):
            return "数字填空题答案格式错误"
        val = _num(answer)
        if val is None:
            return "请输入数字"
        if question.get("integer_only") and not _is_integer_form(answer):
            return "必须为整数"
        mn = question.get("num_min")
        mx = question.get("num_max")
        if mn is not None and val < mn:
            return f"不能小于 {mn:g}"
        if mx is not None and val > mx:
            return f"不能大于 {mx:g}"

    return None


def validate_answers(questions: list[dict], answers: dict, visited: set[str]) -> list[dict]:
    """校验所有实际到达的题目，返回 [{question_id, message}]（空列表表示通过）。"""
    errors: list[dict] = []
    for question in questions:
        qid = question["qid"]
        if qid not in visited:
            continue
        msg = validate_answer(question, answers.get(qid))
        if msg:
            errors.append({"question_id": qid, "message": msg})
    return errors
