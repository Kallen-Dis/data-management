<template>
  <div class="library-page">
    <div class="library-header"><div><router-link :to="`/questions/${route.params.id}`">← 题目详情</router-link><p class="library-eyebrow" style="margin-top: 18px">CROSS-SURVEY INSIGHTS</p><h1 class="page-title">{{ question?.name || '跨问卷单题统计' }}</h1><p class="muted">相同版本跨问卷汇总，不同版本分别展示。</p></div><el-button :loading="comparing" @click="compare">查看所有版本概览</el-button></div>
    <div class="card library-toolbar"><el-select v-model="versionId" aria-label="统计题目版本" style="width: 150px" @change="resetLoad"><el-option v-for="version in question?.versions || []" :key="version.id" :label="`v${version.version_no}`" :value="version.id" /></el-select><el-date-picker v-model="dateRange" type="datetimerange" start-placeholder="开始时间" end-placeholder="结束时间" @change="resetLoad" /><el-button :loading="loading" @click="loadStats">刷新统计</el-button></div>
    <div v-if="error" class="error-banner">{{ error }}</div>
    <template v-if="statistics">
      <p class="library-note">{{ statistics.scope }}。统计单位为作答次数，不代表去重人数。{{ statistics.includes_shared_aggregates ? '已包含其他用户明确授权的汇总，不开放其原始答案。' : '' }}</p>
      <div v-loading="loading" class="library-metrics"><div class="card library-metric"><span class="muted">有效作答次数</span><strong>{{ statistics.answer_count }}</strong></div><div class="card library-metric"><span class="muted">覆盖答卷</span><strong>{{ statistics.response_count }}</strong></div><div class="card library-metric"><span class="muted">有回答的问卷</span><strong>{{ statistics.survey_count }}</strong></div><div v-if="statistics.content.type === 'number'" class="card library-metric"><span class="muted">总体平均值</span><strong>{{ number(statistics.avg) }}</strong></div></div>
      <section class="card"><div class="library-section-heading"><h2>{{ statistics.content.title }}</h2><span class="library-type">{{ TYPE_LABELS[statistics.content.type] }} · v{{ statistics.version.version_no }}</span></div>
        <template v-if="['single', 'multiple'].includes(statistics.content.type)"><div ref="chartElement" class="library-chart"></div><el-table :data="choiceRows"><el-table-column prop="option" label="选项" /><el-table-column prop="count" label="选择次数" /><el-table-column prop="percentage" label="占有效作答" /></el-table><p v-if="statistics.content.type === 'multiple'" class="library-note">多选题每次可选择多个选项，百分比之和可能超过 100%。</p></template>
        <template v-else-if="statistics.content.type === 'number'"><p class="library-note">有效数量 {{ statistics.num_count }} · 最小值 {{ number(statistics.min) }} · 最大值 {{ number(statistics.max) }} · 总和 {{ number(statistics.num_sum) }}</p><div ref="chartElement" class="library-chart"></div><p class="library-note">平均值使用全部有效答案的总和除以数量，分布区间由服务端生成。</p></template>
        <template v-else><p class="library-note">下面只显示你自己问卷的文本明细。{{ statistics.texts.restricted_count ? `另有 ${statistics.texts.restricted_count} 条仅开放聚合计数的回答。` : '' }}</p><el-table :data="statistics.texts.items" empty-text="暂无可查看的文本回答"><el-table-column prop="answer" label="回答内容" /><el-table-column label="提交时间" width="180"><template #default="{ row }">{{ new Date(row.submitted_at).toLocaleString('zh-CN') }}</template></el-table-column></el-table><el-pagination v-if="statistics.texts.total > 30" v-model:current-page="textPage" :page-size="30" :total="statistics.texts.total" layout="total, prev, pager, next" @current-change="loadStats" /></template>
      </section>
      <section v-if="comparison.length" class="card" style="margin-top: 20px"><div class="library-section-heading"><h2>版本概览</h2><span class="muted">各版本单独计算</span></div><el-table :data="comparison"><el-table-column label="版本"><template #default="{ row }">v{{ row.version.version_no }}</template></el-table-column><el-table-column prop="content.title" label="题目" /><el-table-column prop="answer_count" label="作答次数" /><el-table-column prop="survey_count" label="覆盖问卷" /><el-table-column label="数字均值"><template #default="{ row }">{{ row.content.type === 'number' ? number(row.avg) : '不适用' }}</template></el-table-column></el-table></section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from '../charts'
