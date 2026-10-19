<template>
  <div class="stats-page">
    <section class="report-heading">
      <div class="heading-copy">
        <button class="back-link" @click="$router.push('/')">← <span>返回问卷</span></button>
        <div class="eyebrow">RESPONSE ANALYTICS</div>
        <h1 class="page-title">{{ view.title || '问卷数据报告' }}</h1>
        <p class="report-subtitle">汇总回答趋势，快速看见每个问题背后的信息。</p>
      </div>
      <div class="report-actions">
        <button class="btn-ghost" :disabled="loading" @click="load">↻ 刷新</button>
        <button class="btn-primary" :disabled="rebuilding" @click="rebuild">{{ rebuilding ? '正在重建…' : '⟳ 重建统计' }}</button>
      </div>
    </section>

    <div v-if="loading && !view.questions.length" class="loading-state"><span class="spinner"></span>正在整理问卷数据…</div>
    <template v-else>
      <div v-if="loadError" class="error-banner">{{ loadError }}</div>
      <section class="overview-grid">
        <div class="overview-card total-card">
          <div class="overview-label">累计提交</div>
          <div class="overview-value">{{ view.total.toLocaleString('zh-CN') }}<small>份</small></div>
          <div class="overview-foot"><span class="overview-mark">↗</span>所有有效答卷</div>
          <div class="overview-decoration"></div>
        </div>
        <div class="overview-card">
          <div class="overview-label">平均填写时长</div>
          <div class="overview-value">{{ avgSpent }}<small>秒</small></div>
          <div class="overview-foot">按提交记录计算</div>
          <div class="overview-icon clock-icon">◷</div>
        </div>
        <div class="overview-card">
          <div class="overview-label">问卷题目</div>
          <div class="overview-value">{{ view.questions.length }}<small>题</small></div>
          <div class="overview-foot">包含所有当前题型</div>
          <div class="overview-icon question-icon">▤</div>
        </div>
      </section>

      <div v-if="loadError" class="empty-report card">
        <div class="empty-icon">↻</div>
        <h2>报告没有加载完整</h2>
        <p>检查网络连接后刷新，答卷数据仍保存在系统中。</p>
        <button class="btn-ghost" @click="load">重新加载</button>
      </div>
      <div v-else-if="!view.total" class="empty-report card">
        <div class="empty-icon">▥</div>
        <h2>第一份回答还在路上</h2>
        <p>发布问卷并分享填写链接，收到回答后这里会自动生成数据报告。</p>
        <button class="btn-ghost" @click="$router.push(`/editor/${route.params.id}`)">返回编辑问卷</button>
      </div>
      <section v-else class="question-reports">
        <div class="reports-title"><div><h2>题目分析</h2><span>按题目查看回答分布与原始反馈</span></div><span class="report-count">{{ view.questions.length }} 个问题</span></div>

        <article v-for="(question, index) in view.questions" :key="question.qid" class="question-report card">
          <div class="question-heading">
            <div class="question-index">{{ String(index + 1).padStart(2, '0') }}</div>
            <div class="question-copy">
              <div class="question-kicker"><span class="type-badge" :class="question.type">{{ TYPE_LABELS[question.type] }}</span><span>问题 {{ index + 1 }}</span></div>
              <h3>{{ question.title }}</h3>
            </div>
            <div v-if="question.type === 'number'" class="answer-count">{{ question.num_count }} <span>份有效数字</span></div>
          </div>

          <div v-if="question.type === 'single'" class="chart-layout">
            <div class="chart-panel"><div class="chart-caption">选项占比</div><div :id="`c-${question.qid}-pie`" class="chart pie-chart"></div></div>
            <div class="chart-panel"><div class="chart-caption">回答人数</div><div :id="`c-${question.qid}-bar`" class="chart"></div></div>
            <div class="choice-legend">
              <div v-for="(option, optionIndex) in question.options" :key="`${option}-${optionIndex}`" class="legend-row">
                <span class="legend-color" :style="{ background: palette[optionIndex % palette.length] }"></span>
                <span class="legend-label">{{ option }}</span>
                <strong>{{ question.counts?.[optionIndex] || 0 }}</strong>
                <span class="legend-percent">{{ percent(question.counts?.[optionIndex] || 0, question.counts?.reduce((sum, count) => sum + count, 0) || 0) }}%</span>
              </div>
            </div>
          </div>

          <div v-else-if="question.type === 'multiple'" class="chart-layout multiple-layout">
            <div class="chart-panel"><div class="chart-caption">选项被选择次数 <small>多选题每人可选择多个答案</small></div><div :id="`c-${question.qid}-bar`" class="chart wide-chart"></div></div>
            <div class="choice-legend horizontal-legend">
              <div v-for="(option, optionIndex) in question.options" :key="`${option}-${optionIndex}`" class="legend-row">
                <span class="legend-color" :style="{ background: palette[optionIndex % palette.length] }"></span>
                <span class="legend-label">{{ option }}</span>
                <strong>{{ question.counts?.[optionIndex] || 0 }}</strong>
                <span class="legend-percent">次</span>
              </div>
            </div>
          </div>

          <div v-else-if="question.type === 'number'" class="number-layout">
            <div class="number-summary">
              <div><span>平均值</span><strong>{{ question.avg ?? '—' }}</strong></div>
              <div><span>中位数</span><strong>{{ numberSummary(question.qid).median }}</strong></div>
              <div><span>范围</span><strong class="range-value">{{ numberSummary(question.qid).range }}</strong></div>
            </div>
            <div class="chart-panel"><div class="chart-caption">数值分布 <small>{{ question.num_count }} 份有效回答</small></div><div :id="`c-${question.qid}-hist`" class="chart wide-chart"></div></div>
          </div>

          <div v-else class="text-layout">
            <div class="text-insight">
              <div class="text-heading"><div><strong>高频词语</strong><span>从文本回答中提取</span></div><span>{{ textCloud[question.qid]?.length || 0 }} 个词</span></div>
              <div class="cloud">
                <span v-for="word in textCloud[question.qid] || []" :key="word.text" class="cloud-tag" :style="{ fontSize: `${12 + Math.min(word.count, 8) * 2}px` }">
                  {{ word.text }}<i>{{ word.count }}</i>
                </span>
                <span v-if="!(textCloud[question.qid] || []).length" class="empty-inline">暂无可统计的文本</span>
              </div>
            </div>
            <div class="text-answers">
              <div class="text-heading"><div><strong>回答明细</strong><span>按提交时间排列</span></div><span>{{ textList[question.qid]?.length || 0 }} 条回答</span></div>
              <div v-if="(textList[question.qid] || []).length" class="answer-list">
                <div v-for="(answer, answerIndex) in textList[question.qid]" :key="`${question.qid}-${answerIndex}`" class="answer-item">
                  <span>{{ String(answerIndex + 1).padStart(2, '0') }}</span><p>{{ answer }}</p>
                </div>
              </div>
              <div v-else class="empty-inline">暂无文本回答</div>
            </div>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api from '../api'
