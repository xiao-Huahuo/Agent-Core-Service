<script setup lang="ts">
import { Check, Circle, ListChecks, PanelRightClose } from 'lucide-vue-next'

import type { AgentTaskListItem } from '@/api/taskList'
import { useTaskListStore } from '@/stores/taskList'

const taskListStore = useTaskListStore()

function itemIcon(item: AgentTaskListItem) {
  return item.status === 'completed' ? Check : Circle
}
</script>

<template>
  <aside class="task-list-drawer" :class="{ open: taskListStore.sidebarOpen }">
    <header class="task-list-header">
      <div class="task-list-title">
        <ListChecks :size="16" />
        <span>{{ taskListStore.taskList?.title || 'Task list' }}</span>
      </div>
      <button class="task-list-close" type="button" title="Close task list" @click="taskListStore.setSidebarOpen(false)">
        <PanelRightClose :size="15" />
      </button>
    </header>

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
          <component :is="itemIcon(item)" class="task-item-icon" :size="15" />
          <div class="task-item-body">
            <p class="task-item-title">{{ item.title }}</p>
            <p v-if="item.completion_summary" class="task-item-summary">{{ item.completion_summary }}</p>
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
  </aside>
</template>

<style scoped>
.task-list-drawer {
  flex: 0 0 0px;
  display: flex;
  width: min(340px, 88vw);
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface-raised);
  transition: flex-basis 220ms cubic-bezier(0.4, 0, 0.2, 1);
}

.task-list-drawer.open {
  flex-basis: min(340px, 88vw);
}

.task-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 46px;
  padding: 0 var(--space-12);
  border-bottom: 1px solid var(--color-border);
}

.task-list-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-8);
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(13px * var(--font-scale));
  font-weight: 650;
}

.task-list-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-list-close {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
}

.task-list-close:hover {
  background: var(--color-primary-softer);
  color: var(--color-text);
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
  grid-template-columns: 18px minmax(0, 1fr);
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

.task-item-icon {
  margin-top: 2px;
  color: var(--color-primary);
}

.task-item.completed .task-item-icon {
  color: #22c55e;
}

.task-item-body {
  min-width: 0;
}

.task-item-title,
.task-item-summary,
.task-final-summary,
.task-list-empty {
  margin: 0;
  font-family: var(--font-ui);
}

.task-item-title {
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.45;
}

.task-item-summary {
  margin-top: var(--space-6);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  line-height: 1.5;
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
</style>
