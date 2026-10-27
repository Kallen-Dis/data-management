import argparse
import json
import re
import sys
from hashlib import sha256
from pathlib import Path

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, PyMongoError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

EXAMPLE_PATH = Path(__file__).resolve().parents[2] / "examples" / "simple_question_bank.json"


def load_definition(path=EXAMPLE_PATH):
    from app.models.schemas import BankCreate, QuestionCreate
    from app.services.question_service import validate_content

    definition = json.loads(Path(path).read_text(encoding="utf-8"))
    BankCreate.model_validate(definition)
    if not definition["name"].strip() or not definition.get("questions"):
        raise ValueError("题库名称及题目列表不能为空")
    keys = [definition["key"], *(item["key"] for item in definition["questions"])]
    if any(not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key) for key in keys):
        raise ValueError("示例标识只允许 1 至 64 位字母、数字、下划线或连字符")
    if len(set(keys[1:])) != len(keys[1:]):
        raise ValueError("示例题目的 key 不能重复")
    for item in definition["questions"]:
        request = QuestionCreate.model_validate(item)
        item["content"] = validate_content(request.content.model_dump())
        item["tags"] = request.tags
    return definition


def seed_question_bank(username, definition, apply=False):
    from app.db import init_db, question_banks, question_bank_items, question_series, users
    from app.services import question_bank_service, question_service

    user = users().find_one({"username": username})
    if user is None:
        raise ValueError("账号不存在，请先在系统注册；导入脚本不会创建账号或修改密码")
    source = f"example-bank:{user['_id']}:{definition['key']}"
    bank_id = ObjectId(sha256(source.encode()).hexdigest()[:24])
    existing_bank = question_banks().find_one({"_id": bank_id})
    if existing_bank and (existing_bank["owner_id"] != user["_id"] or existing_bank.get("example_key") != definition["key"]):
        raise ValueError("示例题库身份冲突，未覆盖现有数据")
    if existing_bank and existing_bank.get("archived_at"):
        raise ValueError("示例题库已归档，请先在页面中恢复；脚本不会自动取消归档")
    if apply:
        init_db()
        timestamp = question_service.now()
        try:
            question_banks().insert_one({"_id": bank_id, "owner_id": user["_id"], "example_key": definition["key"],
                "name": definition["name"], "description": definition.get("description", ""), "revision": 1,
                "archived_at": None, "created_at": timestamp, "updated_at": timestamp})
        except DuplicateKeyError:
            pass
    items = []
    for item in definition["questions"]:
        origin = f"{source}:question:{item['key']}"
        series_id = ObjectId(sha256(origin.encode()).hexdigest()[:24])
        selected = question_bank_items().find_one({"bank_id": bank_id, "series_id": series_id})
        was_present = selected is not None
        if not selected and question_series().find_one({"_id": series_id, "archived_at": {"$ne": None}}):
            raise ValueError("示例题目已归档，请先恢复；未自动取消归档或覆盖版本")
        if apply and not selected:
            _, version = question_service.create_series(item["content"], user, tags=item["tags"],
                change_note="校园生活示例题库初始版本", origin_key=origin)
            try:
                selected = question_bank_service.add_item(bank_id, version["_id"], user)
            except HTTPException as failure:
                if failure.status_code != 409 or not question_bank_items().find_one({"bank_id": bank_id, "series_id": series_id}):
                    raise
        items.append({"key": item["key"], "title": item["content"]["title"], "type": item["content"]["type"],
            "action": "preserved" if was_present else ("added" if apply else "would_add"),
            "series_id": str(series_id)})
    return {"dry_run": not apply, "owner": username, "bank_id": str(bank_id),
        "bank_name": existing_bank["name"] if existing_bank else definition["name"], "question_count": len(items), "items": items}


def main():
    parser = argparse.ArgumentParser(description="导入简单示例题库：默认只读预演，--apply 才写入，不创建账号或答卷")
    parser.add_argument("--owner", required=True, help="已有账号的用户名")
    parser.add_argument("--database", required=True)
    parser.add_argument("--uri", default="mongodb://127.0.0.1:27017")
    parser.add_argument("--file", default=str(EXAMPLE_PATH))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    import app.config as config
    config.DB_NAME = args.database
    config.MONGODB_URI = args.uri
    try:
        report = seed_question_bank(args.owner, load_definition(args.file), apply=args.apply)
    except (ValueError, KeyError, TypeError, OSError, HTTPException, PyMongoError) as failure:
        parser.exit(1, f"导入未完成：{getattr(failure, 'detail', str(failure))}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
