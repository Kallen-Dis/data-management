# 问卷星球 SurveyGo —— 基于 MongoDB 的问卷系统

> 当代数据管理课程项目（第一阶段）。技术栈：**FastAPI + MongoDB + Vue 3 + ECharts**。

## 目录结构

```
survey-system/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── main.py         # 应用入口（CORS、路由注册、启动初始化）
│   │   ├── config.py       # 环境变量配置
│   │   ├── db.py           # MongoDB 连接、$jsonSchema 校验器、索引
│   │   ├── security.py     # bcrypt 密码哈希 + JWT
│   │   ├── deps.py         # 登录依赖（必须登录 / 可选登录）
│   │   ├── models/         # Pydantic 模型（即 API 文档数据契约）
│   │   ├── routers/        # auth / surveys / submit / stats
│   │   └── services/       # 核心引擎（与接口层分离，可独立单测）
│   │       ├── jump_engine.py   # 跳转引擎：图遍历 + 环检测 + 死题检测
│   │       ├── validator.py     # 声明式校验引擎
│   │       └── stats_service.py # 统计引擎：$inc 预聚合 + 聚合重建
│   └── tests/              # pytest：61 个用例（含 100 并发提交测试）
├── frontend/               # Vue 3 + Vite + Element Plus + ECharts
│   └── src/
│       ├── jump.js         # 前端跳转/校验引擎（与后端语义一致的镜像）
│       └── views/          # Login / Dashboard / Editor / Fill / Stats
├── docs/                   # 提交文档（系统说明/数据库设计/API说明/关键逻辑/测试/报告/AI日志）
└── .mongo-data/            # 本地 MongoDB 数据目录（开发用）
```

## 运行方法

### 0. 启动 MongoDB（本地数据目录）

```powershell
mongod --dbpath .mongo-data --port 27017 --bind_ip 127.0.0.1
```

### 1. 启动后端（端口 8000）

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

打开 http://localhost:8000/docs 可查看自动生成的 OpenAPI 文档（即 API 说明）。

### 2. 启动前端（端口 5173）

```powershell
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 ，前端 `/api` 请求自动代理到后端。

### 3. 运行测试

```powershell
cd backend
python -m pytest tests -q
```

> 测试使用独立的 `survey_db_test` 数据库，每个用例前后自动清空，可反复运行。

## 核心亮点（对应报告章节）

1. **响应快照**：每份答卷内嵌提交瞬间的问卷题目副本 → 问卷修改后旧数据统计依然准确
2. **跳转图引擎**：问卷建模为有向图，DFS 环检测 + 可达性死题检测，规则数据驱动
3. **声明式校验**：约束存于题目文档，校验器只解释规则
4. **双通道统计**：提交时 `$inc` 原子预聚合（O(1) 查询）+ 基于答卷快照重建；稳定摘要键使选项改序后仍能正确归档
5. **并发正确性**：单文档原子插入、唯一索引防重复提交、`version` 乐观锁
