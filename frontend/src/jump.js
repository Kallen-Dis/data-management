// 前端跳转引擎（与后端 jump_engine.py 语义一致的 JS 镜像）
// 用途：填写端与编辑器预览的即时跳转体验；服务端仍是唯一可信校验边界。

const num = (a) => {
  const text = typeof a === 'string' ? a.trim() : ''
  if (typeof a !== 'number' && !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text)) return null
  const v = typeof a === 'number' ? a : Number(text)
  return Number.isFinite(v) ? v : null
}

const textLength = (value) => Array.from(value).length

export const OPS = {
  eq: (rv, a) => (Array.isArray(a) && a.includes(rv)) || (num(a) !== null && num(rv) !== null && num(a) === num(rv)) || (a != null && rv != null && a === rv),
  contains: (rv, a) => Array.isArray(a) && a.includes(rv),
  count_gt: (rv, a) => Array.isArray(a) && num(rv) !== null && a.length > num(rv),
  count_eq: (rv, a) => Array.isArray(a) && num(rv) !== null && a.length === num(rv),
  gt: (rv, a) => num(a) !== null && num(rv) !== null && num(a) > num(rv),
  lt: (rv, a) => num(a) !== null && num(rv) !== null && num(a) < num(rv),
  range: (rv, a) => num(a) !== null && num(rv?.[0]) !== null && num(rv?.[1]) !== null && num(a) >= num(rv[0]) && num(a) <= num(rv[1]),
}

export function nextQid(questions, currentQid, answers) {
  const ordered = [...questions].sort((a, b) => a.order - b.order)
  const i = ordered.findIndex((q) => q.qid === currentQid)
  if (i < 0) return null
  const q = ordered[i]
  for (const rule of q.jump_rules || []) {
    const fn = OPS[rule.when?.op]
    if (fn && fn(rule.when?.value, answers[currentQid])) return rule.goto
  }
  return i + 1 < ordered.length ? ordered[i + 1].qid : null
}

// 客户端校验（与 validator.py 一致的镜像），返回错误消息或 null
export function validateAnswer(q, answer) {
  const empty = answer == null || answer === '' || (Array.isArray(answer) && answer.length === 0)
  if (empty) return q.required ? '此题为必答题' : null
  switch (q.type) {
    case 'single':
      if (!Array.isArray(answer) || answer.length !== 1) return '单选题必须选择 1 个选项'
      if (!q.options.includes(answer[0])) return '选项不在允许范围内'
      return null
    case 'multiple': {
      if (!Array.isArray(answer)) return '多选题答案格式错误'
      if (answer.some((o) => !q.options.includes(o))) return '包含无效选项'
      if (new Set(answer).size !== answer.length) return '不能重复选择同一选项'
      if (answer.length < (q.min_select ?? 1)) return `至少选择 ${q.min_select ?? 1} 个`
      if (q.max_select != null && answer.length > q.max_select) return `最多选择 ${q.max_select} 个`
      return null
    }
    case 'text': {
      const n = textLength(answer || '')
      if (n < (q.text_min_len ?? 0)) return `至少输入 ${q.text_min_len ?? 0} 个字`
      if (q.text_max_len != null && n > q.text_max_len) return `最多输入 ${q.text_max_len} 个字`
      return null
    }
    case 'number': {
      const v = num(answer)
      if (v === null || answer === '') return '请输入数字'
      if (q.integer_only && !Number.isInteger(parseFloat(answer))) return '必须为整数'
      if (q.num_min != null && v < q.num_min) return `不能小于 ${q.num_min}`
      if (q.num_max != null && v > q.num_max) return `不能大于 ${q.num_max}`
      return null
    }
  }
  return null
}

let qidSeq = 1
export function newQuestion(type) {
  return {
    qid: `q${qidSeq++}`,
    type,
    title: '',
    required: false,
    order: 0,
    options: ['选项 1', '选项 2'],
    min_select: 1,
    max_select: null,
    text_min_len: 0,
    text_max_len: null,
    num_min: null,
    num_max: null,
    integer_only: false,
    jump_rules: [],
  }
}

export function ensureUniqueQids(questions) {
  const seen = new Set()
  for (const q of questions) {
    while (!q.qid || seen.has(q.qid)) {
      q.qid = `q${qidSeq++}`
    }
    seen.add(q.qid)
  }
}

export const TYPE_LABELS = {
  single: '单选题',
  multiple: '多选题',
  text: '文本填空',
  number: '数字填空',
}

// 各题型可用的跳转条件（与后端 OPS 对齐）
export const JUMP_OPS_BY_TYPE = {
  single: [{ op: 'eq', label: '选中选项' }],
  multiple: [
    { op: 'contains', label: '包含选项' },
    { op: 'count_gt', label: '选中数量 >' },
    { op: 'count_eq', label: '选中数量 =' },
  ],
  number: [
    { op: 'gt', label: '数值 >' },
    { op: 'lt', label: '数值 <' },
    { op: 'eq', label: '数值 =' },
    { op: 'range', label: '数值在区间' },
  ],
  text: [],
}
