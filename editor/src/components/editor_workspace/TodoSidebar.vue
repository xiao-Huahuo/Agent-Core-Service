<!--
  Todo sidebar panel.

  Usage:
  Renders inside the agent-col alongside AgentPanel. Shows a todo list with
  checkboxes, due dates, search, and hide-done toggle.
-->
<script setup lang="ts">
import { onBeforeUnmount, onMounted, nextTick, ref } from 'vue'
import {
  Calendar,
  Clock3,
  ChevronRight,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from 'lucide-vue-next'
import { useTodoStore } from '@/stores/todo'

const todoStore = useTodoStore()

const newTodoText = ref('')
const newTodoDatetime = ref('')
const editingId = ref('')
const editingText = ref('')
const editingDate = ref('')
const deletingId = ref('')
const timeTick = ref(0)
const automationFormOpen = ref(false)
const newAutomationText = ref('')
const newAutomationPrompt = ref('')
const newAutomationRunAt = ref('')
const newAutomationFrequency = ref<'none' | 'daily' | 'weekly' | 'monthly'>('daily')
const newAutomationAccessMode = ref<'readonly' | 'sandbox' | 'full_access'>('sandbox')
const automationSubmitting = ref(false)
const automationError = ref('')
const expandedAutomationId = ref('')

let tickTimer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  todoStore.refreshFromServer()
  tickTimer = setInterval(() => { timeTick.value = Date.now() }, 30000)
})

onBeforeUnmount(() => {
  if (tickTimer) clearInterval(tickTimer)
})

function triggerPicker(target: 'new' | string) {
  nextTick(() => {
    const el = document.querySelector<HTMLInputElement>('#picker-' + target)
    if (el) {
      el.value = ''
      el.showPicker()
    }
  })
}

function onSharedPick(e: Event) {
  const el = e.target as HTMLInputElement
  const val = el.value
  const id = el.dataset.target
  if (!val || !id) return
  if (id === 'new') {
    newTodoDatetime.value = val
  } else {
    todoStore.setDueDate(id, val)
  }
}

function handleAdd() {
  const trimmed = newTodoText.value.trim()
  if (!trimmed) return
  todoStore.addTodo(trimmed, newTodoDatetime.value || undefined)
  newTodoText.value = ''
  newTodoDatetime.value = ''
}

async function handleAddAutomation() {
  const text = newAutomationText.value.trim()
  const prompt = newAutomationPrompt.value.trim()
  if (!text || !prompt || !newAutomationRunAt.value || automationSubmitting.value) return
  const runAt = new Date(newAutomationRunAt.value)
  if (Number.isNaN(runAt.getTime())) return
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  automationSubmitting.value = true
  automationError.value = ''
  const created = await todoStore.addAutomation(
    text,
    prompt,
    runAt.toISOString(),
    timezone,
    { frequency: newAutomationFrequency.value, interval: 1 },
    newAutomationAccessMode.value,
  )
  automationSubmitting.value = false
  if (!created.success) {
    automationError.value = created.error || '自动化任务创建失败，请确认后端服务已重启并检查必填字段。'
    return
  }
  newAutomationText.value = ''
  newAutomationPrompt.value = ''
  newAutomationRunAt.value = ''
  automationError.value = ''
  automationFormOpen.value = false
}

function startEdit(id: string, text: string, dueDate?: string) {
  editingId.value = id
  editingText.value = text
  editingDate.value = dueDate || ''
  nextTick(() => {
    const el = document.querySelector<HTMLInputElement>(`.todo-edit-input[data-id="${id}"]`)
    el?.focus()
    el?.select()
  })
}

function commitEdit(id: string) {
  todoStore.editTodo(id, editingText.value)
  if (editingDate.value !== todoStore.todos.find((t) => t.id === id)?.dueDate) {
    todoStore.setDueDate(id, editingDate.value || undefined)
  }
  editingId.value = ''
  editingText.value = ''
  editingDate.value = ''
}

