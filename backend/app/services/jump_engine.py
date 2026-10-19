"""跳转引擎：把问卷建模为有向图。

- 节点 = 题目；边 = 跳转规则（goto）+ 顺序边（下一题）
- 执行：next_question / simulate_flow（返回实际到达的题目序列）
- 静态分析：find_cycles（DFS 三色标记）、find_unreachable（可达性分析）、
  validate_structure（qid 唯一、跳转目标存在）

跳转规则数据驱动：规则存在题目文档里，引擎只负责"解释算子"，绝不硬编码业务。
"""
import re
from math import isfinite
from typing import Any

_NUMBER_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def _num(a: Any) -> float | None:
    if isinstance(a, bool):
        return None
    if isinstance(a, str) and not _NUMBER_PATTERN.fullmatch(a.strip()):
        return None
    try:
        value = float(a)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _eq(rule_value: Any, answer: Any) -> bool:
    if isinstance(answer, list):
        return rule_value in answer
    answer_number = _num(answer)
    rule_number = _num(rule_value)
    if answer_number is not None and rule_number is not None:
        return answer_number == rule_number
    return answer == rule_value


def _count_gt(rule_value: Any, answer: Any) -> bool:
    threshold = _num(rule_value)
    return isinstance(answer, list) and threshold is not None and len(answer) > threshold


def _count_eq(rule_value: Any, answer: Any) -> bool:
    threshold = _num(rule_value)
    return isinstance(answer, list) and threshold is not None and len(answer) == threshold


def _in_range(rule_value: Any, answer: Any) -> bool:
    value = _num(answer)
    if value is None or not isinstance(rule_value, (list, tuple)) or len(rule_value) != 2:
        return False
    lower, upper = (_num(bound) for bound in rule_value)
    return lower is not None and upper is not None and lower <= value <= upper


def _compare(rule_value: Any, answer: Any, predicate) -> bool:
    threshold = _num(rule_value)
    value = _num(answer)
    return threshold is not None and value is not None and predicate(value, threshold)


# 条件算子表：op 名称 → 判断函数(规则值 rule_val, 答案 answer)
# eq       单选选中某选项 / 数字等于某值
# contains 多选包含某选项
# count_gt / count_eq  多选选中数量大于 / 等于
# gt / lt / range      数字填空大于 / 小于 / 在区间内
OPS = {
    "eq": _eq,
    "contains": lambda rv, a: isinstance(a, list) and rv in a,
    "count_gt": _count_gt,
    "count_eq": _count_eq,
    "gt": lambda rv, a: _compare(rv, a, lambda value, threshold: value > threshold),
    "lt": lambda rv, a: _compare(rv, a, lambda value, threshold: value < threshold),
    "range": _in_range,
}

OPS_BY_TYPE = {
    "single": {"eq"},
    "multiple": {"contains", "count_gt", "count_eq"},
    "number": {"gt", "lt", "eq", "range"},
    "text": set(),
}


def _ordered(questions: list[dict]) -> list[dict]:
    """按 order 排序题目（order 由后端在保存时按顺序重排）。"""
    return sorted(questions, key=lambda q: q.get("order", 0))


def match_rule(question: dict, answer: Any) -> str | None:
    """依次求值该题的跳转规则，返回第一条命中的 goto；无命中返回 None。"""
    for rule in question.get("jump_rules", []):
        op = rule.get("when", {}).get("op")
        value = rule.get("when", {}).get("value")
        fn = OPS.get(op)
        if fn is not None and fn(value, answer):
            return rule["goto"]
    return None


def next_question(questions: list[dict], current_qid: str, answers: dict) -> str | None:
    """返回下一题 qid；规则命中则跳转，否则顺序下一题；已到末尾返回 None。"""
    ordered = _ordered(questions)
    for i, q in enumerate(ordered):
        if q["qid"] != current_qid:
            continue
        goto = match_rule(q, answers.get(current_qid))
        if goto:
            return goto
        return ordered[i + 1]["qid"] if i + 1 < len(ordered) else None
    return None


def simulate_flow(questions: list[dict], answers: dict) -> list[str]:
    """模拟整卷流程，返回实际到达的题目序列（visited）。

    visited 有两个用途：
    1. 校验器只校验实际到达的题（被跳过的必答题不报错）；
    2. 提交时只保存实际到达题目的答案。
    """
    ordered = _ordered(questions)
    if not ordered:
        return []
    by_qid = {q["qid"]: q for q in ordered}
    visited: list[str] = []
    seen: set[str] = set()
    current: str | None = ordered[0]["qid"]
    while current is not None and current not in seen:
        seen.add(current)
        visited.append(current)
        current = next_question(ordered, current, answers)
        if current is not None and current not in by_qid:
            current = None  # 跳转目标不存在：终止（结构校验会先行拦截）
    return visited


# ---------- 静态分析（创建/保存问卷时使用） ----------

def _edges(questions: list[dict]) -> dict[str, set[str]]:
    """构造邻接表：跳转边 + 顺序边（顺序边仅在跳转规则不"必然命中"时有效）。"""
    ordered = _ordered(questions)
    by_qid = {q["qid"]: q for q in ordered}
    edges: dict[str, set[str]] = {q["qid"]: set() for q in ordered}
    for i, q in enumerate(ordered):
        for rule in q.get("jump_rules", []):
            goto = rule.get("goto")
            if goto in by_qid:
                edges[q["qid"]].add(goto)  # 含自环：交给环检测报告
        if not _always_jumps(q) and i + 1 < len(ordered):
            edges[q["qid"]].add(ordered[i + 1]["qid"])
    return edges


