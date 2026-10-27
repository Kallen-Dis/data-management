"""统计引擎：双通道设计。

快通道（写时预聚合）：提交答卷时用 $inc 原子更新 stats 文档，统计页 O(1) 读取。
慢通道（快照重建）：rebuild_stats 基于 responses 的问卷快照全量重建，
用于兜底与校验 —— 报告里对比"空间换时间 vs 实时计算"两种方案。

统计值设计：
- 单选/多选：题目 ID 和选项文本经 SHA-256 摘要后用作字段键，标签单独保存，
  避免字段名非法并保证统计不受选项顺序变化影响。
- 数字题：num_sum / num_count，平均值 = sum / count。
"""
import re
from hashlib import sha256
from math import isfinite
from time import sleep
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db import responses as responses_col
from app.db import stats as stats_col

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


def _stable_key(value: Any) -> str:
    digest = sha256(str(value).encode("utf-8")).hexdigest()
    return f"k_{digest}"


def init_stats(survey: dict):
    """创建问卷时初始化 stats 文档（total=0）。"""
    try:
        stats_col().insert_one({"survey_id": survey["_id"], "total": 0, "questions": {}, "revision": 0, "stats_version": 2})
    except DuplicateKeyError:
        pass  # 已存在则忽略（upsert 语义）


def _option_index(q: dict, opt: str) -> int | None:
    try:
        return q["options"].index(opt)
    except ValueError:
        return None


def _inc_paths(survey: dict, answers: dict, visited: list[str]) -> dict[str, float | int]:
    """构造 $inc 更新字典：total + 每题选项计数 / 数字和。"""
    inc: dict[str, float | int] = {"total": 1}
    by_qid = {q["qid"]: q for q in survey["questions"]}
    for qid in visited:
        q = by_qid.get(qid)
        answer = answers.get(qid)
        if q is None or answer in (None, "", []):
            continue
        if q["type"] == "single" and isinstance(answer, list) and answer:
            idx = _option_index(q, answer[0])
            if idx is not None:
                inc[f"questions.{_stable_key(qid)}.counts.{_stable_key(answer[0])}"] = 1
        elif q["type"] == "multiple" and isinstance(answer, list):
            for opt in answer:
                idx = _option_index(q, opt)
                if idx is not None:
                    inc[f"questions.{_stable_key(qid)}.counts.{_stable_key(opt)}"] = 1
        elif q["type"] == "number":
            val = _num(answer)
            if val is not None:
                inc[f"questions.{_stable_key(qid)}.num_sum"] = val
                inc[f"questions.{_stable_key(qid)}.num_count"] = 1
    return inc


def _option_label_paths(survey: dict) -> dict[str, str]:
    """Keep labels beside hashed option keys so renamed choices remain reportable."""
    labels: dict[str, str] = {}
    for question in survey["questions"]:
        if question["type"] not in ("single", "multiple"):
            continue
        question_key = _stable_key(question["qid"])
        for option in question.get("options", []):
            labels[f"questions.{question_key}.labels.{_stable_key(option)}"] = option
    return labels


def apply_submission(survey: dict, answers: dict, visited: list[str], expected_revision: int | None = None):
    """提交后原子更新 stats（$inc 单文档原子操作，并发不丢数）。"""
    inc = _inc_paths(survey, answers, visited)
    inc["revision"] = 1
    if expected_revision is None:
        return rebuild_stats(survey["_id"])
    result = stats_col().update_one(
        {"survey_id": survey["_id"], "revision": expected_revision},
        {"$inc": inc, "$set": {**_option_label_paths(survey), "stats_version": 2}},
    )
    if not result.matched_count:
        return rebuild_stats(survey["_id"])


def ensure_stats_version(survey_id: ObjectId):
    current = stats_col().find_one({"survey_id": survey_id})
    if current and current.get("total", 0) and current.get("stats_version") != 2:
        rebuild_stats(survey_id)
        current = stats_col().find_one({"survey_id": survey_id})
    return current.get("revision", 0) if current else 0


