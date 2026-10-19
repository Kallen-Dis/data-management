<template>
  <div class="dashboard">
    <section class="welcome-row">
      <div>
        <div class="eyebrow"><span class="eyebrow-mark">✦</span> SURVEY WORKSPACE</div>
        <h1 class="page-title">问卷工作台</h1>
        <p class="welcome-copy">把想法变成问题，把回答变成洞察。</p>
      </div>
      <button class="btn-primary create-button" :disabled="creating" @click="createSurvey">
        <span class="plus">＋</span>{{ creating ? '正在创建…' : '新建问卷' }}
      </button>
    </section>

    <section class="welcome-banner">
      <div class="banner-copy">
        <span class="banner-kicker">YOUR NEXT INSIGHT STARTS HERE</span>
        <h2>每一份好数据，<br>都从一个好问题开始。</h2>
        <p>设计问卷、分享链接、实时查看反馈，让调研流程简单一点。</p>
      </div>
      <div class="banner-art" aria-hidden="true">
        <div class="art-orbit orbit-one"></div>
        <div class="art-orbit orbit-two"></div>
        <div class="art-card"><span>Q.</span><i></i><i></i><b>✓</b></div>
        <div class="art-spark spark-one">✦</div>
        <div class="art-spark spark-two">✧</div>
      </div>
    </section>

    <section class="metric-grid" aria-label="问卷概览">
      <div class="metric-card">
        <div class="metric-top"><span>问卷总数</span><span class="metric-icon violet">▤</span></div>
        <div class="metric-value">{{ surveys.length }}</div>
        <div class="metric-foot">已创建的全部问卷</div>
      </div>
      <div class="metric-card">
        <div class="metric-top"><span>正在收集</span><span class="metric-icon green">↗</span></div>
        <div class="metric-value">{{ publishedCount }}</div>
        <div class="metric-foot"><span class="live-indicator"></span>当前已发布</div>
      </div>
      <div class="metric-card">
        <div class="metric-top"><span>累计回答</span><span class="metric-icon amber">▥</span></div>
        <div class="metric-value">{{ responseTotal.toLocaleString('zh-CN') }}</div>
        <div class="metric-foot">来自所有问卷的提交</div>
      </div>
    </section>

    <section class="survey-section">
      <div class="section-heading">
        <div class="section-title-wrap">
          <h2>你的问卷</h2>
          <span class="section-count">{{ filteredSurveys.length }}</span>
        </div>
        <div class="toolbar">
          <label class="search-box">
            <span aria-hidden="true">⌕</span>
            <input v-model.trim="searchText" aria-label="搜索问卷" placeholder="搜索问卷名称" />
            <button v-if="searchText" aria-label="清除搜索" @click="searchText = ''">×</button>
          </label>
          <div class="filters" aria-label="按状态筛选">
            <button v-for="filter in filters" :key="filter.value" :class="{ active: statusFilter === filter.value }" @click="statusFilter = filter.value">
              {{ filter.label }}<span>{{ filterCount(filter.value) }}</span>
            </button>
          </div>
        </div>
      </div>

      <div v-if="loading" class="loading-grid">
        <div v-for="item in 3" :key="item" class="survey-skeleton"></div>
      </div>
      <div v-else-if="loadError" class="state-panel">
        <div class="state-symbol">↻</div>
        <h3>问卷暂时没有加载出来</h3>
        <p>{{ loadError }}</p>
        <button class="btn-ghost" @click="load">重新加载</button>
      </div>
      <div v-else-if="!surveys.length" class="state-panel first-survey">
        <div class="empty-art">✎</div>
        <h3>从第一份问卷开始</h3>
        <p>添加题目、配置跳转逻辑，再把分享链接发给填写者。</p>
        <button class="btn-primary" @click="createSurvey">＋ 创建第一份问卷</button>
      </div>
      <div v-else-if="!filteredSurveys.length" class="state-panel compact-state">
        <div class="state-symbol">⌕</div>
        <h3>没有找到匹配的问卷</h3>
        <p>试试其他关键词或切换状态筛选。</p>
        <button class="btn-ghost" @click="clearFilters">清除筛选</button>
      </div>
      <div v-else class="survey-grid">
        <article v-for="(survey, index) in filteredSurveys" :key="survey.id" class="survey-card card" :class="`accent-${index % 4}`">
          <div class="survey-card-top">
            <div class="survey-symbol" aria-hidden="true">{{ survey.title?.trim()?.slice(0, 1) || '问' }}</div>
            <span class="status-pill" :class="survey.status"><span class="status-dot" :class="survey.status"></span>{{ STATUS_LABEL[survey.status] }}</span>
          </div>
          <button class="survey-title" @click="openEditor(survey)">{{ survey.title || '未命名问卷' }}</button>
          <p class="survey-description">{{ survey.description || '为这份问卷添加一段说明，让填写者更了解调研目的。' }}</p>
          <div class="survey-meta">
            <span><strong>{{ survey.response_total || 0 }}</strong> 份回答</span>
            <span>{{ survey.questions?.length || 0 }} 道题</span>
          </div>
          <div v-if="survey.deadline" class="deadline-line">截止 {{ fmt(survey.deadline) }}</div>
          <div class="survey-actions">
            <button class="btn-ghost" @click="openEditor(survey)">编辑问卷</button>
            <button v-if="survey.status === 'draft' || survey.status === 'closed'" class="btn-primary" :disabled="busyId === survey.id" @click="publish(survey)">
              {{ busyId === survey.id ? '处理中…' : survey.status === 'closed' ? '重新发布' : '发布问卷' }}
            </button>
            <button v-else class="btn-primary" @click="openStats(survey)">查看数据</button>
            <button v-if="survey.status === 'published'" class="btn-ghost" :disabled="busyId === survey.id" @click="closeSurvey(survey)">结束收集</button>
          </div>
          <div v-if="survey.status === 'published'" class="share-row">
            <span><span class="share-dot"></span>分享链接可用</span>
            <button @click="copyLink(survey)">复制链接 <span aria-hidden="true">↗</span></button>
          </div>
          <div v-else class="share-row muted-share">
            <span>最近更新 {{ fmtDate(survey.updated_at || survey.created_at) }}</span>
            <button @click="openStats(survey)">查看统计 <span aria-hidden="true">↗</span></button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const surveys = ref([])