function cancelEdit() {
  editingId.value = ''
  editingText.value = ''
}

function removeWithAnimation(id: string) {
  if (deletingId.value) return
  deletingId.value = id
  setTimeout(() => {
    todoStore.removeTodo(id)
    deletingId.value = ''
  }, 350)
}

function formatDatetime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    if (iso.includes('T')) {
      const hh = String(d.getHours()).padStart(2, '0')
      const mm = String(d.getMinutes()).padStart(2, '0')
      return `${y}-${m}-${day} ${hh}:${mm}`
    }
    return `${y}-${m}-${day}`
  } catch {
    return iso
  }
}

function isDatetimeExpired(iso: string): boolean {
  if (!iso) return false
  return new Date(iso).getTime() < Date.now()
}

function getAutomationNextRun(todoId: string): string | undefined {
  return todoStore.automations.find((item) => item.todoId === todoId)?.nextRunAt
}

function toggleAutomationDetails(todoId: string) {
  expandedAutomationId.value = expandedAutomationId.value === todoId ? '' : todoId
}

function formatAutomationRecurrence(todoId: string): string {
  const recurrence = todoStore.automations.find((item) => item.todoId === todoId)?.recurrence
  if (!recurrence || recurrence.frequency === 'none') return '执行一次'
  const labels: Record<'daily' | 'weekly' | 'monthly', { singular: string; interval: string }> = {
    daily: { singular: '每天', interval: '天' },
    weekly: { singular: '每周', interval: '周' },
    monthly: { singular: '每月', interval: '个月' },
  }
  const label = labels[recurrence.frequency]
  return recurrence.interval > 1 ? `每 ${recurrence.interval} ${label.interval}` : label.singular
}

function formatAutomationAccessMode(todoId: string): string {
  const accessMode = todoStore.automations.find((item) => item.todoId === todoId)?.accessMode
  const labels: Record<'readonly' | 'sandbox' | 'full_access', string> = {
    readonly: '只读权限',
    sandbox: '沙盒权限',
    full_access: '完全访问',
  }
  return accessMode ? labels[accessMode] : '未知权限'
}

function getAutomationPrompt(todoId: string): string {
  return todoStore.automations.find((item) => item.todoId === todoId)?.prompt || '暂无描述'
}
</script>

