import json

import pytest

from app.db import get_db
from app.services import question_service
from scripts.seed_question_bank import EXAMPLE_PATH, load_definition, seed_question_bank
from tests.test_stage2_services import owner


def test_example_bank_covers_four_types_and_creates_six_items():
    user = owner()
    definition = load_definition()
    assert {item["content"]["type"] for item in definition["questions"]} == {"single", "multiple", "number", "text"}
    report = seed_question_bank(user["username"], definition, apply=True)
    assert report["question_count"] == 6 and not report["dry_run"]
    assert all(item["action"] == "added" for item in report["items"])
    database = get_db()
    assert database.question_banks.count_documents({}) == 1
    assert database.question_versions.count_documents({}) == database.question_bank_items.count_documents({}) == 6
    assert database.responses.count_documents({}) == database.surveys.count_documents({}) == 0


def test_example_preview_and_unknown_owner_do_not_write():
    user = owner()
    definition = load_definition()
    preview = seed_question_bank(user["username"], definition)
    assert preview["dry_run"] and all(item["action"] == "would_add" for item in preview["items"])
    with pytest.raises(ValueError, match="账号不存在"):
        seed_question_bank("unknown", definition, apply=True)
    assert get_db().question_banks.count_documents({}) == get_db().question_series.count_documents({}) == 0


def test_example_reimport_preserves_user_changes_and_selected_version():
    user = owner()
    definition = load_definition()
    seed_question_bank(user["username"], definition, apply=True)
    database = get_db()
    first = database.question_versions.find_one({"content.type": "number"})
    series = question_service.raw_series(first["series_id"])
    second = question_service.add_version(series["_id"], {**first["content"], "title": "自行创建的新版"}, first["_id"], series["revision"], user)
    database.question_bank_items.update_one({"series_id": series["_id"]}, {"$set": {"selected_version_id": second["_id"]}})
    database.question_banks.update_one({}, {"$set": {"name": "用户已改名"}})
    report = seed_question_bank(user["username"], load_definition(), apply=True)
    assert report["bank_name"] == "用户已改名" and all(item["action"] == "preserved" for item in report["items"])
    assert database.question_versions.count_documents({}) == 7
    assert database.question_banks.count_documents({}) == 1
    assert database.question_bank_items.find_one({"series_id": series["_id"]})["selected_version_id"] == second["_id"]


def test_example_is_private_per_user_and_respects_archive():
    alice, bob = owner(), owner("bob")
    first = seed_question_bank(alice["username"], load_definition(), apply=True)
    second = seed_question_bank(bob["username"], load_definition(), apply=True)
    assert first["bank_id"] != second["bank_id"]
    database = get_db()
    database.question_banks.update_one({"owner_id": alice["_id"]}, {"$set": {"archived_at": question_service.now()}})
    with pytest.raises(ValueError, match="已归档"):
        seed_question_bank(alice["username"], load_definition(), apply=True)
    assert database.question_banks.count_documents({}) == 2
    assert database.question_versions.count_documents({}) == 12


def test_example_rejects_duplicate_keys_before_import(tmp_path):
    definition = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    definition["questions"][1]["key"] = definition["questions"][0]["key"]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(definition), encoding="utf-8")
    with pytest.raises(ValueError, match="不能重复"):
        load_definition(path)
