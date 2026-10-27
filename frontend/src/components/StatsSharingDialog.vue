<template>
  <el-dialog :model-value="modelValue" title="单题聚合统计授权" width="650px" @update:model-value="emit('update:modelValue', $event)">
    <p class="library-note">授权后，对方可在跨问卷单题统计中看到汇总计数及数值分布，不能读取此问卷原始文本或填写者身份。题目共享本身不授予统计权限。</p>
    <div class="library-toolbar"><el-select v-model="versionId" aria-label="授权题目版本" placeholder="选择题目" style="width: 250px"><el-option v-for="question in questions" :key="question.qid" :label="question.title" :value="question.question_version_id" /></el-select><el-input v-model="username" aria-label="被授权用户名" placeholder="对方用户名" /><el-button @click="add">添加</el-button></div>
    <el-table :data="grants" empty-text="尚未开放跨用户聚合统计"><el-table-column label="题目"><template #default="{ row }">{{ questions.find((question) => question.question_version_id === row.question_version_id)?.title || '已绑定版本' }}</template></el-table-column><el-table-column prop="username" label="用户" /><el-table-column width="80"><template #default="{ $index }"><el-button link type="danger" @click="grants.splice($index, 1)">移除</el-button></template></el-table-column></el-table>
    <template #footer><el-button @click="emit('update:modelValue', false)">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存授权</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { errorMessage } from '../questionContent'

const props = defineProps({ modelValue: Boolean, survey: { type: Object, required: true } })
const emit = defineEmits(['update:modelValue', 'saved'])
const username = ref(''), versionId = ref(''), grants = ref([]), saving = ref(false)
const questions = computed(() => props.survey.questions.filter((question) => question.question_version_id))
watch(() => props.modelValue, (open) => { if (open) grants.value = (props.survey.question_stats_shares || []).map((grant) => ({ question_version_id: grant.question_version_id, username: grant.username })) })
function add() { if (!versionId.value || !username.value.trim()) { ElMessage.warning('请选择题目并填写用户名'); return } const item = { question_version_id: versionId.value, username: username.value.trim() }; if (!grants.value.some((grant) => grant.question_version_id === item.question_version_id && grant.username === item.username)) grants.value.push(item); username.value = '' }
async function save() { if (saving.value) return; saving.value = true; try { const { data } = await api.put(`/surveys/${props.survey.id}/question-stats-sharing`, { version: props.survey.version, grants: grants.value }); emit('saved', data); emit('update:modelValue', false); ElMessage.success('聚合统计授权已保存') } catch (failure) { ElMessage.error(errorMessage(failure)) } finally { saving.value = false } }
</script>