<template>
  <div class="todo-sidebar">
    <div class="todo-header">
      <span class="todo-title">待办</span>
      <div class="todo-header-actions">
        <label class="todo-hide-done" title="隐藏已完成">
          <input type="checkbox" :checked="todoStore.hideDone" @change="todoStore.toggleHideDone()" />
          <span class="todo-toggle-track">
            <span class="todo-toggle-thumb" />
          </span>
          <span>隐藏已完成</span>
        </label>
        <button
          class="todo-clear-done"
          type="button"
          :class="{ spinning: todoStore.pending.has('add') }"
          title="从服务器刷新"
          :disabled="todoStore.pending.has('add')"
          @click="todoStore.refreshFromServer()"
        >
          <RefreshCw :size="12" />
        </button>
        <button
          class="todo-clear-done"
          type="button"
          title="清除已完成"
          :disabled="!todoStore.todos.some((t) => t.done)"
          @click="todoStore.clearDone()"
        >
          <Trash2 :size="12" />
        </button>
      </div>
    </div>

    <div class="todo-toolbar">
      <div class="todo-search">
        <Search :size="12" class="todo-search-icon" />
        <input
          v-model="todoStore.searchQuery"
          class="todo-search-input"
          type="text"
          placeholder="搜索待办…"
          spellcheck="false"
        />
        <button
          v-if="todoStore.searchQuery"
          class="todo-search-clear"
          type="button"
          @click="todoStore.searchQuery = ''"
        >
          <X :size="10" />
        </button>
      </div>
    </div>

    <div class="todo-list" :data-tick="timeTick">
      <div
        v-for="item in todoStore.filteredTodos"
        :key="item.id"
        class="todo-item"
        :class="{
          'todo-done': item.done,
          'todo-overdue': todoStore.overdueIds.has(item.id) && !item.done,
          'todo-deleting': deletingId === item.id,
        }"
      >
        <label class="creative-checkbox" :title="item.done ? '标记未完成' : '标记完成'">
          <input
            type="checkbox"
            :checked="item.done"
            @change="todoStore.toggleTodo(item.id)"
          />
          <div class="checkbox-box">
            <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
              <path
                class="box-path"
                d="M12,4 H32 A8,8 0 0 1 40,12 V32 A8,8 0 0 1 32,40 H12 A8,8 0 0 1 4,32 V12 A8,8 0 0 1 12,4 Z"
              />
              <path class="check-path" d="M14,23 L19,28 L30,15" />
            </svg>
          </div>
        </label>

        <div class="todo-body">
          <div class="todo-title-row">
            <div v-if="editingId === item.id" class="todo-edit-wrap">
              <input
                :data-id="item.id"
                v-model="editingText"
                class="todo-edit-input"
                type="text"
                spellcheck="false"
                @blur="commitEdit(item.id)"
                @keydown.enter.prevent="commitEdit(item.id)"
                @keydown.escape.prevent="cancelEdit"
              />
            </div>
            <span
              v-else
              class="todo-text"
              :title="item.text"
              @dblclick="startEdit(item.id, item.text, item.dueDate)"
            >
              {{ item.text }}
            </span>
            <button
              v-if="item.category === 'automation'"
              class="todo-automation-expand"
              type="button"
              :title="expandedAutomationId === item.id ? '收起自动化详情' : '展开自动化详情'"
              :aria-label="expandedAutomationId === item.id ? '收起自动化详情' : '展开自动化详情'"
              :aria-expanded="expandedAutomationId === item.id"
              @click.stop="toggleAutomationDetails(item.id)"
            >
              <ChevronRight :size="12" :class="{ expanded: expandedAutomationId === item.id }" />
            </button>
          </div>
          <div v-if="item.dueDate || item.category === 'automation'" class="todo-date-col">
            <Clock3 v-if="item.category === 'automation'" :size="10" />
            <Calendar v-else :size="10" />
            <span
              class="todo-date"
              :class="{ expired: isDatetimeExpired(item.dueDate || getAutomationNextRun(item.id) || '') && !item.done }"
            >
              {{ formatDatetime(item.dueDate || getAutomationNextRun(item.id) || '') }}
            </span>
            <button
              v-if="item.dueDate"
              class="todo-date-clear"
              type="button"
              title="清除日期"
              @click="todoStore.setDueDate(item.id, undefined)"
            >
              <X :size="10" />
            </button>
          </div>
          <div
            v-if="item.category === 'automation' && expandedAutomationId === item.id"
            class="todo-automation-details"
          >
            <div class="todo-automation-detail-row">
              <span>时间</span>
              <strong>{{ formatDatetime(getAutomationNextRun(item.id) || '') || '未设置' }}</strong>
            </div>
            <div class="todo-automation-detail-row">
              <span>权限</span>
              <strong>{{ formatAutomationAccessMode(item.id) }}</strong>
            </div>
            <div class="todo-automation-detail-row">
              <span>周期</span>
              <strong>{{ formatAutomationRecurrence(item.id) }}</strong>
            </div>
            <div class="todo-automation-detail-row todo-automation-detail-description">
              <span>描述</span>
              <p>{{ getAutomationPrompt(item.id) }}</p>
            </div>
          </div>
        </div>

        <div class="todo-actions">
          <button
            class="todo-action-btn"
            type="button"
            title="编辑"
            @click="startEdit(item.id, item.text, item.dueDate)"
          >
            <Pencil :size="11" />
          </button>
          <button
            class="todo-action-btn"
            type="button"
            :title="item.dueDate ? '修改日期' : '添加日期'"
            @click="triggerPicker(item.id)"
          >
            <Calendar :size="11" />
          </button>
          <input
            :id="'picker-' + item.id"
            class="todo-inline-picker"
            type="datetime-local"
            :data-target="item.id"
            @change="onSharedPick"
          />
          <button
            class="todo-action-btn todo-action-remove"
            type="button"
            title="删除"
            @click="removeWithAnimation(item.id)"
          >
            <X :size="11" />
          </button>
        </div>
      </div>

      <div v-if="todoStore.filteredTodos.length === 0" class="todo-empty">
        暂无待办
      </div>
    </div>

    <form v-if="automationFormOpen" class="todo-automation-form" @submit.prevent="handleAddAutomation">
      <div class="todo-automation-heading">
        <span>新建自动化任务</span>
        <button class="todo-automation-close" type="button" title="关闭" @click="automationFormOpen = false">
          <X :size="12" />
        </button>
      </div>
      <input v-model="newAutomationText" class="todo-automation-input" type="text" placeholder="自动化任务名称" />
      <textarea v-model="newAutomationPrompt" class="todo-automation-input todo-automation-prompt" rows="2" placeholder="到时间后让 Agent 做什么？" />
      <p v-if="automationError" class="todo-automation-error">{{ automationError }}</p>
      <div class="todo-automation-row">
        <input v-model="newAutomationRunAt" class="todo-automation-input" type="datetime-local" />
        <select v-model="newAutomationFrequency" class="todo-automation-select">
          <option value="none">执行一次</option>
          <option value="daily">每天</option>
          <option value="weekly">每周</option>
          <option value="monthly">每月</option>
        </select>
      </div>
      <div class="todo-automation-row">
        <select v-model="newAutomationAccessMode" class="todo-automation-select">
          <option value="sandbox">沙盒权限</option>
          <option value="readonly">只读权限</option>
          <option value="full_access">完全访问</option>
        </select>
        <button
          class="todo-add-btn todo-automation-submit"
          type="submit"
          :disabled="automationSubmitting || !newAutomationText.trim() || !newAutomationPrompt.trim() || !newAutomationRunAt"
        >
          <RefreshCw v-if="automationSubmitting" :size="14" class="todo-automation-spinner" />
          <Plus v-else :size="14" />
        </button>
      </div>
    </form>

    <div class="todo-add-bar">
      <div class="todo-add-row">
        <button
          class="todo-add-automation-btn"
          type="button"
          :class="{ active: automationFormOpen }"
          title="新建自动化任务"
          @click="automationFormOpen = !automationFormOpen"
        >
          <Clock3 :size="14" />
        </button>
        <input
          v-model="newTodoText"
          class="todo-add-input"
          type="text"
          placeholder="添加新待办…"
          spellcheck="false"
          @keydown.enter.prevent="handleAdd"
        />
        <button
          class="todo-add-cal-btn"
          type="button"
          :title="newTodoDatetime ? '修改时间' : '添加时间'"
          :class="{ hasDate: !!newTodoDatetime }"
          @click="triggerPicker('new')"
        >
          <Calendar :size="14" />
        </button>
        <input id="picker-new" class="todo-inline-picker" type="datetime-local" data-target="new" @change="onSharedPick" />
        <button
          class="todo-add-btn"
          :disabled="!newTodoText.trim()"
          type="button"
          title="添加"
          @click="handleAdd"
        >
          <Plus :size="14" />
        </button>
      </div>
      <div v-if="newTodoDatetime" class="todo-new-date-display">
        <Calendar :size="10" />
        <span>{{ formatDatetime(newTodoDatetime) }}</span>
        <button
          class="todo-date-clear"
          type="button"
          title="清除日期"
          @click="newTodoDatetime = ''"
        >
          <X :size="10" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.todo-sidebar {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: var(--color-bg-surface);
  border: 0;
  font-size: calc(12px * var(--font-scale));
  min-height: 0;
}

