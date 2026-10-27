from unittest.mock import patch

from bson import ObjectId
from pymongo.errors import AutoReconnect

from app.db import responses, stats, surveys
from app.services import stats_service
from tests.conftest import auth_header, make_survey, register


def published(client):
    token = register(client)
    created = client.post("/api/surveys", json=make_survey(allow_anonymous=True, allow_multiple_submissions=True), headers=auth_header(token)).json()
    client.post(f"/api/surveys/{created['id']}/publish", headers=auth_header(token))
    return token, created, surveys().find_one({"_id": ObjectId(created["id"])})


def test_rebuild_between_response_insert_and_increment_does_not_double_count(client):
    token, survey, stored = published(client)
    original_apply = stats_service.apply_submission

    def rebuild_before_increment(document, answers, visited, revision):
        stats_service.rebuild_stats(document["_id"])
        return original_apply(document, answers, visited, revision)

    with patch.object(stats_service, "apply_submission", side_effect=rebuild_before_increment):
        result = client.post(f"/api/s/{survey['share_token']}/responses", json={"answers": {"q1": ["男"], "q3": "22", "q4": "建议"}})
    assert result.status_code == 201, result.text
    cached = stats().find_one({"survey_id": stored["_id"]})
    assert cached["total"] == 1
    view = client.get(f"/api/surveys/{survey['id']}/stats", headers=auth_header(token)).json()
    assert view["total"] == 1
    assert next(question for question in view["questions"] if question["qid"] == "q3")["num_sum"] == 22


def test_persisted_response_survives_cache_failure_and_read_repairs_it(client):
    token, survey, stored = published(client)
    with patch.object(stats_service, "apply_submission", side_effect=AutoReconnect("simulated cache failure")):
        result = client.post(f"/api/s/{survey['share_token']}/responses", json={"answers": {"q1": ["男"], "q3": "22", "q4": "建议"}})
    assert result.status_code == 201 and result.json()["stats_pending"]
    assert responses().count_documents({"survey_id": stored["_id"]}) == 1
    assert stats().find_one({"survey_id": stored["_id"]})["total"] == 0
    repaired = client.get(f"/api/surveys/{survey['id']}/stats", headers=auth_header(token))
    assert repaired.status_code == 200 and repaired.json()["total"] == 1
    assert stats().find_one({"survey_id": stored["_id"]})["total"] == 1
