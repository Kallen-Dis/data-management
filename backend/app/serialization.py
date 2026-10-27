from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException


def object_id(value, message="记录不存在"):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError, ValueError):
        raise HTTPException(404, message)


def json_value(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def document_view(document):
    return json_value({"id": document["_id"], **{key: value for key, value in document.items() if key != "_id"}})
