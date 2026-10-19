<template>
  <div v-if="survey" class="editor">
    <!-- 顶栏 -->
    <div class="topbar">
      <button class="btn-ghost" @click="$router.push('/')">← 返回</button>
      <el-input v-model="survey.title" class="title-input" placeholder="问卷标题" @input="scheduleSave" />
      <span class="save-state muted">
        {{ saving ? '保存中…' : (savedAt ? `已自动保存 ${savedAt}` : '') }}
      </span>
      <span v-if="survey.status" class="status">
        <span class="status-dot" :class="survey.status"></span>{{ STATUS_LABEL[survey.status] }}
      </span>
      <button
        v-if="survey.status !== 'published'"
        class="btn-primary"
        @click="publish"
      >{{ survey.status === 'closed' ? '重新发布' : '发布' }}</button>
      <button v-else class="btn-ghost" @click="closeSurvey">关闭问卷</button>
    </div>

    <!-- 警告条 -->
    <div v-if="warnings.length" class="warn-banner">
      ⚠ 检测到不可达题目：{{ warnings.join('、') }} —— 任何回答路径都无法到达这些题
    </div>

    <div class="cols">
      <!-- 左：题目列表（拖拽排序） -->
      <div class="col-left card">
        <div class="col-title">题目列表</div>
        <div class="q-list">
          <div
            v-for="(q, i) in survey.questions"
            :key="q.qid"
            class="q-item"
            :class="{ active: q.qid === selectedQid }"
            draggable="true"
            @dragstart="dragIndex = i"
            @dragover.prevent
            @drop="onDrop(i)"
            @click="selectedQid = q.qid"
          >
            <span class="drag">⠿</span>
            <span class="q-badge" :class="q.type">{{ TYPE_LABELS[q.type] }}</span>
            <span class="q-text">{{ q.title || '未命名题目' }}</span>
            <span v-if="q.jump_rules.length" class="jump-flag">↪</span>
          </div>
        </div>
        <div class="add-btns">
          <button class="btn-ghost small" @click="addQuestion('single')">＋ 单选</button>
          <button class="btn-ghost small" @click="addQuestion('multiple')">＋ 多选</button>
          <button class="btn-ghost small" @click="addQuestion('text')">＋ 文本</button>
          <button class="btn-ghost small" @click="addQuestion('number')">＋ 数字</button>
        </div>
      </div>

      <!-- 中：编辑区 -->
      <div class="col-mid card">
        <template v-if="selected">
          <div class="col-title">
            {{ TYPE_LABELS[selected.type] }}
            <button class="btn-ghost small danger" @click="removeQuestion">删除此题</button>
          </div>
          <el-input v-model="selected.title" placeholder="题目标题" @input="scheduleSave" />
          <div class="field">
            <label>是否必答</label>
            <el-switch v-model="selected.required" @change="scheduleSave" />
          </div>

          <!-- 选项（单选/多选） -->
          <template v-if="selected.type === 'single' || selected.type === 'multiple'">
            <div class="field-col">
              <label>选项</label>
              <div v-for="(opt, oi) in selected.options" :key="oi" class="opt-row">
                <el-input v-model="selected.options[oi]" size="small" @input="scheduleSave" />
                <button class="btn-ghost small" @click="removeOption(oi)">✕</button>
              </div>
              <button class="btn-ghost small" @click="addOption">＋ 添加选项</button>
            </div>
            <div v-if="selected.type === 'multiple'" class="field">
              <label>至少选择</label>
              <el-input-number v-model="selected.min_select" :min="1" size="small" @change="scheduleSave" />
              <label>最多选择</label>
              <el-input-number
                v-model="selected.max_select"
                :min="1" size="small"
                placeholder="不限"
                @change="scheduleSave"
              />
            </div>
          </template>

          <!-- 文本约束 -->
          <div v-else-if="selected.type === 'text'" class="field">
            <label>最少字数</label>
            <el-input-number v-model="selected.text_min_len" :min="0" size="small" @change="scheduleSave" />
            <label>最多字数</label>
            <el-input-number
              v-model="selected.text_max_len"
              :min="0" size="small" placeholder="不限"
              @change="scheduleSave"
            />
          </div>

          <!-- 数字约束 -->
          <div v-else-if="selected.type === 'number'" class="field">
            <label>最小值</label>
            <el-input-number v-model="selected.num_min" size="small" @change="scheduleSave" />
            <label>最大值</label>
            <el-input-number v-model="selected.num_max" size="small" @change="scheduleSave" />
            <label>必须整数</label>
            <el-switch v-model="selected.integer_only" @change="scheduleSave" />
          </div>

          <!-- 跳转规则 -->
          <div class="field-col">
            <label>跳转规则 <span class="muted">（命中第一条即跳转）</span></label>
            <div v-if="!JUMP_OPS_BY_TYPE[selected.type]?.length" class="muted">该题型暂不支持跳转</div>
            <div v-for="(rule, ri) in selected.jump_rules" :key="ri" class="jump-row">
              <span class="muted">如果</span>
              <el-select v-model="rule.when.op" size="small" style="width: 120px" @change="onRuleOpChange(rule)">
                <el-option v-for="o in JUMP_OPS_BY_TYPE[selected.type]" :key="o.op" :label="o.label" :value="o.op" />
              </el-select>
              <el-select
                v-if="isOptionRule(rule.when.op)"
                v-model="rule.when.value"
                size="small"
                style="width: 120px"
                placeholder="选项"
                @change="scheduleSave"
              >
                <el-option v-for="o in selected.options" :key="o" :label="o" :value="o" />
              </el-select>
              <el-input-number
                v-else
                v-model="rule.when.value"
                size="small"
                :min="0"
                placeholder="数值"
                @change="scheduleSave"
              />
              <span class="muted">跳到</span>
              <el-select v-model="rule.goto" size="small" style="width: 150px" placeholder="目标题目" @change="scheduleSave">
                <el-option
                  v-for="q in survey.questions.filter((x) => x.qid !== selected.qid)"
                  :key="q.qid"
                  :label="q.title || q.qid"
                  :value="q.qid"
                />
              </el-select>
              <button class="btn-ghost small" @click="selected.jump_rules.splice(ri, 1); scheduleSave()">✕</button>
            </div>
            <button
              v-if="JUMP_OPS_BY_TYPE[selected.type]?.length"
              class="btn-ghost small"
              @click="addRule"
            >＋ 添加跳转</button>
          </div>
        </template>
        <div v-else class="muted center-hint">点击左侧题目进行编辑，或添加新题目</div>

        <!-- 问卷设置 -->
        <div class="survey-settings">
          <div class="col-title">问卷设置</div>
          <el-input
            v-model="survey.description"
            type="textarea"
            :rows="2"
            placeholder="问卷说明（填写者可见）"
            @input="scheduleSave"
          />
          <div class="field">
            <label>允许匿名填写</label>
            <el-switch v-model="survey.allow_anonymous" @change="scheduleSave" />
          </div>
          <div class="field">
            <label>允许重复填写</label>
            <el-switch v-model="survey.allow_multiple_submissions" @change="scheduleSave" />
          </div>
          <div class="field">
            <label>截止时间</label>
            <el-date-picker
              v-model="deadlineDate"
              type="datetime"
              placeholder="不限"
              size="small"
              @change="onDeadlineChange"
            />
          </div>
        </div>
      </div>

      <!-- 右：实时预览 -->
      <div class="col-right card">
        <div class="col-title">实时预览</div>
        <div v-if="!survey.questions.length" class="muted center-hint">添加题目后，这里会实时展示填写效果</div>
        <div v-else class="preview-body">
          <div class="preview-title">{{ survey.title || '问卷标题' }}</div>
          <div v-if="survey.description" class="muted">{{ survey.description }}</div>
          <div class="preview-q">
            <div class="p-q-title">
              {{ previewIndex + 1 }}. {{ previewQ.title || '未命名题目' }}
              <span v-if="previewQ.required" class="req">*</span>
            </div>
            <div v-if="previewQ.type === 'single' || previewQ.type === 'multiple'" class="p-options">
              <label v-for="o in previewQ.options" :key="o" class="p-opt">
                <input
                  :type="previewQ.type === 'single' ? 'radio' : 'checkbox'"
                  :name="'pv-' + previewQ.qid"
                  :checked="(previewAnswers[previewQ.qid] || []).includes(o)"
                  @change="togglePreview(previewQ, o)"
                />
                {{ o }}
              </label>
            </div>
            <el-input
              v-else
              :model-value="previewAnswers[previewQ.qid] || ''"
              :placeholder="previewQ.type === 'number' ? '输入数字' : '输入文字'"
              size="small"
              @input="(v) => { previewAnswers[previewQ.qid] = v; }"
            />
            <p v-if="previewError" class="p-error">{{ previewError }}</p>
          </div>
          <div class="p-btns">
            <button class="btn-ghost small" :disabled="previewIndex === 0" @click="previewNav(-1)">上一题</button>
            <button class="btn-primary small" @click="previewNav(1)">下一题</button>
          </div>
          <p v-if="previewDone" class="muted">✓ 已完成整份问卷（跳转路径：{{ previewPath.join(' → ') }}）</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import {
  JUMP_OPS_BY_TYPE,
  TYPE_LABELS,
  ensureUniqueQids,
  newQuestion,
  nextQid,
  validateAnswer,
} from '../jump'

