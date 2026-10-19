"""密码哈希（bcrypt）与 JWT 令牌。"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

import app.config as config


def hash_password(password: str) -> str:
    """bcrypt 加盐哈希，数据库中绝不存明文密码。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id, username: str) -> str:
    """签发 JWT：sub=用户 _id，exp=过期时间。"""
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """解析 JWT，无效或过期返回 None。"""
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
