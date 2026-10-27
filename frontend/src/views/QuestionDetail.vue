<template>
  <div v-loading="loading" class="library-page">
    <div v-if="error" class="error-banner">{{ error }} <el-button @click="load">重试</el-button></div>
    <template v-if="question && selected">
      <div class="library-header">
        <div><router-link to="/questions">← 题目中心</router-link><h1 class="page-title" style="margin-top: 15px">{{ question.name }}</h1><p class="muted">{{ question.owner_username }} · 每一版内容独立保留</p></div>
        <div class="library-inline"><el-button @click="openBank">加入题库</el-button><el-button @click="$router.push(`/question-stats/${question.id}?version=${selected.id}`)">跨问卷统计</el-button></div>
      </div>
      <div v-if="question.archived_at" class="warn-banner">此题目已归档，已有问卷不受影响。<el-button v-if="question.can_manage" link @click="archive(false)">恢复题目</el-button></div>
      <div class="library-two-column">
        <aside class="card"><div class="library-section-heading"><h2>版本历史</h2><span class="muted">{{ question.versions.length }} 版</span></div>
          <button v-for="version in question.versions" :key="version.id" class="version-row" :class="{ active: selected.id === version.id }" @click="selectedId = version.id">
            <strong>v{{ version.version_no }}</strong><el-tag v-if="question.default_version_id === version.id" size="small" style="margin-left: 8px">推荐</el-tag>
            <span class="muted">{{ version.change_note || '未填写修改说明' }}</span><span class="muted">{{ formatDate(version.created_at) }}</span>
            <span v-if="version.parent_version_id" class="muted">基于 {{ versionName(version.parent_version_id) }}</span>
            <span v-if="version.restored_from_version_id" class="muted">内容恢复自 {{ versionName(version.restored_from_version_id) }}</span>
            <span v-if="version.derived_from_version_id" class="muted">派生自另一个题目</span>
          </button>
        </aside>
        <section class="card">
          <div class="library-section-heading"><div class="library-inline"><span class="library-type">{{ TYPE_LABELS[selected.content.type] }}</span><strong>v{{ selected.version_no }}</strong></div>
            <div class="library-inline" v-if="question.can_manage"><el-button :disabled="!!question.archived_at" @click="openEdit">基于此版编辑</el-button><el-button :disabled="!!question.archived_at" @click="restore">恢复此版本</el-button></div>
            <el-button v-else @click="fork">派生为我的题目</el-button>
          </div>
          <div v-if="selected.content_completeness === 'snapshot_only'" class="warn-banner">从第一阶段历史快照导入。原始约束未被记录，不能据此推断；创建新版本时请补全约束。</div>
          <div class="library-preview"><h2>{{ selected.content.title }}</h2><ul v-if="selected.content.options?.length"><li v-for="option in selected.content.options" :key="option">{{ option }}</li></ul><p v-if="selected.content.type === 'number'">数值范围：{{ selected.content.num_min ?? '未设置或未知' }} 至 {{ selected.content.num_max ?? '未设置或未知' }}<span v-if="selected.content.integer_only"> · 仅整数</span></p><p v-if="selected.content.type === 'text'">字数：{{ selected.content.text_min_len ?? '未知' }} 至 {{ selected.content.text_max_len ?? '不限或未知' }}</p><p v-if="selected.content.type === 'multiple'">选择数量：{{ selected.content.min_select ?? '未知' }} 至 {{ selected.content.max_select ?? '不限或未知' }}</p></div>
          <p v-if="changes.length" class="library-note">相较父版本变更：{{ changes.join('、') }}</p>
          <p class="library-note">问卷绑定具体版本。修改题目或更新推荐版本，不会改变其他问卷。</p>
          <el-tabs v-model="tab" class="library-detail-tabs">
            <el-tab-pane label="使用情况" name="usages">
              <p class="muted">仅展示你有权查看的问卷，不公开其他用户的私有问卷。</p>
              <el-table :data="usages" empty-text="你的问卷尚未引用此题目"><el-table-column prop="title" label="问卷" /><el-table-column label="状态" width="100"><template #default="{ row }">{{ statusLabels[row.status] }}</template></el-table-column><el-table-column label="题目实例"><template #default="{ row }">{{ row.instances.map((item) => `${item.qid} · ${versionName(item.version_id)}`).join('，') }}</template></el-table-column><el-table-column width="90"><template #default="{ row }"><router-link :to="`/editor/${row.survey_id}`">查看问卷</router-link></template></el-table-column></el-table>
            </el-tab-pane>
            <el-tab-pane v-if="question.can_manage" label="共享管理" name="sharing">
              <p class="library-note">共享的是题目内容与使用权，不包含问卷答卷。接收者只能派生自己的题目，不能覆盖你的版本。</p>
              <el-form label-position="top"><div class="form-pair"><el-form-item label="接收者用户名"><el-input v-model="shareUsername" aria-label="接收者用户名" /></el-form-item><el-form-item label="允许派生"><el-switch v-model="allowFork" aria-label="允许派生" /></el-form-item></div>
                <el-form-item label="分享版本"><el-select v-model="shareVersions" multiple aria-label="分享版本" :disabled="allVersions" style="width: 100%"><el-option v-for="version in question.versions" :key="version.id" :label="`v${version.version_no}`" :value="version.id" /></el-select></el-form-item>
                <el-checkbox v-model="allVersions">公开给此用户全部现有和未来版本</el-checkbox><el-button type="primary" :loading="busy" @click="share">保存共享设置</el-button>
              </el-form>
              <el-table :data="question.shared_with" style="margin-top: 20px" empty-text="尚未分享"><el-table-column prop="username" label="用户" /><el-table-column label="版本范围"><template #default="{ row }">{{ row.all_versions ? '全部现有及未来版本' : row.version_ids.map(versionName).join('、') }}</template></el-table-column><el-table-column label="派生" width="70"><template #default="{ row }">{{ row.allow_fork ? '允许' : '禁止' }}</template></el-table-column><el-table-column width="80"><template #default="{ row }"><el-button link type="danger" :disabled="busy" @click="revoke(row)">撤销</el-button></template></el-table-column></el-table>
            </el-tab-pane>
          </el-tabs>
          <div v-if="question.can_manage" class="library-inline" style="margin-top: 25px"><el-button v-if="question.draft" @click="resumeDraft">继续编辑工作草稿</el-button><el-button v-if="!question.archived_at" link type="danger" @click="archive(true)">归档题目</el-button></div>
        </section>
      </div>
      <el-dialog v-model="editOpen" :title="`基于 ${versionName(parentId)} 创建新版本`" width="650px" :close-on-click-modal="false">
        <p class="library-note">原版本与已发布问卷会保持原样。可先保留工作草稿，确认后再创建正式版本。</p><QuestionContentForm v-model="editContent" /><el-input v-model="changeNote" aria-label="修改说明" placeholder="修改说明，方便以后回顾" maxlength="1000" />
        <template #footer><el-button :loading="busy" @click="saveDraft">保留工作草稿</el-button><el-button type="primary" :loading="busy" @click="saveVersion">保存新版本</el-button></template>
      </el-dialog>
      <el-dialog v-model="bankOpen" title="加入题库" width="450px"><p>将 v{{ selected.version_no }} 作为题库中的固定版本。</p><el-select v-model="bankId" aria-label="目标题库" placeholder="请选择题库" style="width: 100%"><el-option v-for="bank in banks" :key="bank.id" :label="bank.name" :value="bank.id" /></el-select><p v-if="!banks.length" class="muted">尚未创建题库，可前往<router-link to="/question-banks">题库管理</router-link>创建。</p><template #footer><el-button type="primary" :disabled="!bankId" :loading="busy" @click="addToBank">加入</el-button></template></el-dialog>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import QuestionContentForm from '../components/QuestionContentForm.vue'
