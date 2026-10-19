"""FastAPI 依赖：当前登录用户（必须登录 / 可选登录）。"""
from bson import ObjectId
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import users as users_col
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """必须登录：解析 Bearer 令牌并返回用户文档，否则 401。"""
    if cred is None:
        raise HTTPException(401, "未登录")
    payload = decode_access_token(cred.credentials)
    if payload is None:
        raise HTTPException(401, "登录已过期，请重新登录")
    try:
        user = users_col().find_one({"_id": ObjectId(payload["sub"])})
    except Exception:
        user = None
    if user is None:
        raise HTTPException(401, "用户不存在")
    return user


def get_optional_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict | None:
    """可选登录：用于匿名问卷填写端，带有效令牌则返回用户，否则 None。"""
    if cred is None:
        return None
    payload = decode_access_token(cred.credentials)
    if payload is None:
        return None
    try:
        return users_col().find_one({"_id": ObjectId(payload["sub"])})
    except Exception:
        return None