import { TYPE_LABELS } from '../jump'

const route = useRoute()
const view = ref({ title: '', total: 0, questions: [] })
const responses = ref([])
const textCloud = ref({})
const textList = ref({})
const loading = ref(true)
const rebuilding = ref(false)
const loadError = ref('')
let charts = []

const palette = ['#6866dd', '#42b995', '#e7a548', '#6398df', '#e77889', '#52b8c4', '#9b78d0', '#91b863']
const avgSpent = computed(() => {
  const values = responses.value.map((response) => Number(response.spent_seconds)).filter(Number.isFinite)
  return values.length ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length) : 0
})
const numericAnswers = computed(() => {
  const byQuestion = {}
  for (const question of view.value.questions.filter((item) => item.type === 'number')) {
    byQuestion[question.qid] = responses.value
      .filter((response) => {
        const snapshotQuestion = response.snapshot?.questions?.find((item) => item.qid === question.qid)
        return !snapshotQuestion || snapshotQuestion.type === 'number'
      })
      .map((response) => response.answers?.[question.qid])
      .filter((answer) => typeof answer === 'string' && answer.trim() !== '')
      .map(Number)
      .filter(Number.isFinite)
      .sort((first, second) => first - second)
  }
  return byQuestion
})

onMounted(load)
onBeforeUnmount(() => {
  disposeCharts()
  window.removeEventListener('resize', resizeCharts)
})

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const [stats, details] = await Promise.all([
      api.get(`/surveys/${route.params.id}/stats`),
      api.get(`/surveys/${route.params.id}/responses`),
    ])
    view.value = stats.data
    responses.value = details.data
    buildTextData()
    await nextTick()
    renderCharts()
    window.removeEventListener('resize', resizeCharts)
    window.addEventListener('resize', resizeCharts, { passive: true })
  } catch (error) {
    loadError.value = error.response?.data?.detail || '数据暂时无法加载，请稍后刷新。'
  } finally {
    loading.value = false
  }
}

