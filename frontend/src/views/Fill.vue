<template>
  <div class="fill-wrap">
    <!-- 错误状态页 -->
    <div v-if="pageError" class="state-card card">
      <div class="state-icon">🚫</div>
      <h3>{{ pageError }}</h3>
      <p class="muted">该问卷可能未发布、已关闭或已截止。</p>
    </div>

    <!-- 需要登录 -->
    <div v-else-if="needLogin" class="state-card card">
      <div class="state-icon">🔒</div>
      <h3>此问卷需要登录后填写</h3>
      <p class="muted">问卷创建者关闭了匿名填写选项</p>
      <button class="btn-primary" @click="goLogin">去登录 / 注册</button>
    </div>

    <!-- 提交成功 -->
    <div v-else-if="submitted" class="state-card card">
      <div class="state-icon">🎉</div>
      <h3>提交成功，感谢你的回答！</h3>
      <p class="muted">本次填写路径：{{ visitedPath.join(' → ') }}</p>
      <button
        v-if="survey.allow_multiple_submissions"
        class="btn-primary"
        @click="resetFill"
      >再填一份</button>
    </div>

    <!-- 答题主界面 -->
    <div v-else-if="currentQ" class="fill-card card">
      <div class="fill-brand"><span class="fill-mark">S</span><span>问卷星球</span><i>安全填写</i></div>
      <div class="head">
        <div class="title">{{ survey.title }}</div>
        <div v-if="survey.description" class="muted desc">{{ survey.description }}</div>
      </div>
      <div class="progress">
        <div class="progress-track"><div class="progress-fill" :style="{ width: pct + '%' }"></div></div>
        <span class="pct">{{ Math.round(pct) }}%</span>
      </div>
      <div class="step-label">第 {{ currentQuestionNumber }} 题 <span>·</span> 共 {{ totalQuestions }} 道题</div>

      <div class="q-card">
        <div class="q-title">
          {{ index + 1 }}. {{ currentQ.title }}
          <span v-if="currentQ.required" class="req">* 必答</span>
        </div>

        <!-- 单选 -->
        <div v-if="currentQ.type === 'single'" class="options">
          <label v-for="o in currentQ.options" :key="o" class="option"
                 :class="{ checked: (answers[currentQ.qid] || []).includes(o) }">
            <input type="radio" :name="currentQ.qid" :value="o" :aria-label="o"
                   :checked="(answers[currentQ.qid] || []).includes(o)"
                   @change="answers[currentQ.qid] = [o]; error = ''" />
            <span class="radio-dot"></span>{{ o }}
          </label>
        </div>
        <!-- 多选 -->
        <div v-else-if="currentQ.type === 'multiple'" class="options">
          <label v-for="o in currentQ.options" :key="o" class="option"
                 :class="{ checked: (answers[currentQ.qid] || []).includes(o) }">
            <input type="checkbox" :value="o" :aria-label="o"
                   :checked="(answers[currentQ.qid] || []).includes(o)"
                   @change="toggleMulti(currentQ, o)" />
            <span class="check-box"></span>{{ o }}
          </label>
          <div class="muted hint">
            {{ currentQ.min_select || 1 }} ~ {{ currentQ.max_select || '不限' }} 个
          </div>
        </div>
        <!-- 填空 -->
        <div v-else class="blank">
          <el-input
            :model-value="answers[currentQ.qid] || ''"
            :type="currentQ.type === 'number' ? 'text' : 'textarea'"
            :rows="3"
            :maxlength="currentQ.type === 'text' ? currentQ.text_max_len ?? undefined : undefined"
            :show-word-limit="currentQ.type === 'text' && currentQ.text_max_len != null"
            :inputmode="currentQ.type === 'number' ? 'decimal' : undefined"
            :placeholder="currentQ.type === 'number' ? '请输入数字' : '请输入你的回答'"
            size="large"
            @input="(v) => { answers[currentQ.qid] = v; error = ''; }"
          />
          <div v-if="currentQ.type === 'number'" class="muted hint">
            {{ numHint(currentQ) }}
          </div>
        </div>

        <p v-if="error" class="error-msg">⚠ {{ error }}</p>
      </div>

      <div class="btns">
        <button class="btn-ghost" :disabled="index === 0" @click="goBack">上一题</button>
        <button v-if="!isLast" class="btn-primary" @click="goNext">下一题 →</button>
        <button v-else class="btn-primary submit-btn" :disabled="submitting" @click="submit">
          {{ submitting ? '提交中…' : '提交问卷' }}
        </button>
      </div>
    </div>

    <div v-else class="muted">加载中…</div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { nextQid, validateAnswer } from '../jump'

