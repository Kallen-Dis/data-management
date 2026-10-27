from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256

from bson import ObjectId
from fastapi import HTTPException
from pydantic import ValidationError
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.db import question_series, question_versions, surveys, users
from app.models.schemas import QuestionContent
from app.serialization import document_view, object_id
from app.services import jump_engine

CONTENT_FIELDS = tuple(QuestionContent.model_fields)


def now():
    return datetime.now(timezone.utc)


def content_from(question):
    try:
        return QuestionContent.model_validate({key: question[key] for key in CONTENT_FIELDS if key in question}).model_dump()
    except ValidationError:
        raise HTTPException(400, "题目缺少有效题型或题干")


def validate_content(content, complete=True):
    normalized = content_from(content)
    errors = jump_engine.validate_structure([{**normalized, "qid": "template", "jump_rules": []}])
    if complete and not normalized["title"].strip():
        errors.append("题干不能为空")
    if complete and normalized["type"] in ("single", "multiple") and not normalized["options"]:
        errors.append("选择题至少需要一个选项")
    if errors:
        raise HTTPException(400, "；".join(errors))
    return normalized


def raw_series(series_id):
    document = question_series().find_one({"_id": object_id(series_id, "题目不存在")})
    if document is None:
        raise HTTPException(404, "题目不存在")
    return document


def owned_series(series_id, user):
    document = raw_series(series_id)
    if document["owner_id"] != user["_id"]:
        raise HTTPException(403, "只有题目所有者可以执行此操作")
    return document


def raw_version(version_id):
    document = question_versions().find_one({"_id": object_id(version_id, "题目版本不存在")})
    if document is None:
        raise HTTPException(404, "题目版本不存在")
    return document


def grant_for(series, user):
    return next((grant for grant in series.get("shared_with", []) if grant["user_id"] == user["_id"]), None)


def version_allowed(version, series, user, for_use=False):
    if for_use and version.get("content_completeness") == "snapshot_only":
        return False
    if series["owner_id"] == user["_id"]:
        return not (for_use and series.get("archived_at"))
    grant = grant_for(series, user)
    if grant and not series.get("archived_at") and (grant.get("all_versions") or version["_id"] in grant.get("version_ids", [])):
        return True
    if for_use:
        return False
    return surveys().find_one({"$or": [
        {"owner_id": user["_id"], "questions.question_version_id": version["_id"]},
        {"question_stats_shares": {"$elemMatch": {"grantee_id": user["_id"], "question_version_id": version["_id"], "permission": "aggregate"}}},
    ]}, {"_id": 1}) is not None


def get_version(version_id, user, for_use=False):
    version = raw_version(version_id)
    series = raw_series(version["series_id"])
    if not version_allowed(version, series, user, for_use):
        raise HTTPException(403, "无权使用此题目版本" if for_use else "无权查看此题目版本")
    return version, series


def series_view(series, user):
    versions = [version for version in question_versions().find({"series_id": series["_id"]}).sort("version_no", -1)
                if version_allowed(version, series, user)]
    if not versions and series["owner_id"] != user["_id"]:
        raise HTTPException(403, "无权查看此题目")
    owner = users().find_one({"_id": series["owner_id"]}, {"username": 1})
    result = document_view({key: value for key, value in series.items() if key not in ("shared_with", "draft", "origin_key")})
    result.update({"owner_username": owner["username"] if owner else "历史用户", "can_manage": series["owner_id"] == user["_id"],
                   "versions": [{**document_view(version), "can_use": version_allowed(version, series, user, for_use=True)} for version in versions]})
    if series["owner_id"] != user["_id"] and versions:
        result["name"] = versions[0]["content"]["title"]
    result["default_version_id"] = str(series["default_version_id"]) if any(version["_id"] == series.get("default_version_id") for version in versions) else (str(versions[0]["_id"]) if versions else None)
    if result["can_manage"]:
        result["draft"] = document_view(series)["draft"] if series.get("draft") else None
        result["shared_with"] = []
        for grant in series.get("shared_with", []):
            recipient = users().find_one({"_id": grant["user_id"]}, {"username": 1})
            result["shared_with"].append({"user_id": str(grant["user_id"]), "username": recipient["username"] if recipient else "已删除用户",
                "version_ids": [str(value) for value in grant.get("version_ids", [])], "all_versions": grant.get("all_versions", False), "allow_fork": grant.get("allow_fork", True)})
    return result


