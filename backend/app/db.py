"""MongoDB 连接与集合初始化。

四个集合：
- users     用户账号
- surveys   问卷（题目与跳转规则内嵌）
- responses 填写记录（含提交时的问卷快照，不可变）
- stats     预聚合统计计数器（提交时 $inc 原子更新）

每个集合都挂 $jsonSchema 校验器 + 必要索引。
"""
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, OperationFailure

import app.config as config

_client: MongoClient | None = None


def get_db():
    """返回数据库对象（单例连接）。"""
    global _client
    if _client is None:
        _client = MongoClient(config.MONGODB_URI)
    return _client[config.DB_NAME]


# ---------- 集合访问 ----------

def users():
    return get_db()["users"]


def surveys():
    return get_db()["surveys"]


def responses():
    return get_db()["responses"]


def stats():
    return get_db()["stats"]


# ---------- $jsonSchema 校验器 ----------

USERS_SCHEMA = {
    "bsonType": "object",
    "required": ["username", "password_hash", "created_at"],
    "properties": {
        "username": {"bsonType": "string", "minLength": 1},
        "password_hash": {"bsonType": "string"},
        "created_at": {"bsonType": "date"},
    },
}

SURVEYS_SCHEMA = {
    "bsonType": "object",
    "required": ["title", "owner_id", "status", "version", "questions", "share_token"],
    "properties": {
        "title": {"bsonType": "string"},
        "owner_id": {"bsonType": "objectId"},
        "status": {"enum": ["draft", "published", "closed"]},
        "version": {"bsonType": "int", "minimum": 1},
        "questions": {"bsonType": "array"},
        "share_token": {"bsonType": "string"},
    },
}

RESPONSES_SCHEMA = {
    "bsonType": "object",
    "required": ["survey_id", "survey_version", "snapshot", "answers", "submitted_at"],
    "properties": {
        "survey_id": {"bsonType": "objectId"},
        "survey_version": {"bsonType": "int"},
        "snapshot": {"bsonType": "object"},
        "answers": {"bsonType": "object"},
        "submitted_at": {"bsonType": "date"},
    },
}

STATS_SCHEMA = {
    "bsonType": "object",
    "required": ["survey_id", "total", "questions"],
    "properties": {
        "survey_id": {"bsonType": "objectId"},
        "total": {"bsonType": "int", "minimum": 0},
        "questions": {"bsonType": "object"},
    },
}


def _ensure_collection(db, name: str, schema: dict):
    """创建集合并挂 $jsonSchema 校验器（幂等）。"""
    if name not in db.list_collection_names():
        db.create_collection(name, validator={"$jsonSchema": schema})
    else:
        try:
            db.command("collMod", name, validator={"$jsonSchema": schema})
        except OperationFailure:
            pass  # 已存在的违规文档导致修改失败时保持原校验器


def init_db():
    """创建集合、校验器与索引。应用启动与测试前均调用，幂等。"""
    db = get_db()
    _ensure_collection(db, "users", USERS_SCHEMA)
    _ensure_collection(db, "surveys", SURVEYS_SCHEMA)
    _ensure_collection(db, "responses", RESPONSES_SCHEMA)
    _ensure_collection(db, "stats", STATS_SCHEMA)

    users().create_index("username", unique=True)
    surveys().create_index("owner_id")
    surveys().create_index("share_token", unique=True)
    responses().create_index([("survey_id", 1), ("submitted_at", -1)])
    # 同一问卷同一填写者只允许一份（respondent_key 原子去重）
    responses().create_index([("survey_id", 1), ("respondent_key", 1)], unique=True)
    stats().create_index("survey_id", unique=True)