async function rebuild() {
  rebuilding.value = true
  try {
    await api.post(`/surveys/${route.params.id}/stats/rebuild`)
    ElMessage.success('统计数据已从答卷快照重建')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重建失败，请稍后重试')
  } finally {
    rebuilding.value = false
  }
}

function buildTextData() {
  const cloud = {}
  const list = {}
  const stopWords = new Set(['我们', '你们', '他们', '这个', '那个', '因为', '所以', '还是', '可以', '没有', '非常', '就是', '一个', '一些', '觉得', '比较', '然后', '如果', '但是', '希望', '自己', '什么', '这个', 'the', 'and', 'for', 'with', 'that', 'this'])
  const segmenter = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter('zh-CN', { granularity: 'word' }) : null
  for (const question of view.value.questions.filter((item) => item.type === 'text')) {
    const answers = responses.value
      .filter((response) => {
        const snapshotQuestion = response.snapshot?.questions?.find((item) => item.qid === question.qid)
        return !snapshotQuestion || snapshotQuestion.type === 'text'
      })
      .map((response) => response.answers?.[question.qid])
      .filter((answer) => typeof answer === 'string' && answer.trim())
    list[question.qid] = answers
    const frequency = new Map()
    for (const answer of answers) {
      const tokens = segmenter
        ? [...segmenter.segment(answer)].filter((part) => part.isWordLike).map((part) => part.segment)
        : answer.match(/[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}/g) || []
      for (const rawToken of tokens) {
        const token = rawToken.trim().toLocaleLowerCase()
        if (Array.from(token).length < 2 || stopWords.has(token) || /^\d+$/.test(token)) continue
        frequency.set(token, (frequency.get(token) || 0) + 1)
      }
    }
    cloud[question.qid] = [...frequency.entries()]
      .map(([text, count]) => ({ text, count }))
      .sort((first, second) => second.count - first.count || first.text.localeCompare(second.text, 'zh-CN'))
      .slice(0, 24)
  }
  textCloud.value = cloud
  textList.value = list
}

function numberSummary(qid) {
  const values = numericAnswers.value[qid] || []
  if (!values.length) return { median: '—', range: '—' }
  const middle = Math.floor(values.length / 2)
  const median = values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2
  return { median: formatNumber(median), range: `${formatNumber(values[0])} – ${formatNumber(values.at(-1))}` }
}

function formatNumber(value) {
  return Number.isInteger(value) ? String(value) : Number(value.toFixed(2)).toString()
}

function percent(value, total) {
  return total ? Math.round((value / total) * 100) : 0
}

function initChart(id) {
  const element = document.getElementById(id)
  if (!element) return null
  const chart = echarts.init(element)
  charts.push(chart)
  return chart
}

function renderCharts() {
  disposeCharts()
  for (const question of view.value.questions) {
    if (question.type === 'single') renderSingle(question)
    else if (question.type === 'multiple') renderMultiple(question)
    else if (question.type === 'number') renderNumber(question)
  }
}

function renderSingle(question) {
  const options = question.options || []
  const counts = question.counts || []
  const pie = initChart(`c-${question.qid}-pie`)
  pie?.setOption({
    color: palette,
    tooltip: { trigger: 'item', formatter: '{b}<br>{c} 份回答 · {d}%' },
    series: [{
      type: 'pie', radius: ['51%', '74%'], center: ['50%', '52%'],
      itemStyle: { borderColor: '#fff', borderWidth: 3, borderRadius: 5 },
      label: { show: true, formatter: '{d}%', color: '#59647b', fontSize: 10 },
      emphasis: { scaleSize: 7 },
      data: options.map((name, index) => ({ name, value: counts[index] || 0 })),
    }],
  })
  const bar = initChart(`c-${question.qid}-bar`)
  bar?.setOption(barOption(options, counts))
}

function renderMultiple(question) {
  initChart(`c-${question.qid}-bar`)?.setOption(barOption(question.options || [], question.counts || [], true))
}