.todo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-6) var(--space-8);
}

.todo-title {
  font-weight: 650;
  font-size: calc(13px * var(--font-scale));
  color: var(--color-text);
}

.todo-header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.todo-clear-done {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.todo-clear-done:hover:not(:disabled) {
  background: color-mix(in srgb, var(--color-accent) 10%, transparent);
  color: var(--color-accent);
}

.todo-clear-done.active {
  color: var(--color-primary);
}

.todo-clear-done:disabled {
  opacity: 0.35;
  cursor: default;
}

.todo-clear-done.spinning :deep(svg) {
  animation: todo-refresh-spin 800ms linear infinite;
}

.todo-toolbar {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6) var(--space-8);
}

.todo-automation-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  margin: 0 var(--space-8);
  padding: var(--space-6) 0;
  border-top: 1px solid var(--color-border-soft);
}

.todo-automation-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--color-text-secondary);
  font-size: calc(11px * var(--font-scale));
  font-weight: 650;
}

.todo-automation-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.todo-automation-close:hover {
  color: var(--color-text);
}

.todo-automation-input,
.todo-automation-select {
  width: 100%;
  min-width: 0;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  outline: 0;
  background: var(--color-bg-input);
  color: var(--color-text);
  font: inherit;
  font-size: calc(11px * var(--font-scale));
}