import { TYPE_LABELS } from '../jump'
import { contentFields, errorMessage, makeContent, pickContent } from '../questionContent'

const route = useRoute(), router = useRouter()
const question = ref(null), selectedId = ref(''), usages = ref([]), loading = ref(false), error = ref(''), busy = ref(false), tab = ref('usages')
const editOpen = ref(false), editContent = ref(makeContent()), parentId = ref(''), changeNote = ref('')
const shareUsername = ref(''), shareVersions = ref([]), allVersions = ref(false), allowFork = ref(true)
const bankOpen = ref(false), banks = ref([]), bankId = ref('')
const statusLabels = { draft: '草稿', published: '已发布', closed: '已关闭' }
const fieldLabels = { type: '题型', title: '题干', options: '选项', min_select: '最少选择数', max_select: '最多选择数', text_min_len: '最少字数', text_max_len: '最多字数', num_min: '最小值', num_max: '最大值', integer_only: '整数限制' }
const selected = computed(() => question.value?.versions.find((version) => version.id === selectedId.value) || question.value?.versions[0])
const changes = computed(() => {
  const parent = question.value?.versions.find((version) => version.id === selected.value?.parent_version_id)
  return parent ? contentFields.filter((field) => JSON.stringify(parent.content[field]) !== JSON.stringify(selected.value.content[field])).map((field) => fieldLabels[field]) : []
})
watch(() => route.params.id, () => { selectedId.value = ''; question.value = null; void load() }, { immediate: true })
function versionName(versionId) { const version = question.value?.versions.find((item) => item.id === versionId); return version ? `v${version.version_no}` : '来源版本' }
function formatDate(value) { return new Date(value).toLocaleString('zh-CN') }
async function load() {
  loading.value = true; error.value = ''
  const seriesId = route.params.id
  try {
    const [detail, usage] = await Promise.all([api.get(`/questions/${seriesId}`), api.get(`/questions/${seriesId}/usages`)])
    if (seriesId !== route.params.id) return
    question.value = detail.data; usages.value = usage.data
    if (!detail.data.versions.some((version) => version.id === selectedId.value)) selectedId.value = detail.data.default_version_id
    shareVersions.value = [selectedId.value]
  } catch (failure) { error.value = errorMessage(failure) }
  finally { loading.value = false }
}
async function perform(action) {
  if (busy.value) return
  busy.value = true
  try { await action() } catch (failure) { if (failure !== 'cancel' && failure !== 'close') ElMessage.error(errorMessage(failure)) }
  finally { busy.value = false }
}
function openEdit() { parentId.value = selected.value.id; editContent.value = pickContent(selected.value.content); changeNote.value = ''; editOpen.value = true }
function resumeDraft() { parentId.value = question.value.draft.base_version_id; editContent.value = pickContent(question.value.draft.content); changeNote.value = question.value.draft.change_note || ''; editOpen.value = true }
function versionPayload() { return { content: editContent.value, parent_version_id: parentId.value, expected_revision: question.value.revision, change_note: changeNote.value } }
async function saveVersion() { await perform(async () => { const { data } = await api.post(`/questions/${question.value.id}/versions`, versionPayload()); selectedId.value = data.version.id; editOpen.value = false; await load(); ElMessage.success('新版本已保存，原问卷保持不变') }) }
async function saveDraft() { await perform(async () => { await api.put(`/questions/${question.value.id}/draft`, versionPayload()); editOpen.value = false; await load(); ElMessage.success('工作草稿已保留') }) }
async function restore() { await perform(async () => { await ElMessageBox.confirm(`将 v${selected.value.version_no} 的内容恢复为一个新版本，历史版本仍保留。`, '恢复历史内容'); const { data } = await api.post(`/questions/${question.value.id}/restore`, { source_version_id: selected.value.id, expected_revision: question.value.revision }); selectedId.value = data.version.id; await load(); ElMessage.success('恢复内容已保存为新版本') }) }
async function fork() { await perform(async () => { const { data } = await api.post(`/question-versions/${selected.value.id}/fork`); router.push(`/questions/${data.id}`); ElMessage.success('已派生为你的独立题目') }) }
async function share() { await perform(async () => { await api.post(`/questions/${question.value.id}/shares`, { username: shareUsername.value.trim(), version_ids: shareVersions.value, all_versions: allVersions.value, allow_fork: allowFork.value, expected_revision: question.value.revision }); await load(); ElMessage.success('共享设置已保存') }) }
async function revoke(grant) { await perform(async () => { await ElMessageBox.confirm('撤销后将阻止新增引用，已保存的问卷仍可使用原版本。', '撤销共享'); await api.delete(`/questions/${question.value.id}/shares/${grant.user_id}`, { params: { revision: question.value.revision } }); await load() }) }
async function archive(archived) { await perform(async () => { await api.patch(`/questions/${question.value.id}`, { revision: question.value.revision, archived }); await load() }) }
async function openBank() { try { banks.value = (await api.get('/question-banks', { params: { page_size: 100 } })).data.items; bankOpen.value = true } catch (failure) { ElMessage.error(errorMessage(failure)) } }
async function addToBank() { await perform(async () => { await api.post(`/question-banks/${bankId.value}/items`, { version_id: selected.value.id }); bankOpen.value = false; ElMessage.success('已加入题库，版本已固定') }) }
</script>
