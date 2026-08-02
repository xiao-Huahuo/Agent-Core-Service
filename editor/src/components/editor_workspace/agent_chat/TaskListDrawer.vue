<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown, ChevronRight, X } from 'lucide-vue-next'

import type { AgentTaskListItem } from '@/api/taskList'
import { useTaskListStore } from '@/stores/taskList'

const taskListStore = useTaskListStore()
const emit = defineEmits<{ close: [] }>()
const expandedIds = ref<Set<string>>(new Set())
const collapsed = ref(false)

function toggleExpand(id: string) {
  const next = new Set(expandedIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  expandedIds.value = next
}
</script>

<template>
  <aside class="task-list-drawer" :class="{ collapsed }">
    <div class="task-list-head">
      <p class="task-list-title">{{ taskListStore.taskList?.title || 'Task list' }}</p>
      <div class="task-list-head-actions">
        <button
          class="task-list-toggle"
          type="button"
          :title="collapsed ? '展开任务列表' : '收起任务列表'"
          :aria-expanded="!collapsed"
          @click="collapsed = !collapsed"
        >
          <ChevronDown class="task-list-toggle-chevron" :class="{ open: !collapsed }" :size="14" />
        </button>
        <button class="task-list-close" type="button" title="关闭任务列表" @click="emit('close')">
          <X :size="14" />
        </button>
      </div>
    </div>

    <Transition name="task-list-collapse">
    <div v-show="!collapsed" class="task-list-body">
    <div v-if="taskListStore.taskList" class="task-list-content">
      <div class="task-list-status">
        <span :class="['status-dot', taskListStore.taskList.status]"></span>
        <span>{{ taskListStore.taskList.status }}</span>
        <strong>{{ taskListStore.completedCount }}/{{ taskListStore.taskList.items.length }}</strong>
      </div>

      <div class="task-items">
        <article
          v-for="item in taskListStore.taskList.items"
          :key="item.id"
          class="task-item"
          :class="{ current: item.id === taskListStore.taskList.current_item_id, completed: item.status === 'completed' }"
        >
          <div class="checkbox-wrapper-12">
            <div class="cbx">
              <input :checked="item.status === 'completed'" type="checkbox" :id="'cbx-' + item.id" />
              <label :for="'cbx-' + item.id"></label>
              <svg fill="none" viewBox="0 0 15 14" height="14" width="15">
                <path d="M2 8.36364L6.23077 12L13 2"></path>
              </svg>
            </div>
            <svg version="1.1" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <filter id="goo">
                  <feGaussianBlur result="blur" stdDeviation="4" in="SourceGraphic"></feGaussianBlur>
                  <feColorMatrix result="goo" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -7" mode="matrix" in="blur"></feColorMatrix>
                  <feBlend in2="goo" in="SourceGraphic"></feBlend>
                </filter>
              </defs>
            </svg>
          </div>
          <div class="task-item-body">
            <div class="task-item-title-row">
              <p class="task-item-title">{{ item.title }}</p>
              <button
                v-if="item.completion_summary"
                class="task-item-expand-btn"
                type="button"
                :title="expandedIds.has(item.id) ? '收起摘要' : '展开摘要'"
                @click="toggleExpand(item.id)"
              >
                <ChevronDown v-if="expandedIds.has(item.id)" :size="14" />
                <ChevronRight v-else :size="14" />
              </button>
            </div>
            <div v-if="item.completion_summary" class="task-item-summary-wrap" :class="{ expanded: expandedIds.has(item.id) }">
              <p class="task-item-summary">{{ item.completion_summary }}</p>
            </div>
          </div>
        </article>
      </div>

      <p v-if="taskListStore.taskList.final_summary" class="task-final-summary">
        {{ taskListStore.taskList.final_summary }}
      </p>
    </div>

    <div v-else class="task-list-empty">
      No task list
    </div>
    </div>
    </Transition>
  </aside>
</template>

<style scoped>
/* 作为融合侧边栏卡片的上分区:无边框、无独立背景,宽度与展开由外层卡片容器控制。
   高度链路:section(flex:0 0 auto + max-height 340) → drawer(flex:1 填满 section)
   → body(flex:1 + min-height:0) → content(overflow-y:auto),确保超高时内部滚动不截断 */
.task-list-drawer {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

/* 收缩后只剩标题行,需要底部留白形成规整的单行,避免塌成胶囊 */
.task-list-drawer.collapsed .task-list-head {
  padding-bottom: var(--space-12);
}

.task-list-head {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  padding: var(--space-12) var(--space-12) 0;
}

.task-list-title {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
  font-weight: 650;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-list-head-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 2px;
}

.task-list-toggle,
.task-list-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.task-list-toggle:hover,
.task-list-close:hover {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.task-list-toggle-chevron {
  transition: transform 180ms ease;
}

.task-list-toggle-chevron.open {
  transform: rotate(180deg);
}

.task-list-body {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

.task-list-collapse-enter-active,
.task-list-collapse-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.task-list-collapse-enter-from,
.task-list-collapse-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.task-list-content {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-10);
  overflow-y: auto;
  padding: var(--space-12);
}

.task-list-status {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
}

.task-list-status strong {
  margin-left: auto;
  color: var(--color-text);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--color-primary);
}

.status-dot.completed {
  background: #22c55e;
}

.task-items {
  display: grid;
  gap: var(--space-8);
}

.task-item {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: var(--space-8);
  padding: var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.task-item.current {
  border-color: color-mix(in srgb, var(--color-primary) 42%, var(--color-border));
  background: var(--color-primary-softer);
}

.task-item.completed {
  color: var(--color-text-muted);
}

.task-item-body {
  min-width: 0;
}

.task-item-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.task-item-title {
  flex: 1;
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.45;
}

.task-item-expand-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  margin-top: 1px;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.task-item-expand-btn:hover {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.task-item-summary-wrap {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 280ms ease;
}

.task-item-summary-wrap.expanded {
  grid-template-rows: 1fr;
}

.task-item-summary {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
  line-height: 1.5;
  padding-top: 0;
}

.task-item-summary-wrap.expanded .task-item-summary {
  padding-top: var(--space-6);
}

.task-final-summary,
.task-list-empty {
  margin: 0;
  font-family: var(--font-ui);
}

.task-final-summary {
  padding: var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-size: calc(11px * var(--font-scale));
  line-height: 1.5;
}

.task-list-empty {
  padding: var(--space-16);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.checkbox-wrapper-12 {
  position: relative;
  margin-top: 3px;
}

.checkbox-wrapper-12 > svg {
  position: absolute;
  top: -130%;
  left: -170%;
  width: 110px;
  pointer-events: none;
}

.checkbox-wrapper-12 * {
  box-sizing: border-box;
}

.checkbox-wrapper-12 input[type="checkbox"] {
  -webkit-appearance: none;
  -moz-appearance: none;
  appearance: none;
  -webkit-tap-highlight-color: transparent;
  pointer-events: none;
  margin: 0;
}

.checkbox-wrapper-12 input[type="checkbox"]:focus {
  outline: 0;
}

.checkbox-wrapper-12 .cbx {
  width: 16px;
  height: 16px;
}

.checkbox-wrapper-12 .cbx input {
  position: absolute;
  top: 0;
  left: 0;
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-border-strong);
  border-radius: 50%;
  background: transparent;
}

.checkbox-wrapper-12 .cbx label {
  width: 16px;
  height: 16px;
  background: none;
  border-radius: 50%;
  position: absolute;
  top: 0;
  left: 0;
  transform: trasnlate3d(0, 0, 0);
  pointer-events: none;
}

.checkbox-wrapper-12 .cbx svg {
  position: absolute;
  top: 2px;
  left: 2px;
  z-index: 1;
  pointer-events: none;
  width: 12px;
  height: 11px;
}

.checkbox-wrapper-12 .cbx svg path {
  stroke: #fff;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 15;
  stroke-dashoffset: 15;
  transition: stroke-dashoffset 0.3s ease;
  transition-delay: 0.2s;
}

.checkbox-wrapper-12 .cbx input:checked + label {
  animation: splash-12 0.6s ease forwards;
}

.checkbox-wrapper-12 .cbx input:checked + label + svg path {
  stroke-dashoffset: 0;
}

@keyframes splash-12 {
  40% {
    background: var(--color-primary);
    box-shadow:
      0 -18px 0 -8px var(--color-primary),
      16px -8px 0 -8px var(--color-primary),
      16px 8px 0 -8px var(--color-primary),
      0 18px 0 -8px var(--color-primary),
      -16px 8px 0 -8px var(--color-primary),
      -16px -8px 0 -8px var(--color-primary);
  }
  100% {
    background: var(--color-primary);
    box-shadow:
      0 -36px 0 -10px transparent,
      32px -16px 0 -10px transparent,
      32px 16px 0 -10px transparent,
      0 36px 0 -10px transparent,
      -32px 16px 0 -10px transparent,
      -32px -16px 0 -10px transparent;
  }
}

.task-item.completed .checkbox-wrapper-12 .cbx input {
  border-color: var(--color-primary);
  background: var(--color-primary);
}
</style>