.todo-automation-input:focus,
.todo-automation-select:focus {
  border-color: var(--color-primary);
}

.todo-automation-prompt {
  resize: vertical;
}

.todo-automation-error {
  margin: 0;
  color: var(--color-accent);
  font-size: calc(10px * var(--font-scale));
}

.todo-automation-spinner {
  animation: todo-refresh-spin 800ms linear infinite;
}

.todo-automation-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.todo-automation-submit {
  flex: 0 0 auto;
}

.todo-search {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-bg-input);
}

.todo-search-icon {
  flex: 0 0 auto;
  color: var(--color-text-muted);
}

.todo-search-input {
  flex: 1 1 auto;
  min-width: 0;
  padding: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
}

.todo-search-input::placeholder {
  color: var(--color-text-muted);
}

.todo-search-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: color var(--transition-fast);
}

.todo-search-clear:hover {
  color: var(--color-text);
}

.todo-hide-done {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: calc(11px * var(--font-scale));
  color: var(--color-text-muted);
  cursor: pointer;
  white-space: nowrap;
}

.todo-hide-done input[type="checkbox"] {
  display: none;
}

.todo-toggle-track {
  position: relative;
  display: inline-block;
  width: 28px;
  height: 16px;
  border-radius: 999px;
  background: var(--color-border);
  transition: background 200ms ease;
}

.todo-hide-done input:checked + .todo-toggle-track {
  background: var(--color-primary);
}

.todo-toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0,0,0,0.15);
  transition: transform 200ms ease;
}

.todo-hide-done input:checked + .todo-toggle-track .todo-toggle-thumb {
  transform: translateX(12px);
}

.todo-list {
  flex: 1 1 auto;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
  padding: var(--space-2) 0;
}

.todo-item {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) auto;
  align-items: start;
  gap: var(--space-6);
  padding: var(--space-6) var(--space-8);
  border-bottom: 1px solid var(--color-border-soft);
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
}

.todo-item:hover {
  background: color-mix(in srgb, var(--color-primary) 5%, transparent);
  box-shadow: inset 2px 0 0 color-mix(in srgb, var(--color-primary) 20%, transparent);
}

.todo-item:active {
  background: color-mix(in srgb, var(--color-primary) 9%, transparent);
}

.todo-done .todo-text {
  text-decoration: line-through;
  color: var(--color-text-muted);
}

