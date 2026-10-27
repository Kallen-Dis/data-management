# API 说明

## 第二阶段 API（2026-10-23）

新增接口全部要求 JWT。`series_id` 是题目系列，`version_id` 是不可变版本，不能与问卷局部 qid 混用。详细请求体以运行中的 OpenAPI 为准。

- `POST /api/questions`：创建系列及 v1，提交 `content / tags / change_note`。
- `GET /api/questions`：按 `scope=mine|shared`、`search`、`archived`、`page / page_size` 列表，返回 `items / total`。
- `GET /api/questions/{series_id}`、`GET .../versions`：授权后的题目详情和可见版本历史。
- `PATCH /api/questions/{series_id}`：修改名称、标签、归档或展示状态，提交 `revision`。
- `POST /api/questions/{series_id}/versions`：新版本，提交 `content / parent_version_id / expected_revision / change_note`。
- `PUT /api/questions/{series_id}/draft`：同样结构保存工作草稿，不创建正式版本。
- `POST /api/questions/{series_id}/restore`：提交 `source_version_id / expected_revision / change_note`，创建恢复版本；不覆盖历史。
- `GET /api/question-versions/{version_id}`、`POST .../fork`：查看单版或派生自己的系列。
- `POST /api/questions/{series_id}/shares`：`username / version_ids / all_versions / allow_fork / expected_revision`。
- `DELETE /api/questions/{series_id}/shares/{user_id}?revision=...`：撤销共享。
- `GET /api/questions/{series_id}/usages?version_id=...`：只返回有权查看的引用问卷。
- `POST /api/question-banks`、`GET /api/question-banks`、`PATCH /api/question-banks/{bank_id}`：创建、列表、修改/归档题库，修改带 `revision`。
- `GET /api/question-banks/{bank_id}/items`、`POST .../items`：条目列表或以 `version_id` 收录题目。
- `PATCH /api/question-banks/{bank_id}/items/{item_id}`：`version_id / revision` 切换同系列固定版本；`DELETE` 仅移出，不删除题目。
- `GET /api/question-versions/{version_id}/stats`：可选重复 `survey_ids`、`start / end`（ISO 时间）、文本 `offset / limit`。返回作答/答卷/问卷数量，及题型相关分布、数字聚合或授权后的文本分页。
- `GET /api/questions/{series_id}/stats`：按版本分别返回统计，不自动合并不同版本。
- `POST /api/surveys/{survey_id}/clone`：独立新草稿，不复制答卷和聚合授权。
- `POST /api/surveys/{survey_id}/questions/{qid}/library`：保存题目并返回更新后的题目与问卷。
- `PUT /api/surveys/{survey_id}/question-stats-sharing`：`version / grants`，每个 grant 包含 `question_version_id / username`，只授予聚合权限。

原问卷创建/保存也接受 `{qid, question_version_id}` 最小引用，服务器填充内容；若携带与正式版本不一致的内容，返回 409。保存已发布/已关闭题目结构返回 409；发布、关闭会推进问卷 version。

提交接口在答卷已保存但统计缓存失败时仍返回 201，并附加 `stats_pending=true`；后续统计读取会修复。业务权限不足返回 403；不存在/非法 ID 返回 404；陈旧修订返回 409；请求格式不合法返回 422。

以下保留第一阶段 API 摘要；冲突行为以本节和当前 OpenAPI 为准。

后端基于 FastAPI，启动后访问 **http://localhost:8000/docs** 可查看自动生成的
OpenAPI 交互式文档（本文件为其文字版摘要）。除填写端接口外，其余接口均需
请求头 `Authorization: Bearer <JWT>`。

## 1. 认证 `/api/auth`

| 方法 | 路径 | 说明 | 成功 | 失败 |
|------|------|------|------|------|
| POST | /api/auth/register | 注册 {username(2-20), password(≥6)} | 201 {access_token, username} | 409 用户名已存在 / 422 格式错误 |
| POST | /api/auth/login | 登录 | 200 {access_token, username} | 401 用户名或密码错误 |