def create_series(content, user, tags=None, change_note="初始版本", listed=True, origin_key=None, completeness="complete", derived_from=None):
    normalized = validate_content(content, complete=completeness == "complete")
    if completeness == "snapshot_only":
        normalized = {key: normalized[key] for key in ("type", "title", "options")}
    series_id = ObjectId(sha256(origin_key.encode()).hexdigest()[:24]) if origin_key else ObjectId()
    version_id = ObjectId(sha256((origin_key + ":v1").encode()).hexdigest()[:24]) if origin_key else ObjectId()
    timestamp = now()
    series = {"_id": series_id, "owner_id": user["_id"], "name": normalized["title"], "tags": tags or [],
        "default_version_id": None, "next_version_no": 1, "revision": 1, "listed": listed,
        "shared_with": [], "archived_at": None, "created_at": timestamp, "updated_at": timestamp}
    if origin_key:
        series["origin_key"] = origin_key
    try:
        question_series().insert_one(series)
    except DuplicateKeyError:
        series = question_series().find_one({"_id": series_id})
        if series is None or series["owner_id"] != user["_id"]:
            raise HTTPException(409, "题目来源冲突")
    version = {"_id": version_id, "series_id": series_id, "version_no": 1, "parent_version_id": None,
        "restored_from_version_id": None, "derived_from_version_id": derived_from, "created_by": user["_id"],
        "created_at": timestamp, "change_note": change_note, "content": normalized, "content_completeness": completeness}
    try:
        question_versions().insert_one(version)
    except DuplicateKeyError:
        version = raw_version(version_id)
    question_series().update_one({"_id": series_id, "default_version_id": None}, {"$set": {"default_version_id": version_id}})
    return raw_series(series_id), version


def add_version(series_id, content, parent_version_id, expected_revision, user, change_note="", restored_from=None):
    series = owned_series(series_id, user)
    if series.get("archived_at"):
        raise HTTPException(409, "题目已归档，请先恢复题目")
    parent = raw_version(parent_version_id)
    if parent["series_id"] != series["_id"]:
        raise HTTPException(400, "父版本不属于此题目")
    normalized = validate_content(content)
    reserved = question_series().find_one_and_update(
        {"_id": series["_id"], "revision": expected_revision, "archived_at": None},
        {"$inc": {"revision": 1, "next_version_no": 1}, "$set": {"updated_at": now()}}, return_document=ReturnDocument.AFTER)
    if reserved is None:
        raise HTTPException(409, "题目已更新，请刷新后重试")
    version = {"_id": ObjectId(), "series_id": series["_id"], "version_no": reserved["next_version_no"],
        "parent_version_id": parent["_id"], "restored_from_version_id": restored_from, "derived_from_version_id": None,
        "created_by": user["_id"], "created_at": now(), "change_note": change_note, "content": normalized, "content_completeness": "complete"}
    question_versions().insert_one(version)
    question_series().update_one({"_id": series["_id"], "revision": reserved["revision"]},
        {"$set": {"default_version_id": version["_id"], "name": normalized["title"]}, "$unset": {"draft": ""}})
    return version