const route = useRoute()
const router = useRouter()
const survey = ref(null)
const selectedQid = ref(null)
const warnings = ref([])
const saving = ref(false)
const savedAt = ref('')
const dragIndex = ref(-1)
const deadlineDate = ref(null)
const STATUS_LABEL = { draft: '草稿', published: '已发布', closed: '已关闭' }

const selected = computed(() =>
  survey.value?.questions.find((q) => q.qid === selectedQid.value) || null
)

let timer = null
let saveTask = null
let editRevision = 0
let processedRevision = 0

onMounted(load)
onBeforeUnmount(() => {
  clearTimeout(timer)
  if (processedRevision < editRevision) void save()
})

async function load() {
  const { data } = await api.get(`/surveys/${route.params.id}`)
  survey.value = data
  if (data.questions.length) selectedQid.value = data.questions[0].qid
  deadlineDate.value = data.deadline ? new Date(data.deadline) : null
  resetPreview()
}

function addQuestion(type) {
  const qids = new Set(survey.value.questions.map((question) => question.qid))
  let q = newQuestion(type)
  while (qids.has(q.qid)) q = newQuestion(type)
  survey.value.questions.push(q)
  selectedQid.value = q.qid
  scheduleSave()
}

function removeQuestion() {
  const removedQid = selectedQid.value
  survey.value.questions = survey.value.questions.filter((q) => q.qid !== selectedQid.value)
  for (const question of survey.value.questions) {
    question.jump_rules = question.jump_rules.filter((rule) => rule.goto !== removedQid)
  }
  selectedQid.value = survey.value.questions[0]?.qid || null
  scheduleSave()
}