const loading = ref(true)
const creating = ref(false)
const loadError = ref('')
const busyId = ref('')
const searchText = ref('')
const statusFilter = ref('all')
const STATUS_LABEL = { draft: '草稿', published: '收集中', closed: '已结束' }
const filters = [
  { value: 'all', label: '全部' },
  { value: 'published', label: '收集中' },
  { value: 'draft', label: '草稿' },
  { value: 'closed', label: '已结束' },
]

const publishedCount = computed(() => surveys.value.filter((survey) => survey.status === 'published').length)
const responseTotal = computed(() => surveys.value.reduce((sum, survey) => sum + (survey.response_total || 0), 0))
const filteredSurveys = computed(() => surveys.value.filter((survey) => {
  const matchesStatus = statusFilter.value === 'all' || survey.status === statusFilter.value
  const query = searchText.value.toLocaleLowerCase()
  const matchesText = !query || `${survey.title} ${survey.description}`.toLocaleLowerCase().includes(query)
  return matchesStatus && matchesText
}))

onMounted(load)

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const { data } = await api.get('/surveys')
    surveys.value = data
  } catch (error) {
    loadError.value = error.response?.data?.detail || '请检查网络连接后重试。'
  } finally {
    loading.value = false
  }
}

async function createSurvey() {
  if (creating.value) return
  creating.value = true
  try {
    const { data } = await api.post('/surveys', {
      title: '未命名问卷', description: '', allow_anonymous: false,
      allow_multiple_submissions: false, questions: [],
    })
    router.push(`/editor/${data.id}`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建失败，请重试')
  } finally {
    creating.value = false
  }
}

function openEditor(survey) { router.push(`/editor/${survey.id}`) }
function openStats(survey) { router.push(`/stats/${survey.id}`) }

async function publish(survey) {
  busyId.value = survey.id
  try {
    await api.post(`/surveys/${survey.id}/publish`)
    ElMessage.success('问卷已发布，可以复制链接分享')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '发布失败')
  } finally {
    busyId.value = ''
  }
}