## 2. 问卷管理 `/api/surveys`（需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/surveys | 创建问卷（草稿），可携带完整题目与跳转规则；执行结构校验 + 环检测 |
| GET | /api/surveys | 我的问卷列表（含状态、回答数、截止时间） |
| GET | /api/surveys/{id} | 问卷详情（owner 视角，含 share_token、version、跳转规则） |
| PUT | /api/surveys/{id} | 整体保存（**乐观锁**：body 需带 version，冲突 409）；返回新 version 与死题 warnings |
| POST | /api/surveys/{id}/publish | 发布（需至少 1 题；draft/closed → published） |
| POST | /api/surveys/{id}/close | 关闭（published → closed） |

非 owner 访问一律 **403**。

### 创建/保存请求体示例

```json
{
  "title": "大学生消费习惯调查",
  "description": "感谢参与！",
  "allow_anonymous": false,
  "allow_multiple_submissions": false,
  "deadline": null,
  "version": 7,
  "questions": [
    {
      "qid": "q1", "type": "single", "title": "你的性别", "required": true,
      "options": ["男", "女", "其他"],
      "jump_rules": [
        { "when": { "op": "eq", "value": "男" }, "goto": "q3" },
        { "when": { "op": "eq", "value": "女" }, "goto": "q2" }
      ]
    },
    { "qid": "q2", "type": "multiple", "title": "你喜欢的水果", "required": true,
      "options": ["苹果", "香蕉", "西瓜", "葡萄"], "min_select": 1, "max_select": 2 },
    { "qid": "q3", "type": "number", "title": "你的年龄", "required": true,
      "num_min": 0, "num_max": 120, "integer_only": true },
    { "qid": "q4", "type": "text", "title": "你的建议",
      "text_min_len": 1, "text_max_len": 50 }
  ]
}
```

## 3. 填写端 `/api/s/{token}`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/s/{token} | 获取问卷（题目 + 约束 + 跳转规则）；403 未发布/已关闭/已截止；非匿名问卷未登录 401 |
| GET | /api/s/{token}/status | 填写状态（can_submit、expired、allow_anonymous…） |
| POST | /api/s/{token}/responses | 提交答卷（详见下） |

### 提交流程（服务端强校验，全部在此完成）

1. 状态校验：published？未截止？
2. 登录校验：非匿名问卷必须带有效 JWT
3. **跳转引擎执行**：simulate_flow 计算实际到达的题目序列
4. **校验引擎**：只校验实际到达题目的答案
5. 构造**问卷快照** + 过滤后的答案 → 单文档原子插入
6. 唯一索引原子防重复提交（409 "你已经提交过这份问卷"）
7. stats `$inc` 原子更新计数

请求体：`{ answers: {"q1": ["男"], "q3": "20"}, spent_seconds: 42, anon_id: "anon-xxx" }`
（anon_id 仅匿名问卷需要）。

响应 201：`{ ok: true, visited: ["q1","q3","q4"], submitted_at: "..." }`
错误：401 需登录 / 403 已截止 / 409 重复提交 / 422 `[{question_id, message}]` 答案不合法。

## 4. 统计 `/api/surveys/{id}`（需登录，owner）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/surveys/{id}/stats | 整卷统计（total + 每题 counts / avg） |
| GET | /api/surveys/{id}/stats/{qid} | 单题统计 |
| GET | /api/surveys/{id}/responses | 答卷明细（文本全量、数字均值来源），时间倒序 |
| POST | /api/surveys/{id}/stats/rebuild | 慢通道：按快照聚合重建 stats |

## 5. 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /healthz | 健康检查 |

## 6. 统一约定

- 所有时间字段为 ISO 8601 字符串
- ObjectId 在响应中转字符串
- 错误统一格式：HTTPException `{detail: "中文消息"}`；答案校验错误为 `[{question_id, message}]`