.todo-done .todo-text::after {
  display: none;
}

.todo-deleting .todo-text {
  position: relative;
  color: var(--color-text-muted);
}

.todo-deleting .todo-text::after {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 100%;
  height: 2px;
  background: var(--color-text-muted);
  transform: scaleX(0);
  transform-origin: left center;
  animation: strike-through 320ms ease forwards;
}

@keyframes strike-through {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}

@keyframes todo-refresh-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.todo-overdue .todo-text {
  color: var(--color-accent);
}

.todo-overdue .todo-date {
  color: var(--color-accent);
  font-weight: 600;
}

.todo-checkbox {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  margin-top: 1px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  cursor: pointer;
  transition: color var(--transition-fast);
}

.todo-check-icon {
  color: var(--color-text-muted);
}

.todo-check-icon.done {
  color: var(--color-primary);
}

.todo-checkbox:hover .todo-check-icon {
  color: var(--color-primary);
}

.creative-checkbox {
  --color-idle: var(--color-text-muted);
  --color-hover: var(--color-text-secondary);
  --color-active: var(--color-primary);
  --color-active-glow: color-mix(in srgb, var(--color-primary) 20%, transparent);
  --size: 24px;
  flex: 0 0 auto;
  display: inline-block;
  width: var(--size);
  height: var(--size);
  cursor: pointer;
  position: relative;
  -webkit-tap-highlight-color: transparent;
  margin-top: 0;
}

.creative-checkbox input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.creative-checkbox .checkbox-box {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: transparent;
  transition:
    background 0.3s,
    transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.creative-checkbox .checkbox-box svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

.creative-checkbox .box-path {
  fill: none;
  stroke: var(--color-idle);
  stroke-width: 3.5px;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 144;
  stroke-dashoffset: 0;
  transition:
    stroke-dashoffset 0.4s cubic-bezier(0.4, 0, 0.2, 1),
    stroke 0.3s,
    stroke-width 0.3s;
}

.creative-checkbox .check-path {
  fill: none;
  stroke: white;
  stroke-width: 4px;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 25;
  stroke-dashoffset: 25;
  transition: stroke-dashoffset 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s;
}

.creative-checkbox:hover .box-path {
  stroke: var(--color-hover);
  stroke-width: 4px;
}

.creative-checkbox input:checked ~ .checkbox-box {
  background: var(--color-active);
  box-shadow: 0 0 0 6px var(--color-active-glow);
  animation: dynamic-bounce 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.creative-checkbox input:checked ~ .checkbox-box .box-path {
  stroke: var(--color-active);
  stroke-dashoffset: 144;
  stroke-width: 0px;
}

.creative-checkbox input:checked ~ .checkbox-box .check-path {
  stroke-dashoffset: 0;
}

@keyframes dynamic-bounce {
  0% { transform: scale(1); }
  30% { transform: scale(0.85) rotate(-4deg); }
  70% { transform: scale(1.12) rotate(4deg); }
  100% { transform: scale(1) rotate(0deg); }
}

.todo-body {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
}

.todo-title-row {
  display: flex;
  align-items: center;
  min-height: 24px;
}

.todo-automation-expand {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 18px;
  width: 18px;
  height: 18px;
  margin-right: var(--space-2);
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.todo-automation-expand:hover {
  background: color-mix(in srgb, var(--color-primary) 8%, transparent);
  color: var(--color-primary);
}

.todo-automation-expand svg {
  transition: transform var(--transition-fast);
}

.todo-automation-expand svg.expanded {
  transform: rotate(90deg);
}

.todo-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text);
  line-height: 1.4;
  cursor: default;
}

/* ── Date as separate column ── */
.todo-date-col {
  display: flex;
  align-items: center;
  width: fit-content;
  gap: var(--space-2);
  position: relative;
  margin-top: var(--space-2);
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
  white-space: nowrap;
}

.todo-date.expired {
  color: var(--color-accent);
  font-weight: 600;
}

.todo-edit-wrap {
  width: 100%;
}

.todo-edit-input {
  display: block;
  width: 100%;
  height: 30px;
  padding: 0 var(--space-4);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  outline: 0;
  background: var(--color-bg-input);
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  transition: box-shadow var(--transition-fast);
}

.todo-edit-input:focus {
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary) 20%, transparent);
}

