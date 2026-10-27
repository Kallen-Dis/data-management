<template>
  <div class="library-page">
    <div class="library-header"><div><p class="library-eyebrow">QUESTION LIBRARY</p><h1 class="page-title">让好问题重复发挥价值</h1><p class="muted">保存、分享与管理题目，每个正式版本都独立保留。</p></div><button class="btn-primary" @click="openCreate">新建题目</button></div>
    <div class="library-toolbar card">
      <el-radio-group v-model="scope" @change="resetLoad"><el-radio-button value="mine">我的题目</el-radio-button><el-radio-button value="shared">分享给我</el-radio-button></el-radio-group>
      <el-input v-model="search" placeholder="搜索题目名称" aria-label="搜索题目名称" clearable @keyup.enter="resetLoad" @clear="resetLoad" />
      <el-checkbox v-if="scope === 'mine'" v-model="archived" @change="resetLoad">查看已归档</el-checkbox>
      <el-button @click="resetLoad">搜索</el-button>
    </div>
    <div v-if="error" class="error-banner">{{ error }} <button class="btn-ghost" @click="load">重试</button></div>
    <div v-loading="loading" class="library-grid">
      <article v-for="question in questions" :key="question.id" class="card library-question-card">
        <div class="library-inline"><span class="library-type">{{ TYPE_LABELS[defaultVersion(question)?.content?.type] }}</span><span class="muted">{{ question.versions.length }} 个版本</span></div>
        <router-link class="library-question-title" :to="`/questions/${question.id}`">{{ question.name }}</router-link>
        <p class="muted">{{ scope === 'mine' ? '由我管理' : `来自 ${question.owner_username}` }} · 推荐 v{{ defaultVersion(question)?.version_no }}</p>
        <div class="library-tags"><el-tag v-for="tag in question.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag></div>
        <div class="library-card-footer"><router-link :to="`/questions/${question.id}`">版本与使用情况</router-link><router-link :to="`/question-stats/${question.id}`">跨问卷统计 →</router-link></div>
      </article>
    </div>
    <el-empty v-if="!loading && !error && !questions.length" :description="scope === 'shared' ? '还没有分享给你的题目' : '从一道常用题目开始，也可以在问卷编辑器中保存题目'" />
    <el-pagination v-if="total > 20" v-model:current-page="page" :page-size="20" :total="total" layout="total, prev, pager, next" @current-change="load" />
    <el-dialog v-model="createOpen" title="创建可复用题目" width="620px" :close-on-click-modal="false">
      <QuestionContentForm v-model="content" />
      <el-form label-position="top"><el-form-item label="标签 用逗号分隔"><el-input v-model="tags" aria-label="题目标签" placeholder="例如：基本信息，课程反馈" /></el-form-item></el-form>
      <p class="muted">保存为 v1 后，后续修改将创建新版本。</p>
      <template #footer><el-button @click="createOpen = false">取消</el-button><el-button type="primary" :loading="creating" @click="create">保存题目</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import QuestionContentForm from '../components/QuestionContentForm.vue'
import { TYPE_LABELS } from '../jump'
import { errorMessage, makeContent } from '../questionContent'

const router = useRouter()
const scope = ref('mine'), search = ref(''), archived = ref(false), questions = ref([]), total = ref(0), page = ref(1)
const loading = ref(false), error = ref(''), createOpen = ref(false), creating = ref(false), content = ref(makeContent()), tags = ref('')
let requestSequence = 0
onMounted(load)
function defaultVersion(question) { return question.versions.find((version) => version.id === question.default_version_id) || question.versions[0] }
function openCreate() { content.value = makeContent(); tags.value = ''; createOpen.value = true }
async function resetLoad() { page.value = 1; await load() }
async function load() {
  const sequence = ++requestSequence
  loading.value = true; error.value = ''
  try {
    const { data } = await api.get('/questions', { params: { scope: scope.value, search: search.value, archived: scope.value === 'mine' && archived.value, page: page.value } })
    if (sequence === requestSequence) { questions.value = data.items; total.value = data.total }
  } catch (failure) { if (sequence === requestSequence) error.value = errorMessage(failure) }
  finally { if (sequence === requestSequence) loading.value = false }
}
async function create() {
  if (creating.value) return
  creating.value = true
  try {
    const { data } = await api.post('/questions', { content: content.value, tags: tags.value.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean) })
    createOpen.value = false; ElMessage.success('题目 v1 已保存'); router.push(`/questions/${data.id}`)
  } catch (failure) { ElMessage.error(errorMessage(failure)) }
  finally { creating.value = false }
}
</script>
