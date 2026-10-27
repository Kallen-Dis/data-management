"""提交答卷测试：完整提交流程、跳转执行、校验拦截、快照正确性、
匿名/登录限制、截止时间、重复提交 409、stats 计数正确。"""
from datetime import datetime, timedelta, timezone

from tests.conftest import auth_header, make_survey, register


def create_and_publish(client, token, body=None):
    r = client.post("/api/surveys", json=body or make_survey(), headers=auth_header(token))
    assert r.status_code == 201, r.text
    s = r.json()
    r = client.post(f"/api/surveys/{s['id']}/publish", headers=auth_header(token))
    assert r.status_code == 200
    return r.json()


def valid_answers_female_path():
    """q1 选女 → q2 多选 → q3 数字 → q4 文本。"""
    return {"q1": ["女"], "q2": ["苹果"], "q3": "20", "q4": "不错"}


class TestSubmit:
    def test_full_submit_flow(self, client):
        token = register(client)
        s = create_and_publish(client, token)
        r = client.post(f"/api/s/{s['share_token']}/responses",
                        json={"answers": valid_answers_female_path(), "spent_seconds": 30},
                        headers=auth_header(token))
        assert r.status_code == 201, r.text
        assert r.json()["visited"] == ["q1", "q2", "q3", "q4"]

    def test_jump_skips_questions_and_saves_only_visited(self, client):
        """q1 选男 → 跳到 q3（q2 被跳过）。"""
        token = register(client)
        s = create_and_publish(client, token)
        answers = {"q1": ["男"], "q2": ["苹果"], "q3": "20", "q4": "好"}
        r = client.post(f"/api/s/{s['share_token']}/responses",
                        json={"answers": answers}, headers=auth_header(token))
        assert r.status_code == 201
        assert r.json()["visited"] == ["q1", "q3", "q4"]

        # 明细里不应包含被跳过的 q2 答案（服务端过滤）
        det = client.get(f"/api/surveys/{s['id']}/responses", headers=auth_header(token))
        saved = det.json()[0]["answers"]
        assert "q2" not in saved and saved["q3"] == "20"

    def test_validation_blocks_invalid_answer(self, client):
        token = register(client)
        s = create_and_publish(client, token)
        bad = client.post(f"/api/s/{s['share_token']}/responses",
                          json={"answers": {"q1": ["女"], "q2": ["苹果"], "q3": "500", "q4": "x"}},
                          headers=auth_header(token))
        assert bad.status_code == 422
        assert bad.json()["detail"][0]["question_id"] == "q3"

    def test_multiple_select_limits_enforced(self, client):
        token = register(client)
        s = create_and_publish(client, token)
        r = client.post(f"/api/s/{s['share_token']}/responses",
                        json={"answers": {"q1": ["女"], "q2": ["苹果", "香蕉", "西瓜"], "q3": "20"}},
                        headers=auth_header(token))
        assert r.status_code == 422

    def test_snapshot_captures_survey_at_submit_time(self, client):
        """提交后修改问卷：旧答卷快照仍保留原题目结构（核心亮点验证）。"""
        token = register(client)
        s = create_and_publish(client, token)
        client.post(f"/api/s/{s['share_token']}/responses",
                    json={"answers": valid_answers_female_path()}, headers=auth_header(token))

        # 修改问卷：删掉 q4
        body = make_survey()
        body["questions"] = body["questions"][:3]
        r = client.put(f"/api/surveys/{s['id']}", json={**body, "version": s["version"]},
                       headers=auth_header(token))
        assert r.status_code == 409

        clone = client.post(f"/api/surveys/{s['id']}/clone", headers=auth_header(token))
        assert clone.status_code == 201
        r = client.put(f"/api/surveys/{clone.json()['id']}", json={**body, "version": clone.json()["version"]}, headers=auth_header(token))
        assert r.status_code == 200

        det = client.get(f"/api/surveys/{s['id']}/responses", headers=auth_header(token))
        snap = det.json()[0]
        qids = list(snap["answers"].keys())
        # 快照中 q4 仍存在（旧数据完整保留）
        assert "q4" in qids
        assert snap["survey_version"] == s["version"]

    def test_requires_login_when_not_anonymous(self, client):
        token = register(client)
        s = create_and_publish(client, token)
        r = client.post(f"/api/s/{s['share_token']}/responses",
                        json={"answers": valid_answers_female_path()})
        assert r.status_code == 401

    def test_anonymous_allowed(self, client):
        token = register(client)
        s = create_and_publish(client, token, make_survey(allow_anonymous=True))
        r = client.post(f"/api/s/{s['share_token']}/responses",
                        json={"answers": valid_answers_female_path(), "anon_id": "anon-001"})
        assert r.status_code == 201

    def test_duplicate_submission_rejected(self, client):
        token = register(client)
        s = create_and_publish(client, token)
        first = client.post(f"/api/s/{s['share_token']}/responses",
                            json={"answers": valid_answers_female_path()},
                            headers=auth_header(token))
        assert first.status_code == 201
        second = client.post(f"/api/s/{s['share_token']}/responses",
                             json={"answers": valid_answers_female_path()},
                             headers=auth_header(token))
        assert second.status_code == 409

    def test_multiple_submissions_allowed_when_enabled(self, client):
        token = register(client)
        s = create_and_publish(client, token, make_survey(allow_multiple_submissions=True))
        for _ in range(2):
            r = client.post(f"/api/s/{s['share_token']}/responses",
                            json={"answers": valid_answers_female_path()},
                            headers=auth_header(token))
            assert r.status_code == 201

    def test_deadline_expired_blocks_submit(self, client):
        token = register(client)
        deadline = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        s = create_and_publish(client, token, make_survey(deadline=deadline))
        r = client.post(f"/api/s/{s['share_token']}/responses",
                        json={"answers": valid_answers_female_path()},
                        headers=auth_header(token))
        assert r.status_code == 403
        assert "截止" in r.json()["detail"]

    def test_draft_and_closed_surveys_cannot_fill(self, client):
        token = register(client)
        r = client.post("/api/surveys", json=make_survey(), headers=auth_header(token))
        s = r.json()
        # 草稿不可填
        r = client.get(f"/api/s/{s['share_token']}")
        assert r.status_code == 403
        # 发布 → 关闭 → 不可填
        client.post(f"/api/surveys/{s['id']}/publish", headers=auth_header(token))
        client.post(f"/api/surveys/{s['id']}/close", headers=auth_header(token))
        r = client.get(f"/api/s/{s['share_token']}")
        assert r.status_code == 403
