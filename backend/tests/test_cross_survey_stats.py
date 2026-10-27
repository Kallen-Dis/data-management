import pytest

from tests.conftest import auth_header, register
from tests.test_question_library import create_question, create_version, referenced_survey, share, version_id

pytestmark = pytest.mark.mongo


def submit(client, survey, answers):
    result = client.post(f"/api/s/{survey['share_token']}/responses", json={"answers": answers})
    assert result.status_code == 201, result.text


def test_cross_survey_numeric_average_and_versions(client):
    token = register(client)
    question = create_question(client, token)
    first = referenced_survey(client, token, version_id(question), "q3", publish=True)
    second = referenced_survey(client, token, version_id(question), "q1", publish=True)
    submit(client, first, {"q3": "20"})
    submit(client, first, {"q3": "22"})
    submit(client, second, {"q1": "30"})
    newer = create_version(client, token, question)
    third = referenced_survey(client, token, version_id(newer), publish=True)
    submit(client, third, {"q1": "80"})
    unrelated = create_question(client, token)
    fourth = referenced_survey(client, token, version_id(unrelated), publish=True)
    submit(client, fourth, {"q1": "99"})
    result = client.get(f"/api/question-versions/{version_id(question)}/stats", headers=auth_header(token))
    assert result.status_code == 200, result.text
    view = result.json()
    assert view["avg"] == 24 and view["num_sum"] == 72 and view["num_count"] == 3
    assert view["survey_count"] == 2 and sum(bucket["count"] for bucket in view["histogram"]) == 3
    groups = client.get(f"/api/questions/{question['id']}/stats", headers=auth_header(token)).json()
    assert sorted(group["num_count"] for group in groups["versions"]) == [1, 3]


def test_question_sharing_is_not_statistics_sharing(client):
    alice, bob = register(client), register(client, "bob")
    question = share(client, alice, create_question(client, alice))
    own = referenced_survey(client, alice, version_id(question), publish=True)
    other = referenced_survey(client, bob, version_id(question), publish=True)
    submit(client, own, {"q1": "20"})
    submit(client, other, {"q1": "30"})
    path = f"/api/question-versions/{version_id(question)}/stats"
    before = client.get(path, headers=auth_header(alice)).json()
    assert before["num_count"] == 1 and before["avg"] == 20
    assert client.get(path, params={"survey_ids": other["id"]}, headers=auth_header(alice)).status_code == 403
    allowed = client.put(f"/api/surveys/{other['id']}/question-stats-sharing", headers=auth_header(bob), json={"version": other["version"], "grants": [{"question_version_id": version_id(question), "username": "alice"}]})
    assert allowed.status_code == 200
    combined = client.get(path, headers=auth_header(alice)).json()
    assert combined["num_count"] == 2 and combined["avg"] == 25 and combined["includes_shared_aggregates"]
    revoked = client.put(f"/api/surveys/{other['id']}/question-stats-sharing", headers=auth_header(bob), json={"version": allowed.json()["version"], "grants": []})
    assert revoked.status_code == 200
    assert client.get(path, headers=auth_header(alice)).json()["num_count"] == 1


def test_shared_text_aggregate_never_exposes_raw_text(client):
    alice, bob = register(client), register(client, "bob")
    question = share(client, alice, create_question(client, alice, title="建议", question_type="text"))
    first = referenced_survey(client, alice, version_id(question), publish=True)
    second = referenced_survey(client, bob, version_id(question), publish=True)
    submit(client, first, {"q1": "自己的文本"})
    submit(client, second, {"q1": "其他用户私密文本"})
    client.put(f"/api/surveys/{second['id']}/question-stats-sharing", headers=auth_header(bob), json={"version": second["version"], "grants": [{"question_version_id": version_id(question), "username": "alice"}]})
    response = client.get(f"/api/question-versions/{version_id(question)}/stats", headers=auth_header(alice))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["answer_count"] == 2 and result["texts"]["restricted_count"] == 1
    assert [item["answer"] for item in result["texts"]["items"]] == ["自己的文本"]
    assert "其他用户私密文本" not in response.text


def test_multiple_choice_counts_and_duplicate_instances(client):
    token = register(client)
    question = create_question(client, token, title="水果", question_type="multiple", options=["苹果", "香蕉"], min_select=0)
    survey = referenced_survey(client, token, version_id(question), publish=True,
        questions=[{"qid": "q1", "question_version_id": version_id(question)}, {"qid": "q2", "question_version_id": version_id(question)}])
    submit(client, survey, {"q1": ["苹果", "香蕉"], "q2": ["苹果"]})
    result = client.get(f"/api/question-versions/{version_id(question)}/stats", headers=auth_header(token))
    assert result.status_code == 200, result.text
    view = result.json()
    assert view["counts"] == [2, 1] and view["answer_count"] == 2 and view["response_count"] == 1


def test_empty_numeric_and_invalid_date_ranges(client):
    token = register(client)
    question = create_question(client, token)
    response = client.get(f"/api/question-versions/{version_id(question)}/stats", headers=auth_header(token))
    assert response.status_code == 200, response.text
    assert response.json()["avg"] is None and response.json()["histogram"] == []
    invalid = client.get(f"/api/question-versions/{version_id(question)}/stats", headers=auth_header(token), params={"start": "2026-10-23T00:00:00Z", "end": "2026-10-22T00:00:00Z"})
    assert invalid.status_code == 400


def test_legacy_binding_aggregates_without_rewriting_response(client):
    from app.db import get_db
    from app.services.migration_service import migrate_stage2
    from app.services.question_stats_service import version_stats
    from tests.test_stage2_services import legacy_fixture, owner

    user = owner()
    _, original = legacy_fixture(user, response_revision=0)
    assert migrate_stage2(dry_run=False)["snapshot_only_bindings"] == 1
    version = get_db().question_versions.find_one({"content_completeness": "snapshot_only"})
    view = version_stats(version["_id"], user)
    assert view["num_count"] == 1 and view["avg"] == 22
    assert get_db().responses.find_one({"_id": original["_id"]}) == original


def test_mongodb_rejects_invalid_version_document():
    from bson import ObjectId
    from pymongo.errors import WriteError
    from app.db import question_versions

    with pytest.raises(WriteError) as failure:
        question_versions().insert_one({"series_id": ObjectId(), "version_no": 1, "content": {"type": "invalid", "title": "非法类型"}})
    assert failure.value.code == 121
