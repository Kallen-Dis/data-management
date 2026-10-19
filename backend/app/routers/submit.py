"""填写端接口：按 share_token 访问问卷、查看状态、提交答卷。

提交流程（全部服务端强校验，前端校验只是体验优化）：
1. 问卷状态 = published，且未过截止时间；
2. 非匿名问卷必须登录；匿名问卷通过 anon_id 去重；
3. 跳转引擎 simulate_flow 得到实际到达的题目（visited）；
4. 校验引擎只校验 visited 题目的答案；
5. 构造问卷快照（snapshot）+ 答案，单文档原子插入 responses；
6. 唯一索引 {survey_id, respondent_key} 原子防重复提交；
7. stats $inc 原子更新计数。
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from app.db import responses as responses_col
from app.db import surveys as surveys_col
from app.deps import get_optional_user
from app.models.schemas import SubmitRequest
from app.services import jump_engine, stats_service, validator

router = APIRouter(prefix="/api/s", tags=["fill"])


def _find_by_token(token: str) -> dict:
    doc = surveys_col().find_one({"share_token": token})
    if doc is None:
        raise HTTPException(404, "问卷不存在")
    return doc


def _as_utc(dt) -> datetime | None:
    """MongoDB 读回的 datetime 是 naive 的（无时区），统一转成 UTC 感知时间再比较。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fill_view(s: dict) -> dict:
    """填写端看到的问卷：题目含约束与跳转规则（前端据此镜像跳转体验）。"""
    return {
        "title": s["title"],
        "description": s.get("description", ""),
        "allow_anonymous": s.get("allow_anonymous", False),
        "questions": [
            {
                "qid": q["qid"],
                "type": q["type"],
                "title": q["title"],
                "required": q.get("required", False),
                "options": q.get("options", []),
                "min_select": q.get("min_select", 1),
                "max_select": q.get("max_select"),
                "text_min_len": q.get("text_min_len", 0),
                "text_max_len": q.get("text_max_len"),
                "num_min": q.get("num_min"),
                "num_max": q.get("num_max"),
                "integer_only": q.get("integer_only", False),
                "jump_rules": q.get("jump_rules", []),
            }
            for q in s["questions"]
        ],
    }


@router.get("/{token}")
def get_survey_for_fill(token: str, user: dict | None = Depends(get_optional_user)):
    s = _find_by_token(token)
    if s["status"] != "published":
        raise HTTPException(403, "问卷未发布或已关闭")
    deadline = _as_utc(s.get("deadline"))
    if deadline is not None and datetime.now(timezone.utc) > deadline:
        raise HTTPException(403, "问卷已截止")
    # 非匿名问卷：未登录不允许看到题目（登录限制不只是提交时）
    if not s.get("allow_anonymous", False) and user is None:
        raise HTTPException(401, "此问卷需要登录后填写")
    return _fill_view(s)


@router.get("/{token}/status")
def survey_status(token: str):
    s = _find_by_token(token)
    deadline = _as_utc(s.get("deadline"))
    expired = deadline is not None and datetime.now(timezone.utc) > deadline
    return {
        "title": s["title"],
        "status": s["status"],
        "expired": expired,
        "can_submit": s["status"] == "published" and not expired,
        "allow_anonymous": s.get("allow_anonymous", False),
        "allow_multiple_submissions": s.get("allow_multiple_submissions", False),
        "deadline": s.get("deadline"),
    }


@router.post("/{token}/responses", status_code=201)
def submit_response(token: str, req: SubmitRequest,
                    user: dict | None = Depends(get_optional_user)):
    s = _find_by_token(token)

    # ---- 1. 服务端强校验 ----
    if s["status"] != "published":
        raise HTTPException(403, "问卷未发布或已关闭")
    deadline = _as_utc(s.get("deadline"))
    if deadline is not None and datetime.now(timezone.utc) > deadline:
        raise HTTPException(403, "问卷已截止，无法提交")
    if not s.get("allow_anonymous", False) and user is None:
        raise HTTPException(401, "此问卷需要登录后填写")

    # ---- 2. 跳转引擎：得到实际到达的题目 ----
    visited = jump_engine.simulate_flow(s["questions"], req.answers)
    visited_set = set(visited)

    # ---- 3. 校验引擎：只校验实际到达的题 ----
    errors = validator.validate_answers(s["questions"], req.answers, visited_set)
    if errors:
        raise HTTPException(422, errors)

    # 只保存实际到达题目的答案（防止恶意提交未到达题目的答案）
    saved_answers = {k: v for k, v in req.answers.items() if k in visited_set}

    # ---- 4. 重复提交去重键 ----
    if not s.get("allow_multiple_submissions", False):
        if user is not None:
            respondent_key = "u:" + str(user["_id"])
        else:
            if not req.anon_id:
                raise HTTPException(400, "缺少匿名标识，请刷新页面后重试")
            respondent_key = "a:" + req.anon_id
    else:
        respondent_key = "free:" + secrets.token_hex(8)

    # ---- 5. 问卷快照：提交瞬间的题目结构 ----
    snapshot = {
        "title": s["title"],
        "questions": [
            {"qid": q["qid"], "type": q["type"], "title": q["title"],
             "options": q.get("options", [])}
            for q in s["questions"]
        ],
    }

    resp_doc = {
        "survey_id": s["_id"],
        "survey_version": s["version"],
        "snapshot": snapshot,
        "answers": saved_answers,
        "respondent": {
            "user_id": user["_id"] if user else None,
            "username": user["username"] if user else None,
            "anon_id": req.anon_id,
        },
        "respondent_key": respondent_key,
        "submitted_at": datetime.now(timezone.utc),
        "spent_seconds": req.spent_seconds,
    }
    stats_service.ensure_stats_version(s["_id"])
    try:
        responses_col().insert_one(resp_doc)
    except DuplicateKeyError:
        raise HTTPException(409, "你已经提交过这份问卷")

    # ---- 6. 预聚合计数：$inc 原子更新 ----
    stats_service.apply_submission(s, saved_answers, visited)

    return {"ok": True, "visited": visited, "submitted_at": resp_doc["submitted_at"]}