function addOption() {
  let index = selected.value.options.length + 1
  while (selected.value.options.includes(`选项 ${index}`)) index++
  selected.value.options.push(`选项 ${index}`)
  scheduleSave()
}
function removeOption(i) {
  const [removedOption] = selected.value.options.splice(i, 1)
  selected.value.jump_rules = selected.value.jump_rules.filter((rule) =>
    !['eq', 'contains'].includes(rule.when.op) || rule.when.value !== removedOption
  )
  scheduleSave()
}

function addRule() {
  const target = survey.value.questions.find((question) => question.qid !== selected.value.qid)
  if (!target) {
    ElMessage.warning('请先添加另一道题目作为跳转目标')
    return
  }
  const ops = JUMP_OPS_BY_TYPE[selected.value.type]
  const op = ops[0].op
  selected.value.jump_rules.push({
    when: { op, value: isOptionRule(op) ? selected.value.options[0] : 0 },
    goto: target.qid,
  })
  scheduleSave()
}
function isOptionRule(op) { return op === 'eq' && selected.value?.type === 'single' || op === 'contains' }
function onRuleOpChange(rule) {
  const ops = JUMP_OPS_BY_TYPE[selected.value.type]
  const op = rule.when.op
  rule.when.value = isOptionRule(op) ? selected.value.options[0] : 0
  scheduleSave()
}