def resolve_instances(incoming, user, previous=None):
    previous_by_qid = {question["qid"]: question for question in (previous or {}).get("questions", [])}
    resolved = []
    for question in incoming:
        instance = {"qid": question["qid"], "required": question.get("required", False), "order": question.get("order", 0), "jump_rules": question.get("jump_rules", [])}
        old = previous_by_qid.get(question["qid"], {})
        version_id = question.get("question_version_id")
        if not version_id and old.get("question_version_id"):
            if content_from(question) != content_from(old):
                raise HTTPException(409, "已保存版本不可覆盖，请先创建新版本或改用临时题目")
            version_id = old["question_version_id"]
        if version_id:
            retained = old.get("question_version_id") and str(old["question_version_id"]) == str(version_id)
            version = raw_version(version_id) if retained else get_version(version_id, user, for_use=True)[0]
            if question.get("question_series_id") and str(question["question_series_id"]) != str(version["series_id"]):
                raise HTTPException(400, "题目与版本来源不匹配")
            for field in CONTENT_FIELDS:
                if field in question and question[field] is not None and question[field] != version["content"].get(field):
                    raise HTTPException(409, "正式版本内容不可修改，请创建新版本后替换")
            resolved.append({**deepcopy(version["content"]), **instance, "question_series_id": version["series_id"], "question_version_id": version["_id"]})
        else:
            if question.get("question_series_id"):
                raise HTTPException(400, "缺少具体题目版本")
            resolved.append({**content_from(question), **instance})
    return resolved


def seal_instances(survey, user):
    result = []
    for question in survey["questions"]:
        if question.get("question_version_id"):
            result.append(deepcopy(question))
            continue
        series, version = create_series(question, user, listed=False,
            origin_key=f"survey:{survey['_id']}:revision:{survey['version']}:question:{question['qid']}")
        result.append({**deepcopy(question), "question_series_id": series["_id"], "question_version_id": version["_id"]})
    return result


def update_metadata(series_id, request, user):
    series = owned_series(series_id, user)
    changes = {"updated_at": now()}
    for field in ("name", "tags", "listed"):
        if getattr(request, field) is not None:
            changes[field] = getattr(request, field)
    if request.archived is not None:
        changes["archived_at"] = now() if request.archived else None
    if question_series().update_one({"_id": series["_id"], "revision": request.revision}, {"$set": changes, "$inc": {"revision": 1}}).matched_count != 1:
        raise HTTPException(409, "题目已更新，请刷新后重试")
    return series_view(raw_series(series_id), user)


def save_share(series_id, request, user):
    series = owned_series(series_id, user)
    recipient = users().find_one({"username": request.username})
    if recipient is None:
        raise HTTPException(404, "接收用户不存在")
    if recipient["_id"] == user["_id"]:
        raise HTTPException(400, "无需分享给自己")
    version_ids = [object_id(value) for value in request.version_ids]
    if not request.all_versions and not version_ids:
        raise HTTPException(400, "请选择至少一个版本")
    if question_versions().count_documents({"_id": {"$in": version_ids}, "series_id": series["_id"]}) != len(set(version_ids)):
        raise HTTPException(400, "分享版本不属于此题目")
    grants = [grant for grant in series.get("shared_with", []) if grant["user_id"] != recipient["_id"]]
    grants.append({"user_id": recipient["_id"], "version_ids": list(dict.fromkeys(version_ids)), "all_versions": request.all_versions, "allow_fork": request.allow_fork})
    if question_series().update_one({"_id": series["_id"], "revision": request.expected_revision}, {"$set": {"shared_with": grants, "updated_at": now()}, "$inc": {"revision": 1}}).matched_count != 1:
        raise HTTPException(409, "分享设置已变化，请刷新后重试")
    return series_view(raw_series(series_id), user)


def usages(series_id, user, version_id=None):
    series = raw_series(series_id)
    visible = series_view(series, user)
    allowed_ids = [object_id(version["id"]) for version in visible["versions"]]
    if version_id:
        version, _ = get_version(version_id, user)
        if version["series_id"] != series["_id"]:
            raise HTTPException(400, "版本不属于此题目")
        allowed_ids = [version["_id"]]
    documents = surveys().find({"owner_id": user["_id"], "questions.question_version_id": {"$in": allowed_ids}}).sort("updated_at", -1)
    return [{"survey_id": str(document["_id"]), "title": document["title"], "status": document["status"],
        "instances": [{"qid": question["qid"], "version_id": str(question["question_version_id"])} for question in document["questions"] if question.get("question_version_id") in allowed_ids]}
        for document in documents]
