"""统计测试：单选人数、多选次数、数字平均值与手工计算一致；
单题统计；重建统计（慢通道）与快通道结果一致。"""
from tests.conftest import auth_header, make_survey, register


def setup_with_responses(client, token, survey_body=None):
    r = client.post("/api/surveys", json=survey_body or make_survey(), headers=auth_header(token))
    s = r.json()
    client.post(f"/api/surveys/{s['id']}/publish", headers=auth_header(token))

    token2 = register(client, "bob", "password2")
    token3 = register(client, "carol", "password3")
    submissions = [
        (token, {"q1": ["男"], "q3": "20", "q4": "第一份"}),
        (token2, {"q1": ["女"], "q2": ["苹果", "香蕉"], "q3": "22", "q4": "第二份"}),
        (token3, {"q1": ["男"], "q3": "25", "q4": "第三份"}),
    ]
    for tok, answers in submissions:
        r = client.post(f"/api/s/{s['share_token']}/responses",
                        json={"answers": answers}, headers=auth_header(tok))
        assert r.status_code == 201, r.text
    return s


class TestStats:
    def test_total_and_single_counts(self, client):
        token = register(client)
        s = setup_with_responses(client, token)
        r = client.get(f"/api/surveys/{s['id']}/stats", headers=auth_header(token))
        assert r.status_code == 200
        view = r.json()
        assert view["total"] == 3
        q1 = next(q for q in view["questions"] if q["qid"] == "q1")
        # 男 2 人、女 1 人、其他 0 人
        assert q1["counts"] == [2, 1, 0]

    def test_multiple_counts(self, client):
        token = register(client)
        s = setup_with_responses(client, token)
        view = client.get(f"/api/surveys/{s['id']}/stats", headers=auth_header(token)).json()
        q2 = next(q for q in view["questions"] if q["qid"] == "q2")
        # 苹果 1 次、香蕉 1 次
        assert q2["counts"][0] == 1 and q2["counts"][1] == 1 and sum(q2["counts"]) == 2

    def test_number_average(self, client):
        token = register(client)
        s = setup_with_responses(client, token)
        view = client.get(f"/api/surveys/{s['id']}/stats", headers=auth_header(token)).json()
        q3 = next(q for q in view["questions"] if q["qid"] == "q3")
        # (20+22+25)/3 = 22.333... → 22.33
        assert q3["avg"] == 22.33
        assert q3["num_count"] == 3

    def test_question_stats_endpoint(self, client):
        token = register(client)
        s = setup_with_responses(client, token)
        r = client.get(f"/api/surveys/{s['id']}/stats/q1", headers=auth_header(token))
        assert r.status_code == 200 and r.json()["qid"] == "q1"

    def test_text_responses_listed(self, client):
        token = register(client)
        s = setup_with_responses(client, token)
        r = client.get(f"/api/surveys/{s['id']}/responses", headers=auth_header(token))
        assert r.status_code == 200
        texts = [d["answers"].get("q4") for d in r.json()]
        assert texts == ["第三份", "第二份", "第一份"]  # 按提交时间倒序

    def test_rebuild_matches_fast_channel(self, client):
        """慢通道重建与快通道 $inc 结果一致（双通道互相校验）。"""
        token = register(client)
        s = setup_with_responses(client, token)
        fast = client.get(f"/api/surveys/{s['id']}/stats", headers=auth_header(token)).json()
        client.post(f"/api/surveys/{s['id']}/stats/rebuild", headers=auth_header(token))
        slow = client.get(f"/api/surveys/{s['id']}/stats", headers=auth_header(token)).json()
        assert fast["total"] == slow["total"] == 3
        for qf, qs in zip(fast["questions"], slow["questions"]):
            if qf["type"] in ("single", "multiple"):
                assert qf["counts"] == qs["counts"]
            elif qf["type"] == "number":
                assert qf["avg"] == qs["avg"]