function onDrop(toIndex) {
  const from = dragIndex.value
  if (from < 0 || from === toIndex) return
  const qs = survey.value.questions
  const [moved] = qs.splice(from, 1)
  qs.splice(toIndex, 0, moved)
  dragIndex.value = -1
  scheduleSave()
}

// ---- 自动保存（debounce + 乐观锁 version） ----
function scheduleSave() {
  editRevision++
  clearTimeout(timer)
  timer = setTimeout(save, 900)
}
async function save() {
  clearTimeout(timer)
  if (!survey.value) return false
  if (saveTask) {
    const activeTask = saveTask
    const result = await activeTask
    if (processedRevision < editRevision) return save()
    return result
  }
  const revision = editRevision
  ensureUniqueQids(survey.value.questions)
  survey.value.questions.forEach((q, i) => { q.order = i + 1 })
  saving.value = true
  saveTask = (async () => {
    try {
      const payload = {
        title: survey.value.title,
        description: survey.value.description,
        allow_anonymous: survey.value.allow_anonymous,
        allow_multiple_submissions: survey.value.allow_multiple_submissions,
        deadline: survey.value.deadline,
        questions: survey.value.questions,
        version: survey.value.version,
      }
      const { data } = await api.put(`/surveys/${survey.value.id}`, payload)
      survey.value.version = data.version
      warnings.value = data.warnings || []
      savedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
      return true
    } catch (e) {
      if (e.response?.status === 409) {
        ElMessage.warning('问卷已在其他页面被修改，已为你刷新为最新版本')
        try {
          await load()
        } catch {
          ElMessage.error('刷新问卷失败，请返回工作台后重试')
        }
      } else if (e.response?.status === 400) {
        warnings.value = []
        ElMessage.error(e.response.data.detail || '保存失败：检查跳转规则')
      } else {
        ElMessage.error('保存失败')
      }
      return false
    }
  })()
  const activeTask = saveTask
  const result = await activeTask
  processedRevision = revision
  if (saveTask === activeTask) saveTask = null
  saving.value = false
  if (processedRevision < editRevision) return save()
  return result
}

async function publish() {
  const saved = await save()
  if (!saved) return
  try {
    await api.post(`/surveys/${survey.value.id}/publish`)
    ElMessage.success('问卷已发布')
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '发布失败')
  }
}

async function closeSurvey() {
  try {
    await api.post(`/surveys/${survey.value.id}/close`)
    ElMessage.success('问卷已关闭')
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '关闭失败')
  }
}

function onDeadlineChange(v) {
  survey.value.deadline = v ? v.toISOString() : null
  scheduleSave()
}

// ---- 实时预览（客户端跳转引擎镜像） ----
const previewAnswers = ref({})
const previewPath = ref([])
const previewIndex = ref(0)
const previewError = ref('')
const previewDone = ref(false)

const previewQ = computed(() => {
  if (!survey.value) return {}
  const qid = previewPath.value[previewIndex.value]
  return survey.value.questions.find((q) => q.qid === qid) || {}
})

function resetPreview() {
  previewAnswers.value = {}
  previewPath.value = survey.value.questions.length ? [survey.value.questions[0].qid] : []
  previewIndex.value = 0
  previewError.value = ''
  previewDone.value = false
}

watch(() => survey.value?.questions, resetPreview, { deep: true })

function togglePreview(q, opt) {
  const cur = previewAnswers.value[q.qid] || []
  if (q.type === 'single') {
    previewAnswers.value[q.qid] = [opt]
  } else {
    previewAnswers.value[q.qid] = cur.includes(opt) ? cur.filter((o) => o !== opt) : [...cur, opt]
  }
}

function previewNav(dir) {
  const path = previewPath.value
  const q = survey.value.questions.find((x) => x.qid === path[previewIndex.value])
  if (!q) return
  if (dir === 1) {
    const err = validateAnswer(q, previewAnswers.value[q.qid])
    if (err) { previewError.value = err; return }
    previewError.value = ''
    const nxt = nextQid(survey.value.questions, q.qid, previewAnswers.value)
    if (nxt) {
      path.push(nxt)
      previewIndex.value++
    } else {
      previewDone.value = true
    }
  } else if (previewIndex.value > 0) {
    previewIndex.value--
    previewPath.value = previewPath.value.slice(0, previewIndex.value + 1)
    previewDone.value = false
  }
}
</script>

