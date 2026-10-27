from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.db import question_banks, question_bank_items
from app.serialization import document_view, object_id
from app.services import question_service


def owned_bank(bank_id, user):
    bank = question_banks().find_one({"_id": object_id(bank_id, "题库不存在")})
    if bank is None:
        raise HTTPException(404, "题库不存在")
    if bank["owner_id"] != user["_id"]:
        raise HTTPException(403, "无权访问该题库")
    return bank


def bank_view(bank):
    return {**document_view(bank), "item_count": question_bank_items().count_documents({"bank_id": bank["_id"]})}


def item_view(item, user):
    result = document_view(item)
    try:
        version, series = question_service.get_version(item["selected_version_id"], user, for_use=True)
        visible_versions = question_service.series_view(series, user)["versions"]
        latest = next((candidate["id"] for candidate in visible_versions if candidate["can_use"]), str(version["_id"]))
        result.update({"available": True, "content": version["content"], "version_no": version["version_no"],
            "latest_version_id": latest, "has_new_version": latest != str(version["_id"])})
    except HTTPException:
        result.update({"available": False, "content": None})
    return result


def add_item(bank_id, version_id, user):
    bank = owned_bank(bank_id, user)
    if bank.get("archived_at"):
        raise HTTPException(409, "题库已归档")
    version, series = question_service.get_version(version_id, user, for_use=True)
    item = {"bank_id": bank["_id"], "series_id": series["_id"], "selected_version_id": version["_id"],
        "revision": 1, "added_at": question_service.now()}
    try:
        item["_id"] = question_bank_items().insert_one(item).inserted_id
    except DuplicateKeyError:
        raise HTTPException(409, "题库已包含此题目，请在原条目中切换版本")
    return item_view(item, user)


def update_item(bank_id, item_id, request, user):
    bank = owned_bank(bank_id, user)
    if bank.get("archived_at"):
        raise HTTPException(409, "题库已归档")
    item = question_bank_items().find_one({"_id": object_id(item_id), "bank_id": bank["_id"]})
    if item is None:
        raise HTTPException(404, "题库条目不存在")
    version, _ = question_service.get_version(request.version_id, user, for_use=True)
    if version["series_id"] != item["series_id"]:
        raise HTTPException(400, "只能切换同一题目的版本")
    if question_bank_items().update_one({"_id": item["_id"], "revision": request.revision},
        {"$set": {"selected_version_id": version["_id"]}, "$inc": {"revision": 1}}).matched_count != 1:
        raise HTTPException(409, "题库条目已更新，请刷新后重试")
    return item_view(question_bank_items().find_one({"_id": item["_id"]}), user)
