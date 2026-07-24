<!--
  Todo sidebar panel.

  Usage:
  Renders inside the agent-col alongside AgentPanel. Shows a todo list with
  checkboxes, due dates, search, and hide-done toggle.
-->
<script setup lang="ts">
import { nextTick, ref } from 'vue'
import {
  Calendar,
  Circle,
  CircleCheck,
  Pencil,
  Plus,
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

    <div class="todo-list">
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
        <button
          class="todo-checkbox"
          type="button"
          :title="item.done ? '标记未完成' : '标记完成'"
          @click="todoStore.toggleTodo(item.id)"
        >
          <CircleCheck v-if="item.done" :size="14" class="todo-check-icon done" />
          <Circle v-else :size="14" class="todo-check-icon" />
        </button>

        <div class="todo-body">
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
          <div v-if="item.dueDate" class="todo-date-row">
            <Calendar :size="10" />
            <span
              class="todo-date"
              :class="{ expired: isDatetimeExpired(item.dueDate) && !item.done }"
            >
              {{ formatDatetime(item.dueDate) }}
            </span>
            <button
              class="todo-date-clear"
              type="button"
              title="清除日期"
              @click="todoStore.setDueDate(item.id, undefined)"
            >
              <X :size="10" />
            </button>
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
            type="date"
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

    <div class="todo-add-bar">
      <div class="todo-add-row">
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
        <input id="picker-new" class="todo-inline-picker" type="date" data-target="new" @change="onSharedPick" />
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
  border-bottom: 1px solid var(--color-border);
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

.todo-clear-done:disabled {
  opacity: 0.35;
  cursor: default;
}

.todo-toolbar {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6) var(--space-8);
  border-bottom: 1px solid var(--color-border);
}

.todo-search {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-2) var(--space-6);
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
  user-select: none;
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
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
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

.todo-body {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
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

.todo-date-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
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

.todo-date-row:hover .todo-date-clear {
  opacity: 1;
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