<style scoped>
.editor { display: flex; flex-direction: column; gap: 14px; height: 100%; }
.topbar { display: flex; align-items: center; gap: 12px; }
.title-input { width: 300px; font-size: 16px; }
.save-state { width: 150px; }
.status { display: flex; align-items: center; font-size: 13px; color: var(--text-2); }
.cols { display: grid; grid-template-columns: 240px 1fr 340px; gap: 14px; flex: 1; min-height: 0; }
.col-left, .col-mid, .col-right { overflow-y: auto; }
.col-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
.q-list { display: flex; flex-direction: column; gap: 6px; }
.q-item {
  display: flex; align-items: center; gap: 6px; padding: 8px 10px;
  border: 1px solid var(--border); border-radius: 8px; cursor: pointer; font-size: 13px;
}
.q-item:hover { border-color: var(--primary); }
.q-item.active { border-color: var(--primary); background: #f0f3ff; }
.drag { cursor: grab; color: #b6bcd0; }
.q-badge {
  font-size: 11px; padding: 2px 6px; border-radius: 4px; color: #fff; flex-shrink: 0;
}
.q-badge.single { background: #4f6ef7; }
.q-badge.multiple { background: #8b5cf6; }
.q-badge.text { background: #10b981; }
.q-badge.number { background: #f59e0b; }
.q-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.jump-flag { color: var(--primary); }
.add-btns { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 12px; }
.small { padding: 5px 10px; font-size: 12px; }
.danger { color: var(--danger); }
.field { display: flex; align-items: center; gap: 10px; margin: 12px 0; font-size: 13px; flex-wrap: wrap; }
.field-col { margin: 12px 0; }
.field-col > label { font-size: 13px; font-weight: 500; display: block; margin-bottom: 6px; }
.opt-row { display: flex; gap: 6px; margin-bottom: 6px; }
.opt-row .el-input { flex: 1; }
.jump-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; flex-wrap: wrap; font-size: 13px; }
.survey-settings { border-top: 1px solid var(--border); margin-top: 20px; padding-top: 14px; }
.center-hint { text-align: center; padding: 40px 0; }
.preview-body { display: flex; flex-direction: column; gap: 12px; }
.preview-title { font-size: 17px; font-weight: 600; }
.preview-q { background: #f8f9fd; border-radius: 8px; padding: 14px; }
.p-q-title { font-weight: 600; font-size: 14px; margin-bottom: 10px; }
.req { color: var(--danger); }
.p-options { display: flex; flex-direction: column; gap: 8px; }
.p-opt { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; }
.p-error { color: var(--danger); font-size: 12px; margin: 8px 0 0; }
.p-btns { display: flex; justify-content: space-between; }
.editor { min-height: calc(100vh - 150px); height: auto; gap: 16px; }
.topbar { min-height: 44px; flex-wrap: wrap; }
.cols { grid-template-columns: minmax(205px, .72fr) minmax(360px, 1.38fr) minmax(285px, 1fr); gap: 13px; }
.col-left, .col-mid, .col-right { border-color: #e8ecf4; border-radius: 14px; }
.q-item { min-height: 39px; }
.q-item.active { color: #4f4ec0; }
.add-btns .btn-ghost { min-width: 0; }
.jump-row { padding: 8px; border: 1px solid #edf0f5; border-radius: 9px; background: #fcfcfe; }
.survey-settings { padding-top: 17px; }
@media (max-width: 1200px) {
  .cols { grid-template-columns: minmax(190px, .68fr) minmax(0, 1.32fr); }
  .col-right { grid-column: 1 / -1; max-height: 470px; }
}
@media (max-width: 760px) {
  .editor { min-height: auto; }
  .topbar { gap: 8px; }
  .title-input { width: auto; min-width: 180px; flex: 1; }
  .save-state { width: auto; }
  .cols { grid-template-columns: minmax(0, 1fr); }
  .col-left { max-height: 285px; }
  .col-mid { overflow: visible; }
  .col-right { grid-column: auto; max-height: none; }
  .jump-row { align-items: flex-start; }
}
</style>