def _read_counts(counts, options: list[str]) -> list[int]:
    """读取稳定摘要键，并兼容旧版数字下标统计文档。"""
    out = []
    for i, option in enumerate(options):
        if isinstance(counts, dict):
            out.append(counts.get(_stable_key(option), counts.get(str(i), 0)))
        else:
            out.append(counts[i] if i < len(counts) else 0)
    return out


def get_stats_view(survey: dict) -> dict:
    """快通道：读取预聚合文档，组装前端可直接渲染的统计视图。"""
    s = stats_col().find_one({"survey_id": survey["_id"]})
    response_count = responses_col().count_documents({"survey_id": survey["_id"]})
    if (s is None and response_count) or (s and (s.get("total", 0) != response_count or s.get("stats_version") != 2)):
        rebuild_stats(survey["_id"])
        s = stats_col().find_one({"survey_id": survey["_id"]})
    base = s if s else {"total": 0, "questions": {}}
    view = {
        "survey_id": str(survey["_id"]),
        "title": survey["title"],
        "total": base.get("total", 0),
        "questions": [],
    }
    for q in survey["questions"]:
        questions = base.get("questions", {})
        qs = questions.get(_stable_key(q["qid"]), questions.get(q["qid"], {}))
        item = {
            "qid": q["qid"],
            "type": q["type"],
            "title": q["title"],
            "options": q.get("options", []),
        }
        if q["type"] in ("single", "multiple"):
            current_options = q.get("options", [])
            labels = qs.get("labels", {})
            historical_options = [value for value in labels.values() if value not in current_options]
            item["options"] = current_options + historical_options
            item["counts"] = _read_counts(qs.get("counts", {}), item["options"])
        elif q["type"] == "number":
            total_sum = qs.get("num_sum", 0)
            total_cnt = qs.get("num_count", 0)
            item["num_sum"] = total_sum
            item["num_count"] = total_cnt
            item["avg"] = round(total_sum / total_cnt, 2) if total_cnt else None
        view["questions"].append(item)
    return view


def rebuild_stats(survey_id: ObjectId) -> dict:
    """慢通道：基于 responses 的问卷快照全量重建 stats 并覆盖写入。"""
    for attempt in range(8):
        current = stats_col().find_one({"survey_id": survey_id})
        revision = current.get("revision", 0) if current else 0
        docs = list(responses_col().find({"survey_id": survey_id}))
        qstats: dict[str, dict] = {}
        for doc in docs:
            snap_qs = {q["qid"]: q for q in doc.get("snapshot", {}).get("questions", [])}
            for qid, answer in doc.get("answers", {}).items():
                q = snap_qs.get(qid)
                if q is None or answer in (None, "", []):
                    continue
                stat = qstats.setdefault(_stable_key(qid), {})
                if q["type"] in ("single", "multiple"):
                    opts = q.get("options", [])
                    labels = stat.setdefault("labels", {})
                    for option in opts:
                        labels[_stable_key(option)] = option
                    counts: dict = stat.setdefault("counts", {})
                    vals = answer if isinstance(answer, list) else [answer]
                    for value in vals:
                        if value in opts:
                            key = _stable_key(value)
                            counts[key] = counts.get(key, 0) + 1
                elif q["type"] == "number":
                    value = _num(answer)
                    if value is not None:
                        stat["num_sum"] = stat.get("num_sum", 0) + value
                        stat["num_count"] = stat.get("num_count", 0) + 1
        new_doc = {
            "survey_id": survey_id,
            "total": len(docs),
            "questions": qstats,
            "revision": revision + 1,
            "stats_version": 2,
        }
        revision_filter = (
            {"survey_id": survey_id, "revision": revision}
            if current and "revision" in current
            else {"survey_id": survey_id, "revision": {"$exists": False}}
        )
        if current and stats_col().replace_one(revision_filter, new_doc).matched_count:
            return {"total": len(docs)}
        if not current:
            try:
                stats_col().insert_one(new_doc)
                return {"total": len(docs)}
            except DuplicateKeyError:
                pass
        if attempt < 7:
            sleep(0.01 * (attempt + 1))
    raise RuntimeError("统计重建期间数据持续变化，请稍后重试")
