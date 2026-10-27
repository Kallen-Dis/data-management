from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import question_banks, question_bank_items
from app.deps import get_current_user
from app.models.schemas import BankCreate, BankItemCreate, BankItemUpdate, BankUpdate
from app.serialization import object_id
from app.services import question_bank_service as service
from app.services.question_service import now

router = APIRouter(prefix="/api/question-banks", tags=["question-banks"])


@router.post("", status_code=201)
def create_bank(request: BankCreate, user=Depends(get_current_user)):
    if not request.name.strip():
        raise HTTPException(400, "题库名称不能为空")
    bank = {"owner_id": user["_id"], "name": request.name.strip(), "description": request.description,
        "revision": 1, "archived_at": None, "created_at": now(), "updated_at": now()}
    bank["_id"] = question_banks().insert_one(bank).inserted_id
    return service.bank_view(bank)


@router.get("")
def list_banks(archived: bool = False, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user=Depends(get_current_user)):
    query = {"owner_id": user["_id"], "archived_at": {"$ne": None} if archived else None}
    return {"items": [service.bank_view(bank) for bank in question_banks().find(query).sort("updated_at", -1).skip((page - 1) * page_size).limit(page_size)],
        "total": question_banks().count_documents(query)}


@router.patch("/{bank_id}")
def update_bank(bank_id: str, request: BankUpdate, user=Depends(get_current_user)):
    bank = service.owned_bank(bank_id, user)
    if not request.name.strip():
        raise HTTPException(400, "题库名称不能为空")
    if question_banks().update_one({"_id": bank["_id"], "revision": request.revision},
        {"$set": {"name": request.name.strip(), "description": request.description, "archived_at": now() if request.archived else None, "updated_at": now()}, "$inc": {"revision": 1}}).matched_count != 1:
        raise HTTPException(409, "题库已更新，请刷新后重试")
    return service.bank_view(service.owned_bank(bank_id, user))


@router.get("/{bank_id}/items")
def list_items(bank_id: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user=Depends(get_current_user)):
    bank = service.owned_bank(bank_id, user)
    query = {"bank_id": bank["_id"]}
    return {"bank": service.bank_view(bank), "items": [service.item_view(item, user) for item in question_bank_items().find(query).sort("added_at", -1).skip((page - 1) * page_size).limit(page_size)],
        "total": question_bank_items().count_documents(query)}


@router.post("/{bank_id}/items", status_code=201)
def add_item(bank_id: str, request: BankItemCreate, user=Depends(get_current_user)):
    return service.add_item(bank_id, request.version_id, user)


@router.patch("/{bank_id}/items/{item_id}")
def update_item(bank_id: str, item_id: str, request: BankItemUpdate, user=Depends(get_current_user)):
    return service.update_item(bank_id, item_id, request, user)


@router.delete("/{bank_id}/items/{item_id}")
def delete_item(bank_id: str, item_id: str, user=Depends(get_current_user)):
    bank = service.owned_bank(bank_id, user)
    if question_bank_items().delete_one({"_id": object_id(item_id), "bank_id": bank["_id"]}).deleted_count != 1:
        raise HTTPException(404, "题库条目不存在")
    return {"ok": True}
