<template>
  <el-form label-position="top" class="question-content-form" :disabled="disabled">
    <el-form-item label="题型">
      <el-select :model-value="modelValue.type" aria-label="题型" @update:model-value="changeType">
        <el-option v-for="(label, type) in TYPE_LABELS" :key="type" :label="label" :value="type" />
      </el-select>
    </el-form-item>
    <el-form-item label="题目内容">
      <el-input :model-value="modelValue.title" aria-label="题目内容" maxlength="1000" placeholder="输入希望了解的问题" @update:model-value="update('title', $event)" />
    </el-form-item>
    <template v-if="['single', 'multiple'].includes(modelValue.type)">
      <el-form-item label="选项">
        <div class="form-option-list">
          <div v-for="(option, index) in modelValue.options" :key="index" class="form-option-row">
            <el-input :model-value="option" :aria-label="`选项 ${index + 1}`" @update:model-value="setOption(index, $event)" />
            <el-button :aria-label="`删除选项 ${index + 1}`" @click="update('options', modelValue.options.filter((_, optionIndex) => optionIndex !== index))">删除</el-button>
          </div>
          <el-button @click="update('options', [...modelValue.options, `选项 ${modelValue.options.length + 1}`])">添加选项</el-button>
        </div>
      </el-form-item>
      <div v-if="modelValue.type === 'multiple'" class="form-pair">
        <el-form-item label="至少选择"><el-input-number :model-value="modelValue.min_select" :min="0" aria-label="至少选择" @update:model-value="update('min_select', $event ?? 0)" /></el-form-item>
        <el-form-item label="最多选择 留空不限"><el-input-number :model-value="modelValue.max_select" :min="0" :value-on-clear="null" aria-label="最多选择" @update:model-value="update('max_select', $event ?? null)" /></el-form-item>
      </div>
    </template>
    <div v-if="modelValue.type === 'text'" class="form-pair">
      <el-form-item label="最少字数"><el-input-number :model-value="modelValue.text_min_len" :min="0" aria-label="最少字数" @update:model-value="update('text_min_len', $event ?? 0)" /></el-form-item>
      <el-form-item label="最多字数 留空不限"><el-input-number :model-value="modelValue.text_max_len" :min="0" :value-on-clear="null" aria-label="最多字数" @update:model-value="update('text_max_len', $event ?? null)" /></el-form-item>
    </div>
    <template v-if="modelValue.type === 'number'">
      <div class="form-pair">
        <el-form-item label="最小值 留空不限"><el-input-number :model-value="modelValue.num_min" :value-on-clear="null" aria-label="最小值" @update:model-value="update('num_min', $event ?? null)" /></el-form-item>
        <el-form-item label="最大值 留空不限"><el-input-number :model-value="modelValue.num_max" :value-on-clear="null" aria-label="最大值" @update:model-value="update('num_max', $event ?? null)" /></el-form-item>
      </div>
      <el-form-item label="仅允许整数"><el-switch :model-value="modelValue.integer_only" aria-label="仅允许整数" @update:model-value="update('integer_only', $event)" /></el-form-item>
    </template>
  </el-form>
</template>

<script setup>
import { TYPE_LABELS } from '../jump'
import { makeContent } from '../questionContent'

const props = defineProps({ modelValue: { type: Object, required: true }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
function update(field, value) { emit('update:modelValue', { ...props.modelValue, [field]: value }) }
function setOption(index, value) { const options = [...props.modelValue.options]; options[index] = value; update('options', options) }
function changeType(type) { emit('update:modelValue', { ...makeContent(type), title: props.modelValue.title }) }
</script>
