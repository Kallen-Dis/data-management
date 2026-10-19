"""并发提交测试：多线程同时提交 100 份答卷，$inc 原子计数必须精确等于 100。

这是"如何保证多人同时填写"的硬证据，报告中引用本测试输出。
"""
from concurrent.futures import ThreadPoolExecutor

from app.db import stats as stats_col
from tests.conftest import auth_header, make_survey, register


def submit_one(client, token, share_token, i):
    answers = {"q1": ["男"], "q3": str(20 + i % 30), "q4": f"并发答卷 {i}"}
    r = client.post(f"/api/s/{share_token}/responses",
                    json={"answers": answers}, headers=auth_header(token))
    return r.status_code


def test_100_concurrent_submissions_count_exact(client):
    """allow_multiple_submissions=True 时 100 线程并发提交，计数必须 = 100。"""
    token = register(client)
    r = client.post("/api/surveys", json=make_survey(allow_multiple_submissions=True),
                    headers=auth_header(token))
    s = r.json()
    client.post(f"/api/surveys/{s['id']}/publish", headers=auth_header(token))

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(
            lambda i: submit_one(client, token, s["share_token"], i), range(100)))
    assert all(code == 201 for code in results), set(results)

    from bson import ObjectId
    st = stats_col().find_one({"survey_id": ObjectId(s["id"])})
    assert st is not None
    assert st["total"] == 100
