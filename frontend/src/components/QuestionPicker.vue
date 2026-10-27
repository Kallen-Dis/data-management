<template>
  <el-dialog :model-value="modelValue" title="从题目中心或题库选题" width="720px" @update:model-value="emit('update:modelValue', $event)">
    <div class="library-toolbar">
      <el-radio-group v-model="scope" @change="resetLoad"><el-radio-button value="mine">我的题目</el-radio-button><el-radio-button value="shared">分享给我</el-radio-button><el-radio-button value="bank">我的题库</el-radio-button></el-radio-group>
      <el-select v-if="scope === 'bank'" v-model="bankId" aria-label="选择题库" placeholder="选择题库" @change="resetLoad"><el-option v-for="bank in banks" :key="bank.id" :label="bank.name" :value="bank.id" /></el-select>
      <el-input v-else v-model="search" aria-label="搜索题目" placeholder="搜索题目" clearable @keyup.enter="resetLoad" @clear="resetLoad" />
    </div>
    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-loading="loading" class="picker-list">
      <article v-for="item in items" :key="item.id" class="picker-item">
        <div><span class="library-type">{{ TYPE_LABELS[selectedVersion(item)?.content?.type] || '题目' }}</span><strong>{{ item.name }}</strong><p class="muted">{{ item.owner_username || '题库条目' }}</p></div>
        <div class="library-inline"><el-select v-model="selectedIds[item.id]" aria-label="选择题目版本" style="width: 105px"><el-option v-for="version in item.versions" :key="version.id" :label="`v${version.version_no}`" :value="version.id" /></el-select><el-button type="primary" :disabled="!selectedVersion(item)" @click="choose(item)">选用</el-button></div>
      </article>
      <el-empty v-if="!loading && !items.length" description="没有可选题目，可先在题目中心创建或请其他用户分享" :image-size="70" />
    </div>
    <el-pagination v-if="total > 20" v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next" @current-change="load" />
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../api'
import { TYPE_LABELS } from '../jump'
import { errorMessage } from '../questionContent'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'select'])
const scope = ref('mine'), search = ref(''), banks = ref([]), bankId = ref(''), items = ref([]), selectedIds = ref({})
const loading = ref(false), error = ref(''), page = ref(1), total = ref(0)
let requestSequence = 0
watch(() => props.modelValue, async (open) => {
  if (!open) return
  try { banks.value = (await api.get('/question-banks', { params: { page_size: 100 } })).data.items } catch (failure) { error.value = errorMessage(failure) }
  await resetLoad()
})
function selectedVersion(item) { return item.versions.find((version) => version.id === selectedIds.value[item.id]) }
async function resetLoad() { page.value = 1; await load() }
async function load() {
  const sequence = ++requestSequence
  loading.value = true; error.value = ''
  try {
    if (scope.value === 'bank' && !bankId.value) { items.value = []; total.value = 0; return }
    const response = scope.value === 'bank'
      ? await api.get(`/question-banks/${bankId.value}/items`, { params: { page: page.value, page_size: 20 } })
      : await api.get('/questions', { params: { scope: scope.value, search: search.value, page: page.value, page_size: 20 } })
    if (sequence !== requestSequence) return
    items.value = scope.value === 'bank' ? response.data.items.filter((item) => item.available).map((item) => ({ id: item.series_id, name: item.content.title, default_version_id: item.selected_version_id, versions: [{ id: item.selected_version_id, version_no: item.version_no, content: item.content }] })) : response.data.items
    items.value = items.value.map((item) => ({ ...item, versions: item.versions.filter((version) => version.can_use !== false) })).filter((item) => item.versions.length)
    total.value = response.data.total
    for (const item of items.value) selectedIds.value[item.id] = item.versions.some((version) => version.id === item.default_version_id) ? item.default_version_id : item.versions[0].id
  } catch (failure) { if (sequence === requestSequence) error.value = errorMessage(failure) }
  finally { if (sequence === requestSequence) loading.value = false }
}
function choose(item) {
  const version = selectedVersion(item)
  emit('select', { ...version.content, question_series_id: item.id, question_version_id: version.id })
  emit('update:modelValue', false)
}
</script>