function barOption(labels, values, varied = false) {
  return {
    color: [palette[0]],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (items) => `${labels[items[0].dataIndex]}<br><strong>${items[0].value}</strong> 次` },
    grid: { top: 14, bottom: labels.length > 5 ? 58 : 42, left: 42, right: 18, containLabel: false },
    xAxis: { type: 'category', data: labels, axisTick: { show: false }, axisLine: { lineStyle: { color: '#e8ebf2' } }, axisLabel: { color: '#7d879c', fontSize: 9, interval: 0, rotate: labels.length > 4 ? 25 : 0, formatter: (value) => value.length > 10 ? `${value.slice(0, 9)}…` : value } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#f0f2f6', type: 'dashed' } }, axisLabel: { color: '#9aa3b3', fontSize: 9 } },
    series: [{ type: 'bar', data: values, barMaxWidth: 38, itemStyle: { color: (params) => varied ? palette[params.dataIndex % palette.length] : palette[0], borderRadius: [5, 5, 0, 0] }, showBackground: true, backgroundStyle: { color: '#f5f6fa', borderRadius: [5, 5, 0, 0] } }],
  }
}

function renderNumber(question) {
  const values = numericAnswers.value[question.qid] || []
  if (!values.length) return
  const minimum = values[0]
  const maximum = values[values.length - 1]
  let bins
  if (minimum === maximum) {
    bins = [{ low: minimum, high: maximum, count: values.length, label: formatNumber(minimum) }]
  } else {
    const binCount = Math.max(4, Math.min(10, Math.ceil(1 + Math.log2(values.length))))
    const width = (maximum - minimum) / binCount
    bins = Array.from({ length: binCount }, (_, index) => {
      const low = minimum + index * width
      const high = index === binCount - 1 ? maximum : minimum + (index + 1) * width
      return { low, high, count: 0, label: `${formatNumber(low)}–` }
    })
    for (const value of values) {
      const index = Math.min(Math.floor((value - minimum) / width), binCount - 1)
      bins[index].count += 1
    }
  }
  initChart(`c-${question.qid}-hist`)?.setOption({
    color: [palette[2]],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: (items) => {
      const bin = bins[items[0].dataIndex]
      const range = bin.low === bin.high ? formatNumber(bin.low) : `${formatNumber(bin.low)} – ${formatNumber(bin.high)}`
      return `${range}<br><strong>${bin.count}</strong> 份回答`
    } },
    grid: { top: 10, bottom: 38, left: 42, right: 18 },
    xAxis: { type: 'category', data: bins.map((bin) => bin.label), axisTick: { show: false }, axisLine: { lineStyle: { color: '#e8ebf2' } }, axisLabel: { color: '#7d879c', fontSize: 9 } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#f0f2f6', type: 'dashed' } }, axisLabel: { color: '#9aa3b3', fontSize: 9 } },
    series: [{ type: 'bar', data: bins.map((bin) => bin.count), barMaxWidth: 42, itemStyle: { color: palette[2], borderRadius: [5, 5, 0, 0] }, showBackground: true, backgroundStyle: { color: '#f5f6fa' } }],
  })
}

function disposeCharts() {
  charts.forEach((chart) => chart.dispose())
  charts = []
}

function resizeCharts() {
  charts.forEach((chart) => chart.resize())
}
</script>

