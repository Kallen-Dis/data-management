"""pytest 公共设施：独立测试库、每用例前后清库、登录辅助函数。"""
import os

os.environ.setdefault("DB_NAME", "survey_db_test")  # 必须在 import app 之前设置

import pytest
from fastapi.testclient import TestClient

from app.db import get_db, init_db
from app.main import app

if os.getenv("SURVEY_TEST_MOCK") == "1":
    import mongomock
    import app.db as database_module
    database_module._client = mongomock.MongoClient()

    def ensure_mock_collection(database, name, schema):
        if name not in database.list_collection_names():
            database.create_collection(name)

    database_module._ensure_collection = ensure_mock_collection


def pytest_configure(config):
    config.addinivalue_line("markers", "mongo: requires real MongoDB aggregation")


def pytest_collection_modifyitems(items):
    if os.getenv("SURVEY_TEST_MOCK") == "1":
        for item in items:
            if "mongo" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="MongoDB 聚合需在真实数据库回归中执行"))

COLLECTIONS = ("users", "surveys", "responses", "stats", "question_series", "question_versions", "question_banks", "question_bank_items", "legacy_question_bindings")


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试用例前后清空测试库，保证用例相互独立。"""
    if not get_db().name.endswith("_test"):
        raise RuntimeError("测试只允许使用名称以 _test 结尾的数据库")
    init_db()
    db = get_db()
    for name in COLLECTIONS:
        db[name].delete_many({})
    yield
    for name in COLLECTIONS:
        db[name].delete_many({})


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def register(client, username="alice", password="secret123"):
    """注册并返回 access_token。"""
    r = client.post("/api/auth/register", json={"username": username, "password": password})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_survey(**overrides) -> dict:
    """构造问卷请求体（含单选/多选/文本/数字四种题型与跳转规则）。"""
    body = {
        "title": "大学生消费习惯调查",
        "description": "本问卷用于课程项目演示",
        "allow_anonymous": False,
        "allow_multiple_submissions": False,
        "questions": [
            {"qid": "q1", "type": "single", "title": "你的性别",
             "required": True, "options": ["男", "女", "其他"],
             "jump_rules": [{"when": {"op": "eq", "value": "男"}, "goto": "q3"},
                            {"when": {"op": "eq", "value": "女"}, "goto": "q2"}]},
            {"qid": "q2", "type": "multiple", "title": "你喜欢的水果",
             "required": True, "options": ["苹果", "香蕉", "西瓜", "葡萄"],
             "min_select": 1, "max_select": 2},
            {"qid": "q3", "type": "number", "title": "你的年龄",
             "required": True, "num_min": 0, "num_max": 120, "integer_only": True},
            {"qid": "q4", "type": "text", "title": "你的建议",
             "required": False, "text_min_len": 1, "text_max_len": 50},
        ],
    }
    body.update(overrides)
    return body
