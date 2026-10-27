from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.db import get_db
from app.models.schemas import BankCreate, BankItemCreate, BankItemUpdate, QuestionMetadata, ShareQuestion, StatsSharingUpdate, SubmitRequest, SurveyCreate, SurveyUpdate
from app.routers import question_banks as banks_api
from app.routers import surveys as surveys_api
from app.routers.submit import submit_response
from app.services import question_service as service
from app.services.migration_service import migrate_stage2


def owner(username="alice"):
    user = {"username": username, "password_hash": "test-only", "created_at": service.now()}
    user["_id"] = get_db().users.insert_one(user).inserted_id
    return user


def question(user, title="你的年龄"):
    return service.create_series({"type": "number", "title": title, "num_min": 0, "num_max": 120, "integer_only": True}, user)


def survey(user, version, publish=False):
    result = surveys_api.create_survey(SurveyCreate.model_validate({"title": "测试问卷", "allow_anonymous": True,
        "allow_multiple_submissions": True, "questions": [{"qid": "local", "question_version_id": str(version["_id"])}]}), user)
    return surveys_api.publish_survey(result["id"], user) if publish else result


def test_version_history_branch_restore_content_direct():
    user = owner()
    series, first = question(user)
    second = service.add_version(series["_id"], {**first["content"], "num_max": 100}, first["_id"], series["revision"], user)
    series = service.raw_series(series["_id"])
    third = service.add_version(series["_id"], {**first["content"], "title": "分支"}, first["_id"], series["revision"], user)
    series = service.raw_series(series["_id"])
    restored = service.add_version(series["_id"], first["content"], third["_id"], series["revision"], user, restored_from=first["_id"])
    assert second["version_no"] == 2 and third["parent_version_id"] == first["_id"]
    assert restored["parent_version_id"] == third["_id"] and restored["restored_from_version_id"] == first["_id"]
    assert restored["content"] == service.raw_version(first["_id"])["content"]


@pytest.mark.parametrize("content", [
    {"type": "number", "title": "年龄", "num_min": 10, "num_max": 2},
    {"type": "single", "title": "选择", "options": ["重复", "重复"]},
    {"type": "text", "title": "   "},
    {"type": "multiple", "title": "选择", "options": ["A"], "min_select": 2},
])
def test_library_validates_content_direct(content):
    with pytest.raises(HTTPException) as failure:
        service.create_series(content, owner())
    assert failure.value.status_code == 400
    assert get_db().question_versions.count_documents({}) == 0


def test_specific_share_does_not_expose_unshared_version_direct():
    alice, bob = owner(), owner("bob")
    series, first = question(alice)
    shared = service.save_share(series["_id"], ShareQuestion(username="bob", version_ids=[str(first["_id"])], expected_revision=1), alice)
    second = service.add_version(series["_id"], {**first["content"], "title": "私有新版"}, first["_id"], shared["revision"], alice)
    visible = service.series_view(service.raw_series(series["_id"]), bob)
    assert visible["name"] == first["content"]["title"] and len(visible["versions"]) == 1
    with pytest.raises(HTTPException) as failure:
        service.get_version(second["_id"], bob)
    assert failure.value.status_code == 403
    assert service.get_version(first["_id"], bob, for_use=True)[0]["_id"] == first["_id"]


def test_revoke_keeps_published_snapshot_and_blocks_new_bindings_direct():
    alice, bob = owner(), owner("bob")
    series, version = question(alice)
    service.save_share(series["_id"], ShareQuestion(username="bob", version_ids=[str(version["_id"])], expected_revision=1), alice)
    published = survey(bob, version, publish=True)
    get_db().question_series.update_one({"_id": series["_id"]}, {"$set": {"shared_with": []}})
    with pytest.raises(HTTPException):
        service.get_version(version["_id"], bob, for_use=True)
    assert service.get_version(version["_id"], bob)[0]["_id"] == version["_id"]
    response = submit_response(published["share_token"], SubmitRequest(answers={"local": "25"}), None)
    assert response["ok"]
    saved = get_db().responses.find_one({})
    assert saved["snapshot"]["questions"][0]["question_version_id"] == version["_id"]
    assert saved["snapshot"]["questions"][0]["num_max"] == 120


def test_closed_survey_stays_locked_and_clone_is_independent_direct():
    user = owner()
    _, version = question(user)
    published = survey(user, version, publish=True)
    closed = surveys_api.close_survey(published["id"], user)
    with pytest.raises(HTTPException) as failure:
        surveys_api.update_survey(closed["id"], SurveyUpdate(title=closed["title"], version=closed["version"], questions=[]), user)
    assert failure.value.status_code == 409
    clone = surveys_api.clone_survey(closed["id"], user)
    assert not clone["ever_published"] and clone["share_token"] != closed["share_token"]
    edited = surveys_api.update_survey(clone["id"], SurveyUpdate(title=clone["title"], version=clone["version"], questions=[]), user)
    assert edited["questions"] == []
    assert len(surveys_api.get_survey(closed["id"], user)["questions"]) == 1


def test_publish_and_save_compare_and_set_direct(monkeypatch):
    user = owner()
    _, version = question(user)
    draft = survey(user, version)
    original = surveys_api._normalize_questions
    state = {"published": False}

    def concurrent_publish(questions):
        result = original(questions)
        if not state["published"]:
            state["published"] = True
            surveys_api.publish_survey(draft["id"], user)
        return result

    monkeypatch.setattr(surveys_api, "_normalize_questions", concurrent_publish)
    request = SurveyUpdate.model_validate({"title": draft["title"], "version": draft["version"], "questions": [{**draft["questions"][0], "required": True}]})
    with pytest.raises(HTTPException) as failure:
        surveys_api.update_survey(draft["id"], request, user)
    assert failure.value.status_code == 409
    stored = get_db().surveys.find_one({"_id": ObjectId(draft["id"])})
    assert stored["ever_published"] and not stored["questions"][0]["required"]