<style scoped>
.stats-page { max-width: 1260px; margin: 0 auto; }
.report-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 21px; }
.back-link { display: flex; align-items: center; gap: 7px; margin: 0 0 17px; padding: 0; border: 0; color: #737e94; background: transparent; cursor: pointer; font-size: 11px; }
.back-link:hover { color: var(--primary); }
.eyebrow { margin-bottom: 7px; color: #8d8bbf; font-size: 9px; font-weight: 750; letter-spacing: .15em; }
.report-subtitle { margin: 7px 0 0; color: #8892a7; font-size: 11px; }
.report-actions { display: flex; gap: 8px; }
.report-actions button { min-height: 35px; font-size: 10px; }
.overview-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 13px; margin-bottom: 27px; }
.overview-card { position: relative; min-height: 123px; overflow: hidden; padding: 17px 19px; border: 1px solid var(--border); border-radius: 14px; background: #fff; box-shadow: var(--shadow); }
.total-card { border-color: #deddf9; background: linear-gradient(125deg, #f0efff, #fff 85%); }
.overview-label { color: #818ba0; font-size: 10px; }
.overview-value { position: relative; z-index: 1; margin-top: 6px; color: #2c3550; font-size: 27px; font-weight: 750; letter-spacing: -.04em; }
.total-card .overview-value { color: #514fc2; }
.overview-value small { margin-left: 5px; color: #9099ac; font-size: 11px; font-weight: 550; letter-spacing: 0; }
.overview-foot { display: flex; align-items: center; gap: 6px; margin-top: 4px; color: #9aa3b4; font-size: 9px; }
.overview-mark { color: #23aa80; font-size: 14px; }
.overview-icon { position: absolute; right: 19px; bottom: 18px; width: 30px; height: 30px; display: grid; place-items: center; border-radius: 10px; color: #7977d5; background: #f0efff; font-size: 19px; }
.question-icon { color: #239d7d; background: #eaf8f2; font-size: 13px; }
.overview-decoration { position: absolute; right: -16px; bottom: -66px; width: 150px; height: 150px; border: 1px solid #7774df26; border-radius: 50%; box-shadow: 0 0 0 14px #7774df0b, 0 0 0 29px #7774df08; }
.empty-report { display: flex; min-height: 260px; flex-direction: column; align-items: center; justify-content: center; text-align: center; }
.empty-icon { width: 48px; height: 48px; display: grid; place-items: center; border-radius: 15px; color: #7775d9; background: #efefff; font-size: 23px; }
.empty-report h2 { margin: 12px 0 5px; color: #39435b; font-size: 16px; }
.empty-report p { margin: 0 0 14px; color: #8994a8; font-size: 11px; }
.empty-report button { min-height: 34px; font-size: 10px; }
.reports-title { display: flex; align-items: center; justify-content: space-between; margin: 0 1px 13px; }
.reports-title h2 { margin: 0; color: #2e374f; font-size: 15px; font-weight: 750; }
.reports-title span { color: #949db0; font-size: 10px; }
.reports-title > div > span { display: block; margin-top: 4px; }
.report-count { padding: 5px 9px; border-radius: 15px; color: #6c6abe !important; background: #efefff; }
.question-report { margin-bottom: 14px; padding: 19px 20px 18px; }
.question-heading { display: flex; align-items: center; gap: 12px; padding-bottom: 16px; border-bottom: 1px solid #eff1f6; }
.question-index { width: 35px; height: 35px; display: grid; place-items: center; flex-shrink: 0; border-radius: 11px; color: #6664c9; background: #f0efff; font-size: 11px; font-weight: 750; }
.question-copy { min-width: 0; flex: 1; }
.question-kicker { display: flex; align-items: center; gap: 8px; color: #a0a8b8; font-size: 9px; }
.type-badge { padding: 4px 7px; border-radius: 6px; color: #6260c6; background: #efefff; font-size: 9px; }
.type-badge.multiple { color: #258c79; background: #e9f7f1; }
.type-badge.number { color: #b57a2d; background: #fff4e4; }
.type-badge.text { color: #5287bf; background: #edf5ff; }
.question-copy h3 { overflow: hidden; margin: 6px 0 0; color: #303a52; font-size: 13px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.answer-count { color: #555fc1; font-size: 16px; font-weight: 750; white-space: nowrap; }
.answer-count span { color: #969fb0; font-size: 9px; font-weight: 500; }
.chart-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(150px, .72fr); align-items: center; gap: 13px; padding-top: 14px; }
.chart-panel { min-width: 0; }
.chart-caption { margin: 0 0 3px; color: #7e899f; font-size: 9px; font-weight: 650; }
.chart-caption small { margin-left: 5px; color: #a4acba; font-size: 8px; font-weight: 450; }
.chart { width: 100%; height: 205px; }
.pie-chart { height: 192px; }
.wide-chart { height: 224px; }
.choice-legend { display: flex; flex-direction: column; gap: 10px; padding: 4px 2px 4px 12px; border-left: 1px solid #eff1f5; }
.legend-row { min-width: 0; display: flex; align-items: center; gap: 7px; color: #8993a7; font-size: 9px; }
.legend-color { width: 7px; height: 7px; flex-shrink: 0; border-radius: 3px; }
.legend-label { overflow: hidden; flex: 1; text-overflow: ellipsis; white-space: nowrap; }
.legend-row strong { color: #3e4962; font-size: 10px; }
.legend-percent { min-width: 29px; color: #a2aabb; text-align: right; }
.multiple-layout { grid-template-columns: minmax(0, 1fr); }
.horizontal-legend { flex-direction: row; flex-wrap: wrap; gap: 9px 18px; padding: 12px 3px 0; border-top: 1px solid #eff1f5; border-left: 0; }
.horizontal-legend .legend-row { min-width: 130px; max-width: 210px; flex: 1; }
.number-layout { padding-top: 15px; }
.number-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; margin-bottom: 11px; }
.number-summary > div { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 12px; border: 1px solid #edf0f5; border-radius: 9px; background: #fafbfe; }
.number-summary span { color: #909aac; font-size: 9px; }
.number-summary strong { color: #39445c; font-size: 13px; }
.number-summary .range-value { font-size: 10px; }
.text-layout { display: grid; grid-template-columns: minmax(0, .8fr) minmax(0, 1.2fr); gap: 14px; padding-top: 15px; }
.text-insight, .text-answers { min-width: 0; overflow: hidden; border: 1px solid #edf0f5; border-radius: 11px; background: #fcfcfe; }
.text-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px 13px 10px; border-bottom: 1px solid #eff1f5; color: #9aa3b2; font-size: 8px; }
.text-heading > div { display: flex; flex-direction: column; gap: 4px; }
.text-heading strong { color: #46516a; font-size: 10px; }
.cloud { min-height: 138px; display: flex; align-content: flex-start; flex-wrap: wrap; align-items: baseline; gap: 9px; padding: 14px; }
.cloud-tag { color: #6462ca; font-weight: 650; }
.cloud-tag:nth-child(3n) { color: #259a7b; }
.cloud-tag:nth-child(3n + 1) { color: #b1803d; }
.cloud-tag i { margin-left: 3px; color: #a6adbb; font-size: 8px; font-style: normal; font-weight: 450; }
.empty-inline { padding: 18px 14px; color: #a0a8b6; font-size: 9px; }
.answer-list { max-height: 190px; overflow: auto; padding: 4px 12px; }
.answer-item { display: flex; gap: 9px; padding: 9px 2px; border-bottom: 1px solid #f0f2f6; }
.answer-item:last-child { border-bottom: 0; }
.answer-item > span { padding-top: 2px; color: #a4acba; font-size: 8px; }
.answer-item p { margin: 0; color: #626e83; font-size: 10px; line-height: 1.55; overflow-wrap: anywhere; }
.loading-state { display: flex; min-height: 220px; align-items: center; justify-content: center; gap: 10px; color: #8792a8; font-size: 11px; }
.spinner { width: 17px; height: 17px; border: 2px solid #e4e5f7; border-top-color: var(--primary); border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1050px) {
  .chart-layout { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .chart-layout > .choice-legend { grid-column: span 2; flex-direction: row; flex-wrap: wrap; padding: 11px 3px 0; border-top: 1px solid #eff1f5; border-left: 0; }
  .chart-layout > .choice-legend .legend-row { min-width: 135px; flex: 1; }
}
@media (max-width: 680px) {
  .report-heading { align-items: flex-start; flex-direction: column; }
  .report-heading .heading-copy { width: 100%; }
  .back-link { margin-bottom: 13px; }
  .report-actions { width: 100%; }
  .report-actions button { flex: 1; }
  .overview-grid { gap: 8px; }
  .overview-card { min-height: 106px; padding: 12px 10px; }
  .overview-label { font-size: 9px; }
  .overview-value { font-size: 22px; }
  .overview-icon { right: 9px; bottom: 10px; width: 24px; height: 24px; }
  .overview-foot { font-size: 8px; }
  .question-report { padding: 14px 12px; }
  .question-heading { gap: 9px; }
  .question-index { width: 30px; height: 30px; }
  .answer-count { font-size: 13px; }
  .answer-count span { display: block; margin-top: 2px; text-align: right; }
  .chart-layout { grid-template-columns: 1fr; gap: 8px; }
  .chart-layout > .choice-legend { grid-column: auto; }
  .chart { height: 190px; }
  .pie-chart { height: 180px; }
  .multiple-layout .wide-chart { height: 210px; }
  .text-layout { grid-template-columns: 1fr; }
  .number-summary > div { align-items: flex-start; flex-direction: column; gap: 5px; padding: 9px; }
  .number-summary strong { font-size: 12px; }
  .number-summary .range-value { font-size: 9px; }
}
</style>
