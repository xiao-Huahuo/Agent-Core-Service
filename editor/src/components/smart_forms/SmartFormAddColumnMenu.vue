<!--
  Shared smart-form add-column menu.

  Usage:
  SmartFormsView and LiteratureReadingView mount this menu for every "新增字段"
  action so built-in fields, custom field types, descriptions, icons, disabled
  states, and menu styling stay identical.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import { SMART_COLUMN_TYPE_ICONS, smartColumnIcon, smartColumnTypeLabel } from '@/components/smart_forms/smartColumnPresentation'
import { BUILTIN_COLUMNS, createCustomColumn, type SmartColumn, type SmartColumnType } from '@/components/smart_forms/smartLiteratureTable'

const props = defineProps<{
  columns: SmartColumn[]
  isLiterature: boolean
}>()

const emit = defineEmits<{
  add: [column: SmartColumn]
}>()

const customTitle = ref('')
const customDescription = ref('')
const customTypes: Array<{ value: SmartColumnType; label: string }> = [
  { value: 'text', label: '文本' },
  { value: 'smart_text', label: '智能文本' },
  { value: 'tag', label: '标签' },
  { value: 'smart_tag', label: '智能标签' },
  { value: 'boolean', label: '布尔值' },
  { value: 'star', label: '星级' },
  { value: 'date', label: '日期' },
]
const builtinColumns = computed(() => BUILTIN_COLUMNS.filter((column) => column.id !== 'figures' || props.isLiterature))

function addCustom(type: SmartColumnType): void {
  emit('add', createCustomColumn(customTitle.value, type, customDescription.value))
  customTitle.value = ''
  customDescription.value = ''
}
</script>

<template>
  <div class="smart-form-add-column-menu ui-floating-submenu-surface" role="menu" @click.stop>
    <span class="section-title">内置字段</span>
    <button
      v-for="column in builtinColumns"
      :key="column.id"
      type="button"
      :disabled="columns.some((item) => item.id === column.id) || (!isLiterature && (column.type === 'smart_text' || column.type === 'smart_tag'))"
      @click="emit('add', { ...column })"
    >
      <IcIcon :name="smartColumnIcon(column)" :size="15" />
      <span>{{ column.title }}</span>
      <span class="type-pill">{{ smartColumnTypeLabel(column.type) }}</span>
    </button>
    <label class="menu-input"><span>自定义字段</span><input v-model="customTitle" type="text" placeholder="例如：备注" @click.stop /></label>
    <label class="menu-input"><span>辅助描述</span><input v-model="customDescription" type="text" placeholder="例如：提取作者明确陈述的局限" @click.stop /></label>
    <span class="section-title">字段类型</span>
    <button
      v-for="type in customTypes"
      :key="type.value"
      type="button"
      :disabled="!isLiterature && (type.value === 'smart_text' || type.value === 'smart_tag')"
      @click="addCustom(type.value)"
    >
      <IcIcon :name="SMART_COLUMN_TYPE_ICONS[type.value]" :size="15" />
      <span>{{ type.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.smart-form-add-column-menu { display: grid; width: 300px; max-height: min(620px, calc(100vh - 24px)); padding: var(--space-6); overflow-x: hidden; overflow-y: auto; color: var(--color-text-secondary); }
.smart-form-add-column-menu button { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: center; gap: var(--space-10); width: 100%; min-height: 30px; padding: 0 var(--space-8); border: 0; border-radius: var(--radius-xs); background: transparent; color: inherit; font: inherit; font-size: calc(13px * var(--font-scale)); text-align: left; }
.smart-form-add-column-menu button:hover:not(:disabled) { background: var(--color-selection-blue-soft); color: var(--color-text); }.smart-form-add-column-menu button:disabled { color: var(--color-text-tertiary); opacity: .55; }
.section-title { display: block; padding: 4px var(--space-8); color: var(--color-text-muted); font-size: calc(11px * var(--font-scale)); }
.menu-input { display: grid; gap: 4px; padding: 4px var(--space-8) var(--space-6); color: var(--color-text-muted); font-size: calc(11px * var(--font-scale)); }.menu-input input { width: 100%; height: 28px; box-sizing: border-box; padding: 0 var(--space-8); border: 0; border-radius: 999px; outline: 0; background: var(--color-canvas); color: var(--color-text); font: inherit; }.menu-input input:focus { box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary) 32%, transparent); }
.type-pill { justify-self: end; height: 17px; padding: 0 6px; border-radius: 999px; background: color-mix(in srgb, var(--color-primary) 30%, transparent); color: var(--color-tag-pill-text); font-size: calc(9px * var(--font-scale)); font-weight: 600; line-height: 17px; white-space: nowrap; }
</style>