.todo-inline-picker {
  opacity: 0.01;
  width: 1px;
  height: 28px;
  padding: 0;
  margin: 0;
  border: 0;
  overflow: hidden;
  flex: 0 0 1px;
  pointer-events: none;
}

.todo-date-clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--transition-fast), background var(--transition-fast), color var(--transition-fast);
}

.todo-date-col:hover .todo-date-clear {
  opacity: 1;
}

.todo-date-col .todo-date-clear {
  position: absolute;
  right: -10px;
  top: 50%;
  transform: translateY(-50%);
}

.todo-date-clear:hover {
  background: color-mix(in srgb, var(--color-text-muted) 12%, transparent);
  color: var(--color-text);
}

.todo-new-date-display {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1);
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
}

.todo-new-date-display .todo-date-clear {
  opacity: 1;
}


.todo-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 0 0 auto;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.todo-item:hover .todo-actions {
  opacity: 1;
}

.todo-deleting .todo-actions {
  opacity: 0;
  pointer-events: none;
}

.todo-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-surface);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast), background var(--transition-fast);
}

.todo-action-btn:hover {
  border-color: var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 6%, transparent);
  color: var(--color-primary);
}

.todo-add-cal-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-surface);
  color: var(--color-text-muted);
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color var(--transition-fast), color var(--transition-fast), background var(--transition-fast);
}

.todo-add-cal-btn:hover {
  border-color: var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 6%, transparent);
  color: var(--color-primary);
}

.todo-add-cal-btn.hasDate {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.todo-action-remove:hover {
  border-color: var(--color-accent);
  background: color-mix(in srgb, var(--color-accent) 6%, transparent);
  color: var(--color-accent);
}

.todo-empty {
  padding: var(--space-16) var(--space-8);
  text-align: center;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.todo-add-bar {
  flex: 0 0 auto;
  margin-top: auto;
  padding: var(--space-6) var(--space-8);
  border-top: 1px solid var(--color-border);
}

.todo-add-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.todo-automation-details {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding: var(--space-4) var(--space-6);
  border-left: 2px solid var(--color-primary-soft);
  color: var(--color-text-secondary);
  font-size: calc(10px * var(--font-scale));
}

.todo-automation-detail-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: var(--space-6);
  align-items: start;
}

.todo-automation-detail-row > span {
  color: var(--color-text-muted);
}

.todo-automation-detail-row strong {
  min-width: 0;
  color: var(--color-text-secondary);
  font-weight: 500;
}

.todo-automation-detail-description p {
  min-width: 0;
  margin: 0;
  color: var(--color-text-secondary);
  line-height: 1.45;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.todo-add-automation-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast), background var(--transition-fast);
}

.todo-add-automation-btn:hover,
.todo-add-automation-btn.active {
  border-color: var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 8%, transparent);
  color: var(--color-primary);
}

.todo-add-input {
  flex: 1 1 auto;
  min-width: 0;
  height: 28px;
  padding: 0 var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  outline: 0;
  background: var(--color-bg-input);
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  transition: border-color var(--transition-fast);
}

.todo-add-input:focus {
  border-color: var(--color-primary);
}

.todo-add-input::placeholder {
  color: var(--color-text-muted);
}

.todo-add-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--color-primary);
  border-radius: 999px;
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.todo-add-btn:hover:not(:disabled) {
  opacity: 0.85;
}

.todo-add-btn:disabled {
  opacity: 0.4;
  cursor: default;
}


</style>