def test_bank_upgrade_does_not_upgrade_surveys_direct():
    user = owner()
    series, first = question(user)
    published = survey(user, first, publish=True)
    bank = banks_api.create_bank(BankCreate(name="基础题库"), user)
    item = banks_api.add_item(bank["id"], BankItemCreate(version_id=str(first["_id"])), user)
    second = service.add_version(series["_id"], {**first["content"], "title": "新版年龄"}, first["_id"], 1, user)
    updated = banks_api.update_item(bank["id"], item["id"], BankItemUpdate(version_id=str(second["_id"]), revision=1), user)
    assert updated["version_no"] == 2
    assert surveys_api.get_survey(published["id"], user)["questions"][0]["question_version_id"] == str(first["_id"])
    banks_api.delete_item(bank["id"], item["id"], user)
    assert service.raw_version(first["_id"])["content"]["title"] == "你的年龄"


def test_origin_reservation_is_idempotent_direct():
    user = owner()
    first, first_version = service.create_series({"type": "text", "title": "原内容"}, user, origin_key="stable-origin")
    second, second_version = service.create_series({"type": "text", "title": "不能覆盖"}, user, origin_key="stable-origin")
    assert first["_id"] == second["_id"] and first_version["_id"] == second_version["_id"]
    assert service.raw_version(first_version["_id"])["content"]["title"] == "原内容"
    assert get_db().question_versions.count_documents({}) == 1


def test_parallel_version_creation_direct():
    user = owner()
    series, version = question(user)

    def create(index):
        try:
            return service.add_version(series["_id"], {**version["content"], "title": f"并发 {index}"}, version["_id"], 1, user)["version_no"]
        except HTTPException as failure:
            return failure.status_code

    with ThreadPoolExecutor(max_workers=5) as executor:
        outcomes = list(executor.map(create, range(5)))
    assert outcomes.count(2) == 1 and outcomes.count(409) == 4


def legacy_fixture(user, response_revision=1):
    created = surveys_api.create_survey(SurveyCreate.model_validate({"title": "第一阶段问卷", "questions": [{"qid": "q1", "type": "number", "title": "年龄", "num_min": 0, "num_max": 120}]}), user)
    get_db().surveys.update_one({"_id": ObjectId(created["id"])}, {"$unset": {"schema_version": "", "ever_published": ""}, "$set": {"status": "closed", "published_at": service.now()}})
    document = {"survey_id": ObjectId(created["id"]), "survey_version": response_revision,
        "snapshot": {"title": "第一阶段问卷", "questions": [{"qid": "q1", "type": "number", "title": "年龄", "options": []}]},
        "answers": {"q1": "22"}, "submitted_at": service.now(), "respondent_key": "legacy", "respondent": {"user_id": None}}
    document["_id"] = get_db().responses.insert_one(document).inserted_id
    return created, deepcopy(get_db().responses.find_one({"_id": document["_id"]}))


def test_migration_preserves_responses_and_is_repeatable_direct():
    user = owner()
    created, original_response = legacy_fixture(user)
    preview = migrate_stage2(dry_run=True)
    assert preview["surveys_updated"] == 1 and get_db().question_versions.count_documents({}) == 0
    report = migrate_stage2(dry_run=False)
    assert report["verified_bindings"] == 1 and not report["conflicts"]
    assert get_db().responses.find_one({"_id": original_response["_id"]}) == original_response
    migrated = get_db().surveys.find_one({"_id": ObjectId(created["id"])})
    assert migrated["ever_published"] and migrated["version"] == created["version"]
    repeated = migrate_stage2(dry_run=False)
    assert repeated["surveys_updated"] == 0 and repeated["legacy_bindings"] == 0
    assert get_db().question_versions.count_documents({}) == 1


def test_unverifiable_legacy_questions_are_separate_and_partial_direct():
    user = owner()
    legacy_fixture(user, response_revision=0)
    legacy_fixture(user, response_revision=0)
    report = migrate_stage2(dry_run=False)
    assert report["snapshot_only_bindings"] == 2
    historical = list(get_db().question_versions.find({"content_completeness": "snapshot_only"}))
    assert len(historical) == 2 and historical[0]["series_id"] != historical[1]["series_id"]
    assert set(historical[0]["content"]) == {"type", "title", "options"}
    with pytest.raises(HTTPException):
        service.get_version(historical[0]["_id"], user, for_use=True)


def test_stat_sharing_does_not_grant_unrelated_versions_direct():
    user, bob = owner(), owner("bob")
    _, first = question(user)
    _, unrelated = question(user, title="无关题目")
    published = survey(user, first, publish=True)
    with pytest.raises(HTTPException) as failure:
        surveys_api.set_question_stats_sharing(published["id"], StatsSharingUpdate.model_validate({"version": published["version"], "grants": [{"question_version_id": str(unrelated["_id"]), "username": "bob"}]}), user)
    assert failure.value.status_code == 400
    updated = surveys_api.set_question_stats_sharing(published["id"], StatsSharingUpdate.model_validate({"version": published["version"], "grants": [{"question_version_id": str(first["_id"]), "username": "bob"}]}), user)
    assert updated["question_stats_shares"][0]["grantee_id"] == str(bob["_id"])
