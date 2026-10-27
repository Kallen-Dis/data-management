"""FastAPI 应用入口：注册路由、CORS、启动时初始化数据库。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import auth, question_banks, question_stats, questions, stats, submit, surveys


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SurveyGo 问卷星球 API",
    description="基于 MongoDB 的问卷系统 —— 自动生成的 OpenAPI 文档即 API 说明",
    version="2.0.0",
    lifespan=lifespan,
)

# 开发环境放开跨域，前端 Vite 与后端不同端口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(surveys.router)
app.include_router(submit.router)
app.include_router(stats.router)
app.include_router(questions.router)
app.include_router(question_banks.router)
app.include_router(question_stats.router)


@app.get("/healthz", tags=["system"])
def healthz():
    return {"status": "ok"}
