"""认证接口：注册 / 登录。"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pymongo.errors import DuplicateKeyError

from app.db import users as users_col
from app.models.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest):
    if users_col().find_one({"username": req.username}):
        raise HTTPException(409, "用户名已存在")
    doc = {
        "username": req.username,
        "password_hash": hash_password(req.password),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = users_col().insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "用户名已存在")
    token = create_access_token(result.inserted_id, req.username)
    return TokenResponse(access_token=token, username=req.username)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    user = users_col().find_one({"username": req.username})
    if user is None or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    token = create_access_token(user["_id"], user["username"])
    return TokenResponse(access_token=token, username=user["username"])
