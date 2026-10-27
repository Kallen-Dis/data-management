import re

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import question_series, question_versions
from app.deps import get_current_user
from app.models.schemas import QuestionCreate, QuestionMetadata, RestoreQuestion, ShareQuestion, VersionCreate
from app.serialization import document_view, object_id
from app.services import question_service as service

router = APIRouter(prefix="/api", tags=["question-library"])


@router.post("/questions", status_code=201)
def create_question(request: QuestionCreate, user=Depends(get_current_user)):
    series, _ = service.create_series(request.content.model_dump(), user, request.tags, request.change_note)
    return service.series_view(series, user)


@router.get("/questions")
def list_questions(scope: str = Query("mine", pattern="^(mine|shared)$"), search: str = Query("", max_length=200),
                   archived: bool = False, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    query = {"owner_id": user["_id"]} if scope == "mine" else {"shared_with.user_id": user["_id"], "owner_id": {"$ne": user["_id"]}}
    query["listed"] = {"$ne": False}
    query["archived_at"] = {"$ne": None} if archived else None
    if scope == "shared":
        items = []
        for document in question_series().find(query).sort("updated_at", -1):
            try:
                visible = service.series_view(document, user)
            except HTTPException as failure:
                if failure.status_code == 403:
                    continue
                raise
            if not search.strip() or search.strip().casefold() in visible["name"].casefold():
                items.append(visible)
        start = (page - 1) * page_size
        return {"items": items[start:start + page_size], "total": len(items), "page": page, "page_size": page_size}
    if search.strip():
        query["name"] = {"$regex": re.escape(search.strip()), "$options": "i"}
    documents = question_series().find(query).sort("updated_at", -1).skip((page - 1) * page_size).limit(page_size)
    return {"items": [service.series_view(document, user) for document in documents], "total": question_series().count_documents(query), "page": page, "page_size": page_size}


@router.get("/questions/{series_id}")
def get_question(series_id: str, user=Depends(get_current_user)):
    return service.series_view(service.raw_series(series_id), user)


@router.patch("/questions/{series_id}")
def update_question(series_id: str, request: QuestionMetadata, user=Depends(get_current_user)):
    return service.update_metadata(series_id, request, user)


@router.get("/questions/{series_id}/versions")
def list_versions(series_id: str, user=Depends(get_current_user)):
    return service.series_view(service.raw_series(series_id), user)["versions"]


@router.post("/questions/{series_id}/versions", status_code=201)
def create_version(series_id: str, request: VersionCreate, user=Depends(get_current_user)):
    version = service.add_version(series_id, request.content.model_dump(), request.parent_version_id, request.expected_revision, user, request.change_note)
    return {"version": document_view(version), "question": service.series_view(service.raw_series(series_id), user)}


@router.put("/questions/{series_id}/draft")
def save_draft(series_id: str, request: VersionCreate, user=Depends(get_current_user)):
    series = service.owned_series(series_id, user)
    parent = service.raw_version(request.parent_version_id)
    if parent["series_id"] != series["_id"]:
        raise HTTPException(400, "父版本不属于此题目")
    if question_series().update_one({"_id": series["_id"], "revision": request.expected_revision},
        {"$set": {"draft": {"base_version_id": parent["_id"], "content": request.content.model_dump(), "change_note": request.change_note}, "updated_at": service.now()}, "$inc": {"revision": 1}}).matched_count != 1:
        raise HTTPException(409, "草稿已更新，请刷新后重试")
    return service.series_view(service.raw_series(series_id), user)


@router.post("/questions/{series_id}/restore", status_code=201)
def restore_version(series_id: str, request: RestoreQuestion, user=Depends(get_current_user)):
    series = service.owned_series(series_id, user)
    source = service.raw_version(request.source_version_id)
    if source["series_id"] != series["_id"]:
        raise HTTPException(400, "恢复来源不属于此题目")
    if source.get("content_completeness") == "snapshot_only":
        raise HTTPException(409, "历史快照未保留完整约束，请补全内容后保存为新版本")
    version = service.add_version(series_id, source["content"], series["default_version_id"], request.expected_revision, user, request.change_note, restored_from=source["_id"])
    return {"version": document_view(version), "question": service.series_view(service.raw_series(series_id), user)}


@router.get("/question-versions/{version_id}")
def get_version(version_id: str, user=Depends(get_current_user)):
    version, series = service.get_version(version_id, user)
    return {**document_view(version), "can_manage": series["owner_id"] == user["_id"], "can_use": service.version_allowed(version, series, user, for_use=True)}


@router.post("/question-versions/{version_id}/fork", status_code=201)
def fork_version(version_id: str, user=Depends(get_current_user)):
    version, series = service.get_version(version_id, user, for_use=True)
    grant = service.grant_for(series, user)
    if series["owner_id"] != user["_id"] and not grant.get("allow_fork", True):
        raise HTTPException(403, "此题目仅允许引用，不允许派生")
    fork, _ = service.create_series(version["content"], user, change_note="从共享版本派生", derived_from=version["_id"])
    return service.series_view(fork, user)


@router.post("/questions/{series_id}/shares")
def share_question(series_id: str, request: ShareQuestion, user=Depends(get_current_user)):
    return service.save_share(series_id, request, user)


@router.delete("/questions/{series_id}/shares/{user_id}")
def revoke_share(series_id: str, user_id: str, revision: int = Query(...), user=Depends(get_current_user)):
    series = service.owned_series(series_id, user)
    if question_series().update_one({"_id": series["_id"], "revision": revision},
        {"$pull": {"shared_with": {"user_id": object_id(user_id)}}, "$inc": {"revision": 1}, "$set": {"updated_at": service.now()}}).matched_count != 1:
        raise HTTPException(409, "分享设置已变化，请刷新后重试")
    return service.series_view(service.raw_series(series_id), user)


@router.get("/questions/{series_id}/usages")
def question_usages(series_id: str, version_id: str | None = None, user=Depends(get_current_user)):
    return service.usages(series_id, user, version_id)
