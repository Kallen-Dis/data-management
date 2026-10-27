"""MongoDB 连接与集合初始化。

第一阶段四个集合：
- users     用户账号
- surveys   问卷（题目与跳转规则内嵌）
- responses 填写记录（含提交时的问卷快照，不可变）
- stats     预聚合统计计数器（提交时 $inc 原子更新）

第二阶段增加 question_series / question_versions / question_banks /
question_bank_items / legacy_question_bindings，保留原始答卷快照。

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


def question_series():
    return get_db()["question_series"]


def question_versions():
    return get_db()["question_versions"]


def question_banks():
    return get_db()["question_banks"]


def question_bank_items():
    return get_db()["question_bank_items"]


def legacy_question_bindings():
    return get_db()["legacy_question_bindings"]


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
        "schema_version": {"bsonType": "int"},
        "ever_published": {"bsonType": "bool"},
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
        "schema_version": {"bsonType": "int"},
        "visited_qids": {"bsonType": "array", "items": {"bsonType": "string"}},
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
    schemas = {
        "question_series": {
            "required": ["owner_id", "name", "revision", "next_version_no"],
            "properties": {"owner_id": {"bsonType": "objectId"}, "name": {"bsonType": "string"}, "revision": {"bsonType": "int", "minimum": 1},
                "next_version_no": {"bsonType": "int", "minimum": 1}, "shared_with": {"bsonType": "array", "items": {"bsonType": "object", "required": ["user_id", "version_ids", "all_versions"],
                    "properties": {"user_id": {"bsonType": "objectId"}, "version_ids": {"bsonType": "array", "items": {"bsonType": "objectId"}}, "all_versions": {"bsonType": "bool"}}}}},
        },
        "question_versions": {
            "required": ["series_id", "version_no", "content", "created_by", "created_at"],
            "properties": {"series_id": {"bsonType": "objectId"}, "version_no": {"bsonType": "int", "minimum": 1}, "content": {"bsonType": "object", "required": ["type", "title"],
                "properties": {"type": {"enum": ["single", "multiple", "text", "number"]}, "title": {"bsonType": "string"}, "options": {"bsonType": "array", "items": {"bsonType": "string"}}}},
                "created_by": {"bsonType": "objectId"}, "created_at": {"bsonType": "date"}},
        },
        "question_banks": {"required": ["owner_id", "name", "revision"], "properties": {"owner_id": {"bsonType": "objectId"}, "name": {"bsonType": "string", "minLength": 1}, "revision": {"bsonType": "int", "minimum": 1}}},
        "question_bank_items": {"required": ["bank_id", "series_id", "selected_version_id", "revision"], "properties": {"bank_id": {"bsonType": "objectId"}, "series_id": {"bsonType": "objectId"}, "selected_version_id": {"bsonType": "objectId"}, "revision": {"bsonType": "int", "minimum": 1}}},
        "legacy_question_bindings": {"required": ["survey_id", "survey_version", "qid", "snapshot_fingerprint", "question_version_id"], "properties": {"survey_id": {"bsonType": "objectId"}, "survey_version": {"bsonType": "int"}, "qid": {"bsonType": "string"}, "question_version_id": {"bsonType": "objectId"}}},
    }
    for name, schema in schemas.items():
        _ensure_collection(db, name, {"bsonType": "object", **schema})
    question_series().create_index([("owner_id", 1), ("updated_at", -1)])
    question_series().create_index("shared_with.user_id")
    question_series().create_index("origin_key", unique=True, sparse=True)
    question_versions().create_index([("series_id", 1), ("version_no", 1)], unique=True)
    question_versions().create_index("parent_version_id")
    question_versions().create_index("derived_from_version_id")
    question_banks().create_index([("owner_id", 1), ("updated_at", -1)])
    question_bank_items().create_index([("bank_id", 1), ("series_id", 1)], unique=True)
    question_bank_items().create_index("selected_version_id")
    surveys().create_index([("questions.question_version_id", 1), ("owner_id", 1)])
    surveys().create_index("questions.question_series_id")
    responses().create_index([("snapshot.questions.question_version_id", 1), ("survey_id", 1), ("submitted_at", -1)])
    legacy_question_bindings().create_index([("survey_id", 1), ("survey_version", 1), ("qid", 1), ("snapshot_fingerprint", 1)], unique=True)
    legacy_question_bindings().create_index("question_version_id")
