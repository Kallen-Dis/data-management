# 问卷星球 SurveyGo —— 基于 MongoDB 的问卷系统

> 当代数据管理课程项目（第一、二阶段）。技术栈：**FastAPI + MongoDB + Vue 3 + ECharts**。第二阶段在原项目上扩展，没有重做第一阶段。

第二阶段正式报告：[PDF](docs/2026_ECNU_PJ1_2_张贤柯.pdf) · [Markdown 源文](docs/第二阶段项目完成报告.md)。按课程要求，水杉提交 PDF；修改后的代码保留在本仓库。

## 第二阶段：题目资产与跨问卷洞察

- **题目中心**：独立创建、从问卷保存、跨问卷引用、搜索及归档。
- **不可变版本**：父版本、分支、工作草稿、字段比较、恢复为新版本；问卷始终固定具体版本。
- **定向共享**：指定用户、指定版本或全部现有及未来版本；可限制派生，撤销不破坏已有问卷。
- **永久发布锁**：已发布或已关闭问卷不能改题；需要调整时复制为新草稿。
- **私人题库**：固定选用版本，手动升级，不级联改变已有问卷。
- **跨问卷单题统计**：版本分组、日期过滤、选项分布、数值加权均值及直方图；题目共享不等于答卷授权，跨用户文本仅开放计数。
- **兼容迁移**：默认只读预演、自动 BSON 备份、幂等关联、原答卷摘要校验；不猜测旧快照里缺失的约束。

完整实施说明、数据结构、验收与回滚见 [第二阶段实施与验收](docs/第二阶段实施与验收.md)。[原修改方案](docs/第二阶段修改方案.md)保留设计演进依据。

### 简单示例题库

提供六道校园生活题目，覆盖单选、多选、数字和文本。数据文件、内容说明及重复导入方法见 [示例题库](examples/README.md)。在项目根目录执行下列命令，将用户名替换为自己已注册的账号；去掉 `--apply` 可先只读预览：

```powershell
backend/.venv/Scripts/python.exe backend/scripts/seed_question_bank.py --database survey_db --owner '你的用户名' --apply
```

不会创建账号、覆盖旧题版本或生成模拟答卷；导入后进入“我的题库”查看。

### 推荐启动方式（Windows）

在项目根目录运行，使用已安装的后端虚拟环境与前端依赖：

```powershell
.\scripts\Start-Local.ps1 -Npm 'D:\Program Files\nodejs\npm.cmd'
```

默认只绑定本机，启动 MongoDB 27017、FastAPI 8000、Vite 5173。日志在 `.runtime/`。已占用端口不会被强行终止；首次迁移请按实施说明操作，启动脚本不自动修改旧数据。

访问 [本地系统](http://127.0.0.1:5173/) 或 [交互式接口文档](http://127.0.0.1:8000/docs)。部署到公网前必须配置 `JWT_SECRET`、数据库认证与 HTTPS，不能使用开发默认密钥。

### 推荐回归方式

先在单独窗口启动测试 MongoDB，数据目录与生产目录严格分开：

```powershell
New-Item -ItemType Directory -Force .mongo-test-data | Out-Null
& 'D:\MongoDB\Server\8.3\bin\mongod.exe' --dbpath .mongo-test-data --port 27018 --bind_ip 127.0.0.1
```

再在项目根目录运行：

```powershell
.\scripts\Test-Stage2.ps1 -Npm 'D:\Program Files\nodejs\npm.cmd'
```

测试只允许使用以 `_test` 结尾的库名，并会清空该测试库的项目集合。无 MongoDB 时可加 `-Mock`，但真实聚合与数据库校验器测试会跳过，不能替代完整验收。脚本退出时恢复环境变量，不影响原数据库配置。

### 首次安装

需要 Python 3.13、Node.js 与 MongoDB。首次创建环境：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cd frontend
npm ci
```

不要使用系统 Python 的全局 FastAPI/Starlette 混装环境。以下为原有目录及手动运行说明，第二阶段行为以本文新增说明为准。

GitHub 仓库：[https://github.com/Kallen-Dis/data-management](https://github.com/Kallen-Dis/data-management)

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
│   └── tests/              # pytest：含第二阶段、备份恢复与 100 并发提交回归
├── frontend/               # Vue 3 + Vite + Element Plus + ECharts
│   └── src/
│       ├── jump.js         # 前端跳转/校验引擎（与后端语义一致的镜像）
│       └── views/          # 原 5 页 + Questions / QuestionDetail / QuestionBanks / QuestionStats
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
4. **双通道统计**：提交时版本栅栏保护的 `$inc` + 冲突时基于答卷快照重建；读取校验答卷数量，修复缓存失败，不再把查询严格描述为 O(1)
5. **并发正确性**：单文档原子插入、唯一索引防重复提交、`version` 乐观锁
