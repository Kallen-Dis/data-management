"""Pydantic 请求/响应模型（同时作为 FastAPI 自动文档的数据契约）。"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------- 认证 ----------

class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=20)
    password: str = Field(min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


# ---------- 跳转规则 ----------
# when 形如 {"op": "eq", "value": "男"}，op 由跳转引擎解释，数据驱动不硬编码

class JumpRule(BaseModel):
    when: dict
    goto: str


# ---------- 题目 ----------

class Question(BaseModel):
    qid: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="问卷内唯一短 ID，如 q1，跳转规则引用它")
    type: Literal["single", "multiple", "text", "number"]
    title: str
    required: bool = False
    order: int = 0
    # single / multiple
    options: list[str] = Field(default_factory=list)
    # multiple：至少/最多选择数量
    min_select: int = 1
    max_select: Optional[int] = None
    # text：最少/最多字数
    text_min_len: int = 0
    text_max_len: Optional[int] = None
    # number：最小值/最大值/是否必须整数
    num_min: Optional[float] = None
    num_max: Optional[float] = None
    integer_only: bool = False
    jump_rules: list[JumpRule] = Field(default_factory=list)


# ---------- 问卷 ----------

class SurveyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    allow_anonymous: bool = False
    allow_multiple_submissions: bool = False
    deadline: Optional[datetime] = None
    questions: list[Question] = Field(default_factory=list)


class SurveyUpdate(SurveyCreate):
    version: int = Field(description="乐观锁版本号，与当前版本不一致时返回 409")


# ---------- 填写 ----------

class SubmitRequest(BaseModel):
    answers: dict[str, Any] = Field(description='答案映射，如 {"q1": ["男"], "q3": "20"}')
    spent_seconds: int = Field(default=0, ge=0, le=86400)
    anon_id: Optional[str] = Field(default=None, max_length=128, description="匿名问卷的浏览器标识（无痕去重用）")
