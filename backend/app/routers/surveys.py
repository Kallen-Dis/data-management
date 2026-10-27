"""问卷管理接口：创建 / 列表 / 详情 / 保存（乐观锁）/ 发布 / 关闭。

- 登录用户只能操作自己创建的问卷（越权返回 403）
- PUT 保存携带 version 做乐观锁：版本不匹配返回 409
- 保存时执行结构校验 + 环检测（拒绝）+ 死题检测（返回 warnings）
"""
import secrets
from copy import deepcopy
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.db import stats as stats_col
from app.db import surveys as surveys_col
from app.db import users as users_col
from app.db import question_series
from app.deps import get_current_user
from app.models.schemas import StatsSharingUpdate, SurveyCreate, SurveyUpdate
from app.serialization import json_value
from app.services import jump_engine, question_service, stats_service

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


def _locked(document):
    return bool(document.get("ever_published") or document.get("published_at") or document["status"] in ("published", "closed"))


def _write_filter(document):
    return {"_id": document["_id"], "version": document["version"], "status": document["status"],
        "ever_published": document.get("ever_published") if "ever_published" in document else {"$exists": False}}


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
        "questions": json_value(doc["questions"]),
        "ever_published": _locked(doc),
        "schema_version": doc.get("schema_version", 1),
        "question_stats_shares": json_value(doc.get("question_stats_shares", [])),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
        "response_total": total,
    }


@router.post("", status_code=201)
def create_survey(req: SurveyCreate, user: dict = Depends(get_current_user)):
    questions = question_service.resolve_instances([question.model_dump(exclude_unset=True) for question in req.questions], user)
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
        "schema_version": 2,
        "ever_published": False,
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

    questions = question_service.resolve_instances([question.model_dump(exclude_unset=True) for question in req.questions], user, doc)
    questions, warnings = _normalize_questions(questions)
    if _locked(doc) and questions != doc["questions"]:
        raise HTTPException(409, "已发布问卷的题目结构已锁定，请复制为新草稿后修改")

    result = surveys_col().update_one(
        _write_filter(doc),
        {"$set": {
            "title": req.title,
            "description": req.description,
            "allow_anonymous": req.allow_anonymous,
            "allow_multiple_submissions": req.allow_multiple_submissions,
            "deadline": req.deadline,
            "questions": questions,
            "schema_version": 2,
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
    questions, _ = _normalize_questions(deepcopy(doc["questions"]))
    sealed = question_service.seal_instances({**doc, "questions": questions}, user)
    result = surveys_col().update_one(
        _write_filter(doc),
        {"$set": {"status": "published", "published_at": doc.get("published_at") or datetime.now(timezone.utc),
            "ever_published": True, "questions": sealed, "schema_version": 2, "updated_at": datetime.now(timezone.utc)}, "$inc": {"version": 1}},
    )
    if result.matched_count != 1:
        raise HTTPException(409, "问卷已发生变化，请刷新后重新发布")
    return _out(surveys_col().find_one({"_id": doc["_id"]}))


@router.post("/{survey_id}/close")
def close_survey(survey_id: str, user: dict = Depends(get_current_user)):
    doc = _get_owned(survey_id, user)
    if doc["status"] != "published":
        raise HTTPException(409, "当前状态不可关闭")
    result = surveys_col().update_one(
        _write_filter(doc),
        {"$set": {"status": "closed", "ever_published": True, "updated_at": datetime.now(timezone.utc)}, "$inc": {"version": 1}},
    )
    if result.matched_count != 1:
        raise HTTPException(409, "问卷已发生变化，请刷新后重试")
    return _out(surveys_col().find_one({"_id": doc["_id"]}))


@router.post("/{survey_id}/clone", status_code=201)
def clone_survey(survey_id: str, user: dict = Depends(get_current_user)):
    source = _get_owned(survey_id, user)
    questions = question_service.resolve_instances(json_value(source["questions"]), user)
    timestamp = datetime.now(timezone.utc)
    document = {"title": (source["title"][:90] + "（副本）"), "description": source.get("description", ""), "owner_id": user["_id"],
        "questions": questions, "allow_anonymous": source.get("allow_anonymous", False), "allow_multiple_submissions": source.get("allow_multiple_submissions", False),
        "deadline": None, "status": "draft", "published_at": None, "ever_published": False, "version": 1,
        "schema_version": 2, "share_token": secrets.token_urlsafe(9), "created_at": timestamp, "updated_at": timestamp}
    document["_id"] = surveys_col().insert_one(document).inserted_id
    stats_service.init_stats(document)
    return _out(document)


@router.post("/{survey_id}/questions/{qid}/library")
def save_question_to_library(survey_id: str, qid: str, user: dict = Depends(get_current_user)):
    document = _get_owned(survey_id, user)
    question = next((item for item in document["questions"] if item["qid"] == qid), None)
    if question is None:
        raise HTTPException(404, "题目不存在")
    if question.get("question_version_id"):
        version, series = question_service.get_version(question["question_version_id"], user)
        if series["owner_id"] == user["_id"]:
            question_series().update_one({"_id": series["_id"]}, {"$set": {"listed": True, "updated_at": datetime.now(timezone.utc)}, "$inc": {"revision": 1}})
            series = question_service.raw_series(series["_id"])
    else:
        series, version = question_service.create_series(question, user)
        questions = deepcopy(document["questions"])
        for item in questions:
            if item["qid"] == qid:
                item.update({"question_series_id": series["_id"], "question_version_id": version["_id"]})
        if surveys_col().update_one(_write_filter(document), {"$set": {"questions": questions, "schema_version": 2}, "$inc": {"version": 1}}).matched_count != 1:
            raise HTTPException(409, "题目已存入题目中心，但问卷已变化，请刷新后选用")
    return {"question": question_service.series_view(series, user), "survey": _out(_get_owned(survey_id, user))}


@router.put("/{survey_id}/question-stats-sharing")
def set_question_stats_sharing(survey_id: str, request: StatsSharingUpdate, user: dict = Depends(get_current_user)):
    document = _get_owned(survey_id, user)
    allowed_versions = {question.get("question_version_id") for question in document["questions"] if question.get("question_version_id")}
    grants = []
    for grant in request.grants:
        version = question_service.raw_version(grant.question_version_id)
        recipient = users_col().find_one({"username": grant.username})
        if version["_id"] not in allowed_versions:
            raise HTTPException(400, "只能授权此问卷实际使用的题目版本")
        if recipient is None:
            raise HTTPException(404, "被授权用户不存在")
        item = {"question_version_id": version["_id"], "grantee_id": recipient["_id"], "username": recipient["username"], "permission": "aggregate"}
        if item not in grants:
            grants.append(item)
    if surveys_col().update_one({"_id": document["_id"], "version": request.version}, {"$set": {"question_stats_shares": grants}, "$inc": {"version": 1}}).matched_count != 1:
        raise HTTPException(409, "问卷已更新，请刷新后重试")
    return _out(_get_owned(survey_id, user))
