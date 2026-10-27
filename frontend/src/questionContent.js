export const contentFields = ['type', 'title', 'options', 'min_select', 'max_select', 'text_min_len', 'text_max_len', 'num_min', 'num_max', 'integer_only']

export function makeContent(type = 'single') {
  return { type, title: '', options: type === 'single' || type === 'multiple' ? ['选项 1', '选项 2'] : [], min_select: 1, max_select: null, text_min_len: 0, text_max_len: null, num_min: null, num_max: null, integer_only: false }
}

export function pickContent(question) {
  const result = makeContent(question.type)
  for (const field of contentFields) {
    if (question[field] !== undefined) result[field] = Array.isArray(question[field]) ? [...question[field]] : question[field]
  }
  return result
}

export function errorMessage(error, fallback = '操作失败，请重试') {
  const detail = error.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
