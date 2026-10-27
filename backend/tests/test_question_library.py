from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from bson import ObjectId

from app.db import get_db
from app.services import question_service
from tests.conftest import auth_header, register


def create_question(client, token, title="你的年龄", question_type="number", **overrides):
    content = {"type": question_type, "title": title, **overrides}
    response = client.post("/api/questions", json={"content": content}, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


def version_id(question):
    return question["default_version_id"]


def create_version(client, token, question, title="你目前的年龄", parent=None, **content):
    response = client.post(f"/api/questions/{question['id']}/versions", headers=auth_header(token),
        json={"content": {**question["versions"][0]["content"], "title": title, **content},
            "parent_version_id": parent or version_id(question), "expected_revision": question["revision"], "change_note": "测试版本"})
    assert response.status_code == 201, response.text
    return response.json()["question"]


def referenced_survey(client, token, version, qid="q1", publish=False, **overrides):
    response = client.post("/api/surveys", headers=auth_header(token), json={"title": "引用问卷", "allow_anonymous": True,
        "allow_multiple_submissions": True, "questions": [{"qid": qid, "question_version_id": version}], **overrides})
    assert response.status_code == 201, response.text
    survey = response.json()
    if publish:
        response = client.post(f"/api/surveys/{survey['id']}/publish", headers=auth_header(token))
        assert response.status_code == 200, response.text
        survey = response.json()
    return survey


def share(client, token, question, username="bob", versions=None, all_versions=False, allow_fork=True):
    response = client.post(f"/api/questions/{question['id']}/shares", headers=auth_header(token), json={"username": username,
        "version_ids": versions or [version_id(question)], "expected_revision": question["revision"], "all_versions": all_versions, "allow_fork": allow_fork})
    assert response.status_code == 200, response.text
    return response.json()


def test_reuse_global_identity_and_local_qids(client):
    token = register(client)
    question = create_question(client, token)
    first = referenced_survey(client, token, version_id(question), "q3")
    second = referenced_survey(client, token, version_id(question), "q1")
    assert first["questions"][0]["qid"] != second["questions"][0]["qid"]
    assert first["questions"][0]["question_version_id"] == second["questions"][0]["question_version_id"]
    usages = client.get(f"/api/questions/{question['id']}/usages", headers=auth_header(token)).json()
    assert {row["survey_id"] for row in usages} == {first["id"], second["id"]}


def test_version_branch_restore_and_immutability(client):
    token = register(client)
    original = create_question(client, token)
    initial_id = version_id(original)
    second = create_version(client, token, original)
    third = create_version(client, token, second, title="分支年龄", parent=initial_id)
    assert third["versions"][0]["parent_version_id"] == initial_id
    restored = client.post(f"/api/questions/{original['id']}/restore", headers=auth_header(token), json={"source_version_id": initial_id, "expected_revision": third["revision"]})
    assert restored.status_code == 201, restored.text
    fourth = restored.json()["version"]
    assert fourth["version_no"] == 4 and fourth["parent_version_id"] == version_id(third)
    assert fourth["restored_from_version_id"] == initial_id and fourth["content"]["title"] == original["versions"][0]["content"]["title"]
    assert client.get(f"/api/question-versions/{initial_id}", headers=auth_header(token)).json()["content"] == original["versions"][0]["content"]
    assert client.put(f"/api/question-versions/{initial_id}", headers=auth_header(token), json={"title": "覆盖"}).status_code == 405


def test_cross_series_parent_and_stale_revision_rejected(client):
    token = register(client)
    first, other = create_question(client, token), create_question(client, token, title="另一个题目")
    payload = {"content": first["versions"][0]["content"], "parent_version_id": version_id(other), "expected_revision": first["revision"]}
    assert client.post(f"/api/questions/{first['id']}/versions", headers=auth_header(token), json=payload).status_code == 400
    create_version(client, token, first)
    payload["parent_version_id"] = version_id(first)
    assert client.post(f"/api/questions/{first['id']}/versions", headers=auth_header(token), json=payload).status_code == 409


def test_working_draft_does_not_create_formal_versions(client):
    token = register(client)
    question = create_question(client, token)
    response = client.put(f"/api/questions/{question['id']}/draft", headers=auth_header(token), json={"content": {"type": "number", "title": "尚未正式保存"}, "parent_version_id": version_id(question), "expected_revision": question["revision"]})
    assert response.status_code == 200
    assert len(response.json()["versions"]) == 1
    assert response.json()["draft"]["content"]["title"] == "尚未正式保存"
    assert response.json()["versions"][0]["content"]["title"] == "你的年龄"


def test_share_specific_version_and_fork_permissions(client):
    alice, bob = register(client), register(client, "bob")
    original = create_question(client, alice)
    assert client.get(f"/api/question-versions/{version_id(original)}", headers=auth_header(bob)).status_code == 403
    shared = share(client, alice, original, allow_fork=False)
    second = create_version(client, alice, shared, title="未共享的新内容")
    visible = client.get(f"/api/questions/{original['id']}", headers=auth_header(bob)).json()
    assert len(visible["versions"]) == 1 and visible["versions"][0]["id"] == version_id(original)
    assert visible["name"] != "未共享的新内容"
    search = client.get("/api/questions", params={"scope": "shared", "search": "未共享的新内容"}, headers=auth_header(bob))
    assert search.status_code == 200 and search.json()["total"] == 0
    original_search = client.get("/api/questions", params={"scope": "shared", "search": "你的年龄"}, headers=auth_header(bob))
    assert original_search.status_code == 200 and original_search.json()["total"] == 1
    assert client.get(f"/api/question-versions/{version_id(second)}", headers=auth_header(bob)).status_code == 403
    assert client.post(f"/api/question-versions/{version_id(original)}/fork", headers=auth_header(bob)).status_code == 403
    shared = share(client, alice, second, versions=[version_id(original)])
    fork = client.post(f"/api/question-versions/{version_id(original)}/fork", headers=auth_header(bob))
    assert fork.status_code == 201
    assert fork.json()["id"] != original["id"]
    assert fork.json()["versions"][0]["derived_from_version_id"] == version_id(original)


def test_revoke_preserves_saved_instance_but_blocks_new_use(client):
    alice, bob = register(client), register(client, "bob")
    question = share(client, alice, create_question(client, alice))
    survey = referenced_survey(client, bob, version_id(question), publish=True)
    bob_id = str(get_db().users.find_one({"username": "bob"})["_id"])
    response = client.delete(f"/api/questions/{question['id']}/shares/{bob_id}", params={"revision": question["revision"]}, headers=auth_header(alice))
    assert response.status_code == 200
    assert client.get(f"/api/s/{survey['share_token']}").status_code == 200
    assert client.post(f"/api/s/{survey['share_token']}/responses", json={"answers": {"q1": "25"}}).status_code == 201
    assert client.post("/api/surveys", headers=auth_header(bob), json={"title": "新引用", "questions": [{"qid": "q1", "question_version_id": version_id(question)}]}).status_code == 403
    assert client.post(f"/api/surveys/{survey['id']}/clone", headers=auth_header(bob)).status_code == 403
    usages = client.get(f"/api/questions/{question['id']}/usages", headers=auth_header(alice)).json()
    assert usages == []


def test_reference_tampering_and_invalid_identifiers(client):
    token = register(client)
    first, other = create_question(client, token), create_question(client, token, title="其他题")
    for overrides, expected in [({"title": "伪造的内容"}, 409), ({"question_series_id": other["id"]}, 400)]:
        response = client.post("/api/surveys", headers=auth_header(token), json={"title": "伪造来源", "questions": [{"qid": "q1", "question_version_id": version_id(first), **overrides}]})
        assert response.status_code == expected
    assert client.get("/api/question-versions/not-an-id", headers=auth_header(token)).status_code == 404


def test_published_and_closed_structures_remain_locked(client):
    token = register(client)
    question = create_question(client, token)
    survey = referenced_survey(client, token, version_id(question), publish=True)
    second = create_version(client, token, question)
    for content in ([{**survey["questions"][0], "required": True}], [{"qid": "q1", "question_version_id": version_id(second)}], []):
        assert client.put(f"/api/surveys/{survey['id']}", headers=auth_header(token), json={"title": survey["title"], "version": survey["version"], "questions": content}).status_code == 409
    closed = client.post(f"/api/surveys/{survey['id']}/close", headers=auth_header(token)).json()
    assert closed["ever_published"]
    assert client.put(f"/api/surveys/{survey['id']}", headers=auth_header(token), json={"title": closed["title"], "version": closed["version"], "questions": []}).status_code == 409
    clone = client.post(f"/api/surveys/{survey['id']}/clone", headers=auth_header(token)).json()
    assert clone["share_token"] != survey["share_token"] and not clone["ever_published"]
    assert clone["questions"][0]["question_version_id"] == version_id(question)


def test_publishing_race_cannot_be_overwritten(client, monkeypatch):
    from app.routers import surveys as routes
    token = register(client)
    question = create_question(client, token)
    survey = referenced_survey(client, token, version_id(question))
    original = routes._normalize_questions
    state = {"published": False}

    def normalize_and_publish(questions):
        result = original(questions)
        if not state["published"]:
            state["published"] = True
            assert client.post(f"/api/surveys/{survey['id']}/publish", headers=auth_header(token)).status_code == 200
        return result

    monkeypatch.setattr(routes, "_normalize_questions", normalize_and_publish)
    response = client.put(f"/api/surveys/{survey['id']}", headers=auth_header(token), json={"title": "竞争保存", "version": survey["version"], "questions": [{**survey["questions"][0], "required": True}]})
    assert response.status_code == 409
    stored = client.get(f"/api/surveys/{survey['id']}", headers=auth_header(token)).json()
    assert stored["ever_published"] and not stored["questions"][0]["required"]


def test_banks_pin_versions_and_enforce_ownership(client):
    token, other_token = register(client), register(client, "bob")
    question = create_question(client, token)
    bank = client.post("/api/question-banks", headers=auth_header(token), json={"name": "基础信息"}).json()
    item = client.post(f"/api/question-banks/{bank['id']}/items", headers=auth_header(token), json={"version_id": version_id(question)})
    assert item.status_code == 201
    assert client.post(f"/api/question-banks/{bank['id']}/items", headers=auth_header(token), json={"version_id": version_id(question)}).status_code == 409
    assert client.get(f"/api/question-banks/{bank['id']}/items", headers=auth_header(other_token)).status_code == 403
    survey = referenced_survey(client, token, version_id(question), publish=True)
    second = create_version(client, token, question)
    updated = client.patch(f"/api/question-banks/{bank['id']}/items/{item.json()['id']}", headers=auth_header(token), json={"version_id": version_id(second), "revision": 1})
    assert updated.status_code == 200 and updated.json()["version_no"] == 2
    assert client.get(f"/api/surveys/{survey['id']}", headers=auth_header(token)).json()["questions"][0]["question_version_id"] == version_id(question)
    assert client.delete(f"/api/question-banks/{bank['id']}/items/{item.json()['id']}", headers=auth_header(token)).status_code == 200
    assert client.get(f"/api/question-versions/{version_id(question)}", headers=auth_header(token)).status_code == 200


def test_inline_drafts_only_freeze_on_publish_or_library_save(client):
    token = register(client)
    survey = client.post("/api/surveys", headers=auth_header(token), json={"title": "临时题目", "questions": [{"qid": "q1", "type": "text", "title": "尚未确定"}]}).json()
    assert get_db().question_versions.count_documents({}) == 0
    updated = client.put(f"/api/surveys/{survey['id']}", headers=auth_header(token), json={"title": survey["title"], "version": survey["version"], "questions": [{"qid": "q1", "type": "text", "title": "确定的题目"}]}).json()
    assert get_db().question_versions.count_documents({}) == 0
    saved = client.post(f"/api/surveys/{survey['id']}/questions/q1/library", headers=auth_header(token))
    assert saved.status_code == 200 and get_db().question_versions.count_documents({}) == 1
    assert saved.json()["survey"]["questions"][0]["question_version_id"] == saved.json()["question"]["default_version_id"]
    assert updated["version"] < saved.json()["survey"]["version"]


def test_concurrent_version_reservations_use_optimistic_lock(client):
    token = register(client)
    question = create_question(client, token)
    owner = get_db().users.find_one({"username": "alice"})

    def attempt(index):
        from fastapi import HTTPException
        try:
            return question_service.add_version(question["id"], {"type": "number", "title": f"分支 {index}"}, version_id(question), question["revision"], owner)["version_no"]
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    assert results.count(2) == 1 and results.count(409) == 5
    assert get_db().question_versions.count_documents({"series_id": ObjectId(question["id"])}) == 2
