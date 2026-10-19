"""问卷管理接口：创建 / 列表 / 详情 / 保存（乐观锁）/ 发布 / 关闭。

- 登录用户只能操作自己创建的问卷（越权返回 403）
- PUT 保存携带 version 做乐观锁：版本不匹配返回 409
- 保存时执行结构校验 + 环检测（拒绝）+ 死题检测（返回 warnings）
"""
import secrets
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.db import stats as stats_col
from app.db import surveys as surveys_col
from app.deps import get_current_user
from app.models.schemas import SurveyCreate, SurveyUpdate
from app.services import jump_engine, stats_service

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


def _get_owned(survey_id: str, user: dict) -> dict:
    """取问卷并校验归属，非 owner 返回 403。"""
    try:
        oid = ObjectId(survey_id)
    except Exception:
        raise HTTPException(404, "问卷不存在")
    doc = surveys_col().find_one({"_id": oid})
    if doc is None:
        raise HTTPException(404, "问卷不存在")
    if doc["owner_id"] != user["_id"]:
        raise HTTPException(403, "无权访问该问卷")
    return doc


def _normalize_questions(questions: list[dict]) -> list[dict]:
    """重排 order、校验结构、环检测（拒绝）、死题检测（返回 warnings）。"""
    for i, q in enumerate(questions):
        q["order"] = i + 1
    errs = jump_engine.validate_structure(questions)
    if errs:
        raise HTTPException(400, "；".join(errs))
    cycles = jump_engine.find_cycles(questions)
    if cycles:
        cycle_path = " → ".join(cycles[0])
        raise HTTPException(400, f"跳转规则存在循环：{cycle_path}，请修改后再保存")
    warnings = jump_engine.find_unreachable(questions)
    return questions, warnings


def _iso(value):
    """datetime → ISO 字符串，保证 JSON 可序列化。"""
    return value.isoformat() if isinstance(value, datetime) else value


def _out(doc: dict) -> dict:
    """owner 视角的输出：ObjectId → str，附带统计总数。"""
    st = stats_col().find_one({"survey_id": doc["_id"]})
    total = st["total"] if st else 0
    return {
        "id": str(doc["_id"]),
        "title": doc["title"],
        "description": doc.get("description", ""),
        "allow_anonymous": doc.get("allow_anonymous", False),
        "allow_multiple_submissions": doc.get("allow_multiple_submissions", False),
        "status": doc["status"],
        "published_at": _iso(doc.get("published_at")),
        "deadline": _iso(doc.get("deadline")),
        "share_token": doc["share_token"],
        "share_url": f"/s/{doc['share_token']}",
        "version": doc["version"],
        "questions": doc["questions"],
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
        "response_total": total,
    }


@router.post("", status_code=201)
def create_survey(req: SurveyCreate, user: dict = Depends(get_current_user)):
    questions = [q.model_dump() for q in req.questions]
    questions, _ = _normalize_questions(questions)
    now = datetime.now(timezone.utc)
    doc = {
        "title": req.title,
        "description": req.description,
        "owner_id": user["_id"],
        "allow_anonymous": req.allow_anonymous,
        "allow_multiple_submissions": req.allow_multiple_submissions,
        "status": "draft",
        "published_at": None,
        "deadline": req.deadline,
        "share_token": secrets.token_urlsafe(6),
        "version": 1,
        "questions": questions,
        "created_at": now,
        "updated_at": now,
    }
    result = surveys_col().insert_one(doc)
    doc["_id"] = result.inserted_id
    stats_service.init_stats(doc)
    return _out(surveys_col().find_one({"_id": result.inserted_id}))


@router.get("")
def list_surveys(user: dict = Depends(get_current_user)):
    docs = surveys_col().find({"owner_id": user["_id"]}).sort("created_at", -1)
    return [_out(d) for d in docs]


@router.get("/{survey_id}")
def get_survey(survey_id: str, user: dict = Depends(get_current_user)):
    return _out(_get_owned(survey_id, user))


@router.put("/{survey_id}")
def update_survey(survey_id: str, req: SurveyUpdate, user: dict = Depends(get_current_user)):
    doc = _get_owned(survey_id, user)
    if req.version != doc["version"]:
        raise HTTPException(409, "问卷已被其他页面修改，请刷新后重试")

    questions = [q.model_dump() for q in req.questions]
    questions, warnings = _normalize_questions(questions)

    result = surveys_col().update_one(
        {"_id": doc["_id"], "version": req.version},
        {"$set": {
            "title": req.title,
            "description": req.description,
            "allow_anonymous": req.allow_anonymous,
            "allow_multiple_submissions": req.allow_multiple_submissions,
            "deadline": req.deadline,
            "questions": questions,
            "updated_at": datetime.now(timezone.utc),
        }, "$inc": {"version": 1}},
    )
    if result.matched_count == 0:
        raise HTTPException(409, "问卷已被其他页面修改，请刷新后重试")
    out = _out(surveys_col().find_one({"_id": doc["_id"]}))
    out["warnings"] = warnings
    return out


@router.post("/{survey_id}/publish")
def publish_survey(survey_id: str, user: dict = Depends(get_current_user)):
    doc = _get_owned(survey_id, user)
    if doc["status"] not in ("draft", "closed"):
        raise HTTPException(409, "当前状态不可发布")
    if not doc.get("questions"):
        raise HTTPException(400, "问卷至少需要一道题目才能发布")
    for question in doc["questions"]:
        if question["type"] in ("single", "multiple") and not question.get("options"):
            raise HTTPException(400, f"题目 {question['qid']} 至少需要一个选项")
        if not question.get("title", "").strip():
            raise HTTPException(400, f"第 {question.get('order', 0)} 题缺少题目内容")
    surveys_col().update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "published", "published_at": datetime.now(timezone.utc)}},
    )
    return _out(surveys_col().find_one({"_id": doc["_id"]}))


@router.post("/{survey_id}/close")
def close_survey(survey_id: str, user: dict = Depends(get_current_user)):
    doc = _get_owned(survey_id, user)
    if doc["status"] != "published":
        raise HTTPException(409, "当前状态不可关闭")
    surveys_col().update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": "closed"}},
    )
    return _out(surveys_col().find_one({"_id": doc["_id"]}))