async function closeSurvey(survey) {
  busyId.value = survey.id
  try {
    await api.post(`/surveys/${survey.id}/close`)
    ElMessage.success('问卷已结束收集')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    busyId.value = ''
  }
}

async function copyLink(survey) {
  const url = `${location.origin}${location.pathname}#/s/${survey.share_token}`
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('填写链接已复制')
  } catch {
    ElMessage.info(`填写链接：${url}`, { duration: 6000 })
  }
}

function filterCount(status) {
  return status === 'all' ? surveys.value.length : surveys.value.filter((survey) => survey.status === status).length
}

function clearFilters() {
  searchText.value = ''
  statusFilter.value = 'all'
}

function fmt(iso) {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
}

function fmtDate(iso) {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' })
}
</script>

<style scoped>
.dashboard { max-width: 1260px; margin: 0 auto; }
.welcome-row { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 22px; }
.eyebrow { display: flex; align-items: center; gap: 7px; margin-bottom: 10px; color: #8d91b4; font-size: 9px; font-weight: 750; letter-spacing: .17em; }
.eyebrow-mark { color: var(--primary); font-size: 13px; }
.welcome-copy { margin: 8px 0 0; color: #7c879e; font-size: 12px; }
.create-button { min-width: 132px; min-height: 42px; }
.plus { font-size: 17px; line-height: 1; }
.welcome-banner { position: relative; min-height: 188px; display: flex; overflow: hidden; align-items: center; margin-bottom: 19px; padding: 29px 35px; border: 1px solid #e4e4fb; border-radius: 17px; background: linear-gradient(105deg, #f1f0ff 0%, #f5f5ff 52%, #e8f3ff 100%); }
.banner-copy { position: relative; z-index: 2; max-width: 510px; }
.banner-kicker { color: #8987c6; font-size: 9px; font-weight: 750; letter-spacing: .14em; }
.banner-copy h2 { margin: 10px 0 7px; color: #30345b; font-size: 23px; font-weight: 750; letter-spacing: -.04em; line-height: 1.35; }
.banner-copy p { margin: 0; color: #7d839e; font-size: 11px; }
.banner-art { position: absolute; top: 0; right: 4%; width: 300px; height: 100%; }
.art-orbit { position: absolute; border: 1px solid #aaa8ed55; border-radius: 50%; }
.orbit-one { width: 210px; height: 210px; top: -15px; right: 34px; }
.orbit-two { width: 155px; height: 155px; top: 12px; right: 61px; }
.art-card { position: absolute; top: 35px; right: 91px; width: 112px; height: 119px; padding: 14px; border: 1px solid #ffffff; border-radius: 13px; background: #ffffffd9; box-shadow: 0 12px 28px #615fc72b; transform: rotate(7deg); }
.art-card > span { display: block; margin-bottom: 11px; color: #6865dc; font-size: 19px; font-weight: 800; }
.art-card i { display: block; width: 70%; height: 5px; margin: 7px 0; border-radius: 6px; background: #e5e5f5; }
.art-card i:nth-of-type(2) { width: 50%; }
.art-card b { width: 24px; height: 24px; display: grid; place-items: center; margin-top: 12px; border-radius: 8px; color: #fff; background: #42bd98; font-size: 13px; }
.art-spark { position: absolute; color: #7775e5; }
.spark-one { top: 35px; right: 41px; font-size: 21px; }
.spark-two { bottom: 29px; right: 220px; color: #71a4e9; font-size: 25px; }
.metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-bottom: 31px; }
.metric-card { min-height: 112px; padding: 17px 19px; border: 1px solid var(--border); border-radius: 14px; background: #fff; box-shadow: var(--shadow); }
.metric-top { display: flex; align-items: center; justify-content: space-between; color: #818ba1; font-size: 11px; }
.metric-icon { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 9px; font-size: 15px; font-weight: 700; }
.metric-icon.violet { color: #6461d7; background: #efeeff; }
.metric-icon.green { color: #1caa7d; background: #e8f8f2; }
.metric-icon.amber { color: #d69232; background: #fff4e4; }
.metric-value { margin-top: 7px; color: #29324a; font-size: 24px; font-weight: 750; letter-spacing: -.04em; }
.metric-foot { display: flex; align-items: center; gap: 7px; margin-top: 3px; color: #9aa3b5; font-size: 10px; }
.live-indicator, .share-dot { width: 6px; height: 6px; display: inline-block; border-radius: 50%; background: #28b889; }
.survey-section { min-width: 0; }
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 15px; }
.section-title-wrap { display: flex; align-items: center; gap: 9px; }
.section-title-wrap h2 { margin: 0; color: #2b344b; font-size: 16px; font-weight: 750; }
.section-count { min-width: 22px; padding: 3px 7px; border-radius: 20px; color: #7675c8; background: #efefff; font-size: 10px; text-align: center; }
.toolbar { display: flex; align-items: center; gap: 12px; }
.search-box { min-width: 190px; height: 34px; display: flex; align-items: center; gap: 7px; padding: 0 10px; border: 1px solid #e4e8f0; border-radius: 9px; color: #9099ab; background: #fff; }
.search-box > span { font-size: 19px; line-height: 1; }
.search-box input { width: 100%; min-width: 0; border: 0; outline: 0; color: #35405a; background: transparent; font-size: 10px; }
.search-box input::placeholder { color: #a5adbc; }
.search-box button { border: 0; color: #929bb0; background: none; cursor: pointer; font-size: 16px; }
.filters { display: flex; align-items: center; gap: 3px; padding: 3px; border: 1px solid #e9ecf3; border-radius: 9px; background: #f0f2f7; }
.filters button { display: flex; align-items: center; gap: 5px; padding: 6px 9px; border: 0; border-radius: 7px; color: #78839a; background: transparent; cursor: pointer; font-size: 10px; white-space: nowrap; }
.filters button span { color: #a3acbb; font-size: 9px; }
.filters button.active { color: #4c4ab8; background: #fff; box-shadow: 0 1px 4px #26345214; }
.filters button.active span { color: #7775c8; }
.survey-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.survey-card { position: relative; display: flex; min-height: 244px; flex-direction: column; padding: 17px; overflow: hidden; transition: transform .18s ease, box-shadow .18s ease; }
.survey-card:hover { transform: translateY(-2px); box-shadow: 0 12px 30px #26345212; }
.survey-card::before { position: absolute; top: 0; left: 0; width: 100%; height: 3px; content: ''; background: #7775e5; }
.survey-card.accent-1::before { background: #43b99b; }
.survey-card.accent-2::before { background: #e7aa51; }
.survey-card.accent-3::before { background: #71a1e2; }
.survey-card-top { display: flex; align-items: center; justify-content: space-between; }
.survey-symbol { width: 35px; height: 35px; display: grid; place-items: center; border-radius: 11px; color: #6563cf; background: #f0efff; font-size: 14px; font-weight: 750; }
.accent-1 .survey-symbol { color: #219b7d; background: #e8f8f2; }
.accent-2 .survey-symbol { color: #c5872e; background: #fff5e7; }
.accent-3 .survey-symbol { color: #4b83c6; background: #edf5ff; }
.status-pill { display: inline-flex; align-items: center; padding: 5px 8px; border-radius: 20px; color: #858fa4; background: #f3f5f8; font-size: 9px; white-space: nowrap; }
.status-pill.published { color: #168562; background: #eaf8f2; }
.status-pill.closed { color: #a46e21; background: #fff5e6; }
.status-pill .status-dot { width: 6px; height: 6px; margin-right: 5px; }
.survey-title { overflow: hidden; margin: 14px 0 6px; padding: 0; border: 0; color: #2c354c; background: transparent; cursor: pointer; font-size: 14px; font-weight: 700; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.survey-title:hover { color: var(--primary); }
.survey-description { min-height: 32px; overflow: hidden; margin: 0; color: #8993a8; font-size: 10px; line-height: 1.6; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.survey-meta { display: flex; gap: 14px; margin-top: 13px; color: #929bad; font-size: 10px; }
.survey-meta strong { color: #454f68; font-size: 12px; font-weight: 700; }
.deadline-line { margin-top: 6px; color: #c18a37; font-size: 9px; }
.survey-actions { display: flex; gap: 8px; margin-top: auto; padding-top: 14px; }
.survey-actions > button { min-height: 32px; flex: 1; padding: 6px 9px; font-size: 10px; }
.share-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 12px; padding-top: 10px; border-top: 1px solid #eff1f6; color: #8d98ab; font-size: 9px; }
.share-row > span { display: flex; align-items: center; gap: 6px; }
.share-row button { padding: 3px 0; border: 0; color: #6563cf; background: transparent; cursor: pointer; font-size: 9px; font-weight: 650; white-space: nowrap; }
.muted-share button { color: #8a93a5; }
.state-panel { display: flex; min-height: 220px; flex-direction: column; align-items: center; justify-content: center; padding: 25px; border: 1px dashed #dfe4ee; border-radius: 15px; background: #ffffffa8; text-align: center; }
.state-panel h3 { margin: 11px 0 5px; color: #39445e; font-size: 14px; }
.state-panel p { max-width: 360px; margin: 0 0 13px; color: #8a95a9; font-size: 11px; line-height: 1.6; }
.state-symbol, .empty-art { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 14px; color: #7775d9; background: #efefff; font-size: 23px; }
.empty-art { color: #41a98c; background: #eaf8f2; }
.compact-state { min-height: 180px; }
.loading-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.survey-skeleton { height: 244px; border-radius: 15px; background: linear-gradient(100deg, #eef1f7 20%, #f7f8fb 38%, #eef1f7 60%); background-size: 200% 100%; animation: shimmer 1.6s ease-in-out infinite; }
@keyframes shimmer { to { background-position-x: -200%; } }
@media (max-width: 1100px) {
  .survey-grid, .loading-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .section-heading { align-items: flex-start; flex-direction: column; }
  .toolbar { width: 100%; justify-content: space-between; }
}
@media (max-width: 680px) {
  .welcome-row { align-items: flex-start; }
  .page-title { font-size: 22px; }
  .welcome-copy { max-width: 230px; line-height: 1.6; }
  .create-button { min-width: auto; min-height: 38px; padding: 7px 10px; font-size: 10px; }
  .welcome-banner { min-height: 162px; padding: 22px; }
  .banner-copy { max-width: 70%; }
  .banner-copy h2 { font-size: 19px; }
  .banner-copy p { max-width: 230px; font-size: 10px; line-height: 1.5; }
  .banner-art { right: -105px; transform: scale(.8); }
  .metric-grid { gap: 8px; margin-bottom: 25px; }
  .metric-card { min-height: 99px; padding: 12px 10px; }
  .metric-top { font-size: 9px; }
  .metric-icon { width: 24px; height: 24px; font-size: 12px; }
  .metric-value { font-size: 20px; }
  .metric-foot { font-size: 8px; }
  .toolbar { align-items: stretch; flex-direction: column; gap: 8px; }
  .search-box { width: 100%; }
  .filters { width: 100%; justify-content: space-between; }
  .filters button { flex: 1; justify-content: center; padding: 6px 3px; }
  .survey-grid, .loading-grid { grid-template-columns: 1fr; }
}
</style>
