<template>
  <div class="library-page">
    <div class="library-header"><div><p class="library-eyebrow">QUESTION BANKS</p><h1 class="page-title">把常用题目整理成题库</h1><p class="muted">题库固定选用版本，升级由你决定。</p></div><el-button type="primary" @click="openCreate">新建题库</el-button></div>
    <div v-if="error" class="error-banner">{{ error }} <el-button @click="loadBanks">重试</el-button></div>
    <el-checkbox v-model="archived" style="margin-bottom: 16px" @change="loadBanks">查看已归档题库</el-checkbox>
    <div v-loading="loading" class="library-two-column">
      <aside class="card"><button v-for="bank in banks" :key="bank.id" class="library-bank-button" :class="{ active: bank.id === bankId }" @click="selectBank(bank.id)"><strong>{{ bank.name }}</strong><small>{{ bank.item_count }} 道题</small></button><el-empty v-if="!banks.length" description="暂无题库" :image-size="60" /></aside>
      <section v-if="current" class="card">
        <div class="library-section-heading"><div><h2>{{ current.name }}</h2><p class="muted">{{ current.description || '在这里收藏可重复使用的题目。' }}</p></div><div class="library-inline"><el-button @click="openEdit">设置</el-button><el-button v-if="!current.archived_at" type="primary" @click="pickerOpen = true">添加题目</el-button></div></div>
        <el-table :data="items" empty-text="题库还没有题目，点击添加题目开始整理">
          <el-table-column label="题目"><template #default="{ row }"><router-link v-if="row.available" :to="`/questions/${row.series_id}`">{{ row.content.title }}</router-link><span v-else>题目已归档或共享已撤销</span></template></el-table-column>
          <el-table-column label="固定版本" width="110"><template #default="{ row }">{{ row.available ? `v${row.version_no}` : '不可新增引用' }}</template></el-table-column>
          <el-table-column label="操作" min-width="200"><template #default="{ row }"><el-button v-if="row.available" link :disabled="!!current.archived_at" @click="openVersion(row)">{{ row.has_new_version ? '有新版 · 选择版本' : '切换版本' }}</el-button><el-button link type="danger" @click="remove(row)">移出题库</el-button></template></el-table-column>
        </el-table>
        <el-pagination v-if="itemTotal > 30" v-model:current-page="itemPage" :page-size="30" :total="itemTotal" layout="prev, pager, next" @current-change="loadItems" />
      </section>
    </div>
    <el-dialog v-model="bankOpen" :title="editing ? '题库设置' : '新建题库'" width="480px"><el-form label-position="top"><el-form-item label="名称"><el-input v-model="name" aria-label="题库名称" maxlength="100" /></el-form-item><el-form-item label="说明"><el-input v-model="description" type="textarea" aria-label="题库说明" maxlength="2000" /></el-form-item><el-checkbox v-if="editing" v-model="bankArchived">归档题库 已有问卷不受影响</el-checkbox></el-form><template #footer><el-button @click="bankOpen = false">取消</el-button><el-button type="primary" :loading="busy" @click="saveBank">保存</el-button></template></el-dialog>
    <el-dialog v-model="versionOpen" title="切换题库固定版本" width="450px"><p class="library-note">只更新这个题库条目，已经创建的问卷不自动升级。</p><el-select v-model="versionId" aria-label="题库固定版本" style="width: 100%"><el-option v-for="version in versions" :key="version.id" :label="`v${version.version_no} · ${version.content.title}`" :value="version.id" /></el-select><template #footer><el-button type="primary" :loading="busy" @click="updateVersion">确认切换</el-button></template></el-dialog>
    <QuestionPicker v-model="pickerOpen" @select="addItem" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import QuestionPicker from '../components/QuestionPicker.vue'
import { errorMessage } from '../questionContent'

const banks = ref([]), bankId = ref(''), items = ref([]), archived = ref(false), loading = ref(false), error = ref(''), busy = ref(false)
const itemPage = ref(1), itemTotal = ref(0), bankOpen = ref(false), editing = ref(false), name = ref(''), description = ref(''), bankArchived = ref(false), pickerOpen = ref(false)
const versionOpen = ref(false), versions = ref([]), versionId = ref(''), selectedItem = ref(null)
let itemsSequence = 0
const current = computed(() => banks.value.find((bank) => bank.id === bankId.value))
onMounted(loadBanks)
async function loadBanks() { loading.value = true; error.value = ''; try { banks.value = (await api.get('/question-banks', { params: { archived: archived.value, page_size: 100 } })).data.items; if (!banks.value.some((bank) => bank.id === bankId.value)) bankId.value = banks.value[0]?.id || ''; await loadItems() } catch (failure) { error.value = errorMessage(failure) } finally { loading.value = false } }
async function selectBank(selectedId) { bankId.value = selectedId; itemPage.value = 1; await loadItems() }
async function loadItems() { const sequence = ++itemsSequence; if (!bankId.value) { items.value = []; itemTotal.value = 0; return } try { const { data } = await api.get(`/question-banks/${bankId.value}/items`, { params: { page: itemPage.value, page_size: 30 } }); if (sequence !== itemsSequence) return; items.value = data.items; itemTotal.value = data.total } catch (failure) { if (sequence === itemsSequence) error.value = errorMessage(failure) } }
function openCreate() { editing.value = false; name.value = ''; description.value = ''; bankOpen.value = true }
function openEdit() { editing.value = true; name.value = current.value.name; description.value = current.value.description; bankArchived.value = !!current.value.archived_at; bankOpen.value = true }
async function perform(action) { if (busy.value) return; busy.value = true; try { await action() } catch (failure) { if (failure !== 'cancel' && failure !== 'close') ElMessage.error(errorMessage(failure)) } finally { busy.value = false } }
async function saveBank() { await perform(async () => { const payload = { name: name.value, description: description.value }; const { data } = editing.value ? await api.patch(`/question-banks/${bankId.value}`, { ...payload, revision: current.value.revision, archived: bankArchived.value }) : await api.post('/question-banks', payload); bankId.value = data.id; bankOpen.value = false; await loadBanks(); ElMessage.success('题库已保存') }) }
async function addItem(question) { await perform(async () => { await api.post(`/question-banks/${bankId.value}/items`, { version_id: question.question_version_id }); await loadBanks(); ElMessage.success('题目已加入题库') }) }
async function remove(item) { await perform(async () => { await ElMessageBox.confirm('移出题库不会删除题目，也不会影响已有问卷。', '移出题库'); await api.delete(`/question-banks/${bankId.value}/items/${item.id}`); await loadBanks() }) }
async function openVersion(item) { try { const { data } = await api.get(`/questions/${item.series_id}`); selectedItem.value = item; versions.value = data.versions.filter((version) => version.can_use); versionId.value = item.selected_version_id; versionOpen.value = true } catch (failure) { ElMessage.error(errorMessage(failure)) } }
async function updateVersion() { await perform(async () => { await api.patch(`/question-banks/${bankId.value}/items/${selectedItem.value.id}`, { version_id: versionId.value, revision: selectedItem.value.revision }); versionOpen.value = false; await loadItems(); ElMessage.success('题库版本已更新') }) }
</script>