const route = useRoute()
const router = useRouter()
const survey = ref({})
const answers = ref({})
const visitedPath = ref([])
const index = ref(0)
const error = ref('')
const pageError = ref('')
const needLogin = ref(false)
const submitted = ref(false)
const submitting = ref(false)
const startedAt = ref(Date.now())

const currentQ = computed(() => {
  const qid = visitedPath.value[index.value]
  return (survey.value.questions || []).find((q) => q.qid === qid)
})
// 当前题已合法作答，且按跳转规则没有下一题 → 才是真正的"最后一题"
const hasAnswer = computed(() => {
  const q = currentQ.value
  if (!q) return false
  return !validateAnswer(q, answers.value[q.qid])
})
const isLast = computed(() =>
  hasAnswer.value &&
  !nextQid(survey.value.questions || [], currentQ.value.qid, answers.value)
)
const totalQuestions = computed(() => (survey.value.questions || []).length)
const currentQuestionNumber = computed(() => currentQ.value?.order || index.value + 1)
const pct = computed(() =>
  totalQuestions.value ? (currentQuestionNumber.value / totalQuestions.value) * 100 : 0
)

onMounted(async () => {
  try {
    const { data } = await api.get(`/s/${route.params.token}`)
    survey.value = data
    if (data.questions.length) {
      visitedPath.value = [data.questions[0].qid]
    } else {
      pageError.value = '该问卷暂无题目'
    }
  } catch (e) {
    if (e.response?.status === 401) needLogin.value = true
    else pageError.value = e.response?.data?.detail || '问卷不存在'
  }
})

function toggleMulti(q, o) {
  const cur = answers.value[q.qid] || []
  answers.value[q.qid] = cur.includes(o) ? cur.filter((x) => x !== o) : [...cur, o]
  error.value = ''
}

function numHint(q) {
  const parts = []
  if (q.num_min != null) parts.push(`≥ ${q.num_min}`)
  if (q.num_max != null) parts.push(`≤ ${q.num_max}`)
  if (q.integer_only) parts.push('必须为整数')
  return parts.join('，')
}

function goNext() {
  const q = currentQ.value
  const err = validateAnswer(q, answers.value[q.qid])
  if (err) { error.value = err; return }
  error.value = ''
  const nxt = nextQid(survey.value.questions, q.qid, answers.value)
  if (nxt) {
    visitedPath.value.push(nxt)
    index.value++
  }
}

function goBack() {
  if (index.value > 0) {
    index.value--
    visitedPath.value = visitedPath.value.slice(0, index.value + 1)
    error.value = ''
  }
}