import api from '../api'
import { TYPE_LABELS } from '../jump'
import { errorMessage } from '../questionContent'

const route = useRoute()
const question = ref(null), versionId = ref(''), statistics = ref(null), dateRange = ref(null), textPage = ref(1), loading = ref(false), error = ref(''), comparison = ref([]), comparing = ref(false), chartElement = ref(null)
let chart = null, requestSequence = 0
let detailSequence = 0
const choiceRows = computed(() => (statistics.value?.options || []).map((option, index) => ({ option, count: statistics.value.counts[index], percentage: statistics.value.answer_count ? `${(statistics.value.counts[index] / statistics.value.answer_count * 100).toFixed(1)}%` : '0%' })))
watch(() => route.params.id, async () => {
  const sequence = ++detailSequence
  requestSequence++; statistics.value = null; comparison.value = []; question.value = null; versionId.value = ''; error.value = ''; loading.value = false
  try {
    const { data } = await api.get(`/questions/${route.params.id}`)
    if (sequence !== detailSequence) return
    question.value = data; versionId.value = data.versions.some((version) => version.id === route.query.version) ? route.query.version : data.default_version_id; await resetLoad()
  }
  catch (failure) { if (sequence === detailSequence) error.value = errorMessage(failure) }
}, { immediate: true })
function number(value) { return value == null ? '—' : Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 }) }
async function resetLoad() { textPage.value = 1; await loadStats() }
async function loadStats() {
  if (!versionId.value) return
  const sequence = ++requestSequence
  loading.value = true; error.value = ''
  try {
    const params = { offset: (textPage.value - 1) * 30, limit: 30 }
    if (dateRange.value?.length === 2) { params.start = dateRange.value[0].toISOString(); params.end = dateRange.value[1].toISOString() }
    const { data } = await api.get(`/question-versions/${versionId.value}/stats`, { params })
    if (sequence !== requestSequence) return
    statistics.value = data; await nextTick(); drawChart()
  } catch (failure) { if (sequence === requestSequence) error.value = errorMessage(failure) }
  finally { if (sequence === requestSequence) loading.value = false }
}
function drawChart() {
  chart?.dispose(); chart = null
  if (!chartElement.value) return
  chart = echarts.init(chartElement.value)
  const numeric = statistics.value.content.type === 'number'
  const labels = numeric ? statistics.value.histogram.map((bucket) => `${number(bucket.min)}–${number(bucket.max)}`) : statistics.value.options
  const counts = numeric ? statistics.value.histogram.map((bucket) => bucket.count) : statistics.value.counts
  chart.setOption({ color: ['#5c5bdc'], tooltip: { trigger: 'axis' }, grid: { left: 58, right: 30, bottom: 75 }, xAxis: { type: 'category', data: labels, name: numeric ? '数值区间' : '选项', nameLocation: 'middle', nameGap: 48, axisLabel: { interval: 0, overflow: 'truncate', width: 90 } }, yAxis: { type: 'value', minInterval: 1, name: '作答次数' }, series: [{ type: 'bar', data: counts, barMaxWidth: 55, itemStyle: { borderRadius: [5, 5, 0, 0] } }] })
}
async function compare() { const seriesId = route.params.id; comparing.value = true; try { const { data } = await api.get(`/questions/${seriesId}/stats`); if (seriesId === route.params.id) comparison.value = data.versions } catch (failure) { if (seriesId === route.params.id) error.value = errorMessage(failure) } finally { comparing.value = false } }
const resizeObserver = new ResizeObserver(() => chart?.resize())
watch(chartElement, (element, previous) => { if (previous) resizeObserver.unobserve(previous); if (element) resizeObserver.observe(element) })
onBeforeUnmount(() => { detailSequence++; requestSequence++; resizeObserver.disconnect(); chart?.dispose() })
</script>
