"""问卷管理测试：创建（含四种题型落库）、列表隔离、越权 403、
乐观锁 409、环检测拒绝、死题警告、发布/关闭状态机。"""
from tests.conftest import auth_header, make_survey, register


def create_survey(client, token, body=None):
    r = client.post("/api/surveys", json=body or make_survey(), headers=auth_header(token))
    assert r.status_code == 201, r.text
    return r.json()


class TestCreateSurvey:
    def test_create_with_all_question_types(self, client):
        token = register(client)
        s = create_survey(client, token)
        types = {q["type"] for q in s["questions"]}
        assert {"single", "multiple", "number", "text"} <= types
        assert s["status"] == "draft"
        assert s["version"] == 1
        assert s["share_token"]
        # order 由后端重排
        orders = [q["order"] for q in s["questions"]]
        assert orders == sorted(orders)

    def test_cycle_rejected(self, client):
        token = register(client)
        body = make_survey()
        body["questions"] = [
            {"qid": "q1", "type": "single", "title": "t1", "options": ["a"],
             "jump_rules": [{"when": {"op": "eq", "value": "a"}, "goto": "q2"}]},
            {"qid": "q2", "type": "single", "title": "t2", "options": ["b"],
             "jump_rules": [{"when": {"op": "eq", "value": "b"}, "goto": "q1"}]},
        ]
        r = client.post("/api/surveys", json=body, headers=auth_header(token))
        assert r.status_code == 400
        assert "循环" in r.json()["detail"]

    def test_bad_goto_rejected(self, client):
        token = register(client)
        body = make_survey()
        body["questions"][0]["jump_rules"] = [{"when": {"op": "eq", "value": "男"}, "goto": "qX"}]
        r = client.post("/api/surveys", json=body, headers=auth_header(token))
        assert r.status_code == 400

    def test_publish_requires_questions(self, client):
        token = register(client)
        body = make_survey(questions=[])
        s = create_survey(client, token, body)
        r = client.post(f"/api/surveys/{s['id']}/publish", headers=auth_header(token))
        assert r.status_code == 400


class TestOwnership:
    def test_list_only_own_surveys(self, client):
        t1, t2 = register(client, "alice"), register(client, "bob", "password2")
        create_survey(client, t1)
        r = client.get("/api/surveys", headers=auth_header(t2))
        assert r.status_code == 200 and r.json() == []

    def test_foreign_survey_forbidden(self, client):
        t1, t2 = register(client, "alice"), register(client, "bob", "password2")
        s = create_survey(client, t1)
        for method in ("get", "put"):
            r = client.request(method, f"/api/surveys/{s['id']}",
                               headers=auth_header(t2), json={"version": 1, "title": "x", "questions": []})
            assert r.status_code == 403


class TestOptimisticLock:
    def test_stale_version_conflict(self, client):
        token = register(client)
        s = create_survey(client, token)
        body = make_survey()
        # 用旧版本号保存 → 409
        r = client.put(f"/api/surveys/{s['id']}", json={**body, "version": s["version"]},
                       headers=auth_header(token))
        assert r.status_code == 200
        # 第二次再用同一个旧版本 → 409
        r = client.put(f"/api/surveys/{s['id']}", json={**body, "version": s["version"]},
                       headers=auth_header(token))
        assert r.status_code == 409
        # 新版本可正常保存
        r = client.put(f"/api/surveys/{s['id']}", json={**body, "version": s["version"] + 1},
                       headers=auth_header(token))
        assert r.status_code == 200
        assert r.json()["version"] == s["version"] + 2


class TestDeadQuestionWarning:
    def test_unreachable_warning_returned(self, client):
        token = register(client)
        body = make_survey()
        # q1 单选覆盖全部选项都跳 q3 → q2 死题目
        body["questions"][0]["jump_rules"] = [
            {"when": {"op": "eq", "value": "男"}, "goto": "q3"},
            {"when": {"op": "eq", "value": "女"}, "goto": "q3"},
            {"when": {"op": "eq", "value": "其他"}, "goto": "q3"},
        ]
        s = create_survey(client, token, body)
        r = client.put(f"/api/surveys/{s['id']}", json={**body, "version": s["version"]},
                       headers=auth_header(token))
        assert r.status_code == 200
        assert "q2" in r.json()["warnings"]


class TestStateMachine:
    def test_publish_then_close(self, client):
        token = register(client)
        s = create_survey(client, token)
        pub = client.post(f"/api/surveys/{s['id']}/publish", headers=auth_header(token))
        assert pub.status_code == 200 and pub.json()["status"] == "published"
        assert pub.json()["published_at"] is not None
        closed = client.post(f"/api/surveys/{s['id']}/close", headers=auth_header(token))
        assert closed.status_code == 200 and closed.json()["status"] == "closed"
        again = client.post(f"/api/surveys/{s['id']}/close", headers=auth_header(token))
        assert again.status_code == 409

    def test_reopen_closed_survey(self, client):
        token = register(client)
        s = create_survey(client, token)
        client.post(f"/api/surveys/{s['id']}/publish", headers=auth_header(token))
        client.post(f"/api/surveys/{s['id']}/close", headers=auth_header(token))
        r = client.post(f"/api/surveys/{s['id']}/publish", headers=auth_header(token))
        assert r.status_code == 200 and r.json()["status"] == "published"