function anonId() {
  let id = localStorage.getItem('anon_id')
  if (!id) {
    id = `anon-${globalThis.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`}`
    localStorage.setItem('anon_id', id)
  }
  return id
}

async function submit() {
  const q = currentQ.value
  const err = validateAnswer(q, answers.value[q.qid])
  if (err) { error.value = err; return }
  submitting.value = true
  try {
    await api.post(`/s/${route.params.token}/responses`, {
      answers: answers.value,
      spent_seconds: Math.max(0, Math.round((Date.now() - startedAt.value) / 1000)),
      anon_id: survey.value.allow_anonymous ? anonId() : null,
    })
    submitted.value = true
  } catch (e) {
    const st = e.response?.status
    if (st === 401) needLogin.value = true
    else if (st === 409) ElMessage.warning('你已经提交过这份问卷')
    else if (st === 422) {
      const first = e.response.data.detail?.[0]
      ElMessage.error(first ? `${first.question_id}: ${first.message}` : '提交内容不符合要求')
    } else if (st === 403) {
      ElMessage.error(e.response.data.detail || '问卷已截止')
      pageError.value = e.response.data.detail || '问卷已截止'
    } else {
      ElMessage.error('提交失败，请重试')
    }
  } finally {
    submitting.value = false
  }
}

function resetFill() {
  answers.value = {}
  visitedPath.value = survey.value.questions.length ? [survey.value.questions[0].qid] : []
  index.value = 0
  error.value = ''
  submitted.value = false
  startedAt.value = Date.now()
}

function goLogin() {
  sessionStorage.setItem('after_login', location.hash)
  router.push('/login')
}
</script>

<style scoped>
.fill-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  background: radial-gradient(circle at 15% 15%, #e9e8ff 0, transparent 29%), radial-gradient(circle at 85% 80%, #e4f3f1 0, transparent 25%), #f5f7fb;
}
.fill-card { width: 650px; max-width: 96vw; padding: 28px 36px 30px; border-color: #e7eaf3; box-shadow: 0 18px 60px #26345212; }
.fill-brand { display: flex; align-items: center; gap: 8px; margin-bottom: 25px; color: #576078; font-size: 11px; font-weight: 700; }
.fill-mark { width: 25px; height: 25px; display: grid; place-items: center; border-radius: 8px; color: #fff; background: var(--primary); font-size: 12px; }
.fill-brand i { margin-left: auto; color: #319977; font-size: 9px; font-style: normal; font-weight: 550; }
.fill-brand i::before { content: '●'; margin-right: 5px; color: #37b98e; font-size: 8px; }
.head .title { font-size: 22px; font-weight: 750; letter-spacing: -.03em; }
.head .desc { margin-top: 7px; line-height: 1.6; }
.progress {
  display: flex; align-items: center; gap: 12px; margin: 18px 0;
}
.progress-track { height: 7px; flex: 1; overflow: hidden; border-radius: 9px; background: #eceef5; }
.progress-fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, #6866e2, #8a88ef); transition: width .25s ease; }
.pct { min-width: 34px; color: #6664ce; font-size: 10px; font-weight: 700; text-align: right; }
.step-label { margin: -11px 0 21px; color: #9ba4b4; font-size: 9px; }
.step-label span { margin: 0 4px; color: #c0c6d1; }
.q-card { min-height: 170px; }
.q-title { margin-bottom: 17px; color: #303a52; font-size: 16px; font-weight: 700; line-height: 1.55; }
.req { color: var(--danger); font-size: 12px; font-weight: 400; }
.options { display: flex; flex-direction: column; gap: 10px; }
.option {
  position: relative; display: flex; align-items: center; gap: 10px; padding: 13px 15px;
  border: 1px solid var(--border); border-radius: 8px; cursor: pointer;
  transition: all 0.15s; font-size: 14px;
}
.option:hover { border-color: #aaa9e9; background: #fcfbff; }
.option.checked { border-color: #9694e5; background: #f5f4ff; }
.option input { position: absolute; width: 1px; height: 1px; opacity: 0; }
.option:focus-within { outline: 3px solid #8a89ed66; outline-offset: 2px; }
.radio-dot {
  width: 16px; height: 16px; border: 2px solid #c3c8db; border-radius: 50%;
  display: inline-block; position: relative; flex-shrink: 0;
}
.checked .radio-dot { border-color: var(--primary); }
.checked .radio-dot::after {
  content: ''; position: absolute; inset: 2px; border-radius: 50%; background: var(--primary);
}
.check-box {
  width: 16px; height: 16px; border: 2px solid #c3c8db; border-radius: 4px;
  display: inline-block; flex-shrink: 0; position: relative;
}
.checked .check-box { border-color: var(--primary); background: var(--primary); }
.checked .check-box::after {
  content: '✓'; color: #fff; font-size: 11px; position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
}
.hint { margin-top: 8px; }
.blank { margin-top: 4px; }
.error-msg {
  color: var(--danger); font-size: 13px; margin: 12px 0 0;
  background: #fef2f2; border-radius: 6px; padding: 8px 12px;
}
.btns { display: flex; justify-content: space-between; margin-top: 20px; }
.submit-btn { background: var(--success); }
.submit-btn:hover { background: #16a34a; }
.state-card { width: 460px; max-width: 92vw; text-align: center; padding: 44px 32px; }
.state-icon { font-size: 44px; margin-bottom: 12px; }
.state-card h3 { margin: 0 0 8px; }
.state-card .btn-primary { margin-top: 14px; }
@media (max-width: 560px) {
  .fill-wrap { align-items: flex-start; padding: 18px 12px; }
  .fill-card { width: 100%; max-width: none; padding: 22px 18px; }
  .fill-brand { margin-bottom: 20px; }
  .head .title { font-size: 19px; }
  .q-title { font-size: 15px; }
  .btns { gap: 10px; }
  .btns button { min-width: 0; flex: 1; }
  .state-card { margin: auto 0; padding: 35px 22px; }
}
</style>
