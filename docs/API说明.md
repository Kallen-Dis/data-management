# API 说明

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