def _always_jumps(q: dict) -> bool:
    """判断该题的跳转规则是否"必然命中"。

    精确规则（单选）：每个选项都有对应的 eq 规则 → 无论选什么都会跳走，
    此时顺序边无效。其他题型保守处理（顺序边有效）。
    """
    rules = q.get("jump_rules", [])
    if not rules:
        return False
    if q.get("type") == "single":
        covered = {r.get("when", {}).get("value") for r in rules
                   if r.get("when", {}).get("op") == "eq"}
        options = set(q.get("options", []))
        return bool(options) and options <= covered
    return False


def find_cycles(questions: list[dict]) -> list[list[str]]:
    """用非递归 DFS 三色标记找环，返回可读的环路径。"""
    edges = _edges(questions)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {qid: WHITE for qid in edges}
    cycles: list[list[str]] = []
    for root in edges:
        if color[root] != WHITE:
            continue
        path = [root]
        path_index = {root: 0}
        color[root] = GRAY
        frames = [(root, iter(edges.get(root, ())))]
        while frames:
            node, neighbors = frames[-1]
            nxt = next(neighbors, None)
            if nxt is None:
                frames.pop()
                color[node] = BLACK
                path.pop()
                path_index.pop(node, None)
            elif color[nxt] == WHITE:
                color[nxt] = GRAY
                path_index[nxt] = len(path)
                path.append(nxt)
                frames.append((nxt, iter(edges.get(nxt, ()))))
            elif color[nxt] == GRAY:
                cycles.append(path[path_index[nxt]:] + [nxt])
    return cycles


def find_unreachable(questions: list[dict]) -> list[str]:
    """从第一题出发做可达性分析，返回永远无法到达的题目 qid 列表。"""
    ordered = _ordered(questions)
    if not ordered:
        return []
    edges = _edges(questions)
    reachable: set[str] = {ordered[0]["qid"]}
    queue = [ordered[0]["qid"]]
    cursor = 0
    while cursor < len(queue):
        cur = queue[cursor]
        cursor += 1
        for nxt in edges.get(cur, ()):
            if nxt not in reachable:
                reachable.add(nxt)
                queue.append(nxt)
    return [q["qid"] for q in ordered if q["qid"] not in reachable]


def validate_structure(questions: list[dict]) -> list[str]:
    """校验题目标识、选项和跳转规则，返回错误消息列表。"""
    errors: list[str] = []
    qids = [q["qid"] for q in questions]
    if len(set(qids)) != len(qids):
        errors.append("题目 qid 重复")
    by_qid = set(qids)
    for q in questions:
        qid = q["qid"]
        qtype = q.get("type")
        options = q.get("options", [])
        if qtype in ("single", "multiple"):
            if any(not isinstance(option, str) or not option.strip() for option in options):
                errors.append(f"题目 {qid} 的选项不能为空")
            elif options and len(set(options)) != len(options):
                errors.append(f"题目 {qid} 存在重复选项")
        if qtype == "multiple":
            minimum = q.get("min_select", 1)
            maximum = q.get("max_select")
            if minimum < 0 or minimum > len(options) or (maximum is not None and (maximum < minimum or maximum > len(options))):
                errors.append(f"题目 {qid} 的多选数量限制无效")
        if qtype == "text":
            minimum = q.get("text_min_len", 0)
            maximum = q.get("text_max_len")
            if minimum < 0 or (maximum is not None and maximum < minimum):
                errors.append(f"题目 {qid} 的字数限制无效")
        if qtype == "number":
            minimum = q.get("num_min")
            maximum = q.get("num_max")
            if (minimum is not None and _num(minimum) is None) or (maximum is not None and _num(maximum) is None):
                errors.append(f"题目 {qid} 的数值范围无效")
            elif minimum is not None and maximum is not None and minimum > maximum:
                errors.append(f"题目 {qid} 的数值范围无效")
        for rule in q.get("jump_rules", []):
            if rule.get("goto") not in by_qid:
                errors.append(f"题目 {qid} 的跳转目标 {rule.get('goto')} 不存在")
            condition = rule.get("when") or {}
            op = condition.get("op")
            value = condition.get("value")
            if not isinstance(op, str) or op not in OPS_BY_TYPE.get(qtype, set()):
                errors.append(f"题目 {qid} 不支持跳转条件 {op}")
                continue
            if op in {"eq", "contains"} and qtype != "number" and value not in options:
                errors.append(f"题目 {qid} 的跳转选项不存在")
            elif op in {"count_gt", "count_eq"} or (
                qtype == "number" and op in {"gt", "lt", "eq"}
            ):
                numeric_value = _num(value)
                if numeric_value is None or (op.startswith("count_") and not numeric_value.is_integer()):
                    errors.append(f"题目 {qid} 的跳转阈值无效")
            elif op == "range":
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    errors.append(f"题目 {qid} 的跳转区间无效")
                else:
                    lower, upper = (_num(bound) for bound in value)
                    if lower is None or upper is None or lower > upper:
                        errors.append(f"题目 {qid} 的跳转区间无效")
    return errors
