<!--
  主 Agent 会话内的子 Agent 控制区。

  用途：展示主 Agent 已召唤的子任务目标、前后台模式、权限、状态和结果，
  并提供停止操作。用户不能通过此组件创建子 Agent；子 Agent 只能由主 Agent
  的运行时工具召唤。
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChevronDown, ChevronRight, UsersRound, X } from 'lucide-vue-next'

import { fetchChildAgents, stopChildAgent } from '@/api/agent'
import type { ChildAgentRecord } from '@/api/agent'

const props = defineProps<{
  sessionId: string
  open: boolean
}>()

const emit = defineEmits<{ close: [] }>()

const children = ref<ChildAgentRecord[]>([])
const error = ref('')
const expandedRunIds = ref<Set<string>>(new Set())
let timer: number | null = null

const activeChildren = computed(() => children.value.filter((child) => ['created', 'running'].includes(child.status)))

function isChildActive(child: ChildAgentRecord) {
  return ['created', 'running'].includes(child.status)
}

function isExpanded(child: ChildAgentRecord) {
  return expandedRunIds.value.has(child.run_id)
}

function toggleExpanded(child: ChildAgentRecord) {
  const next = new Set(expandedRunIds.value)
  if (next.has(child.run_id)) {
    next.delete(child.run_id)
  } else {
    next.add(child.run_id)
  }
  expandedRunIds.value = next
}

async function reload() {
  if (!props.sessionId) {
    children.value = []
    return
  }
  try {
    const response = await fetchChildAgents(props.sessionId)
    children.value = response.children
    error.value = ''
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '子 Agent 状态读取失败'
  }
}

async function stopChild(child: ChildAgentRecord) {
  try {
    await stopChildAgent(child.run_id)
    await reload()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '停止子 Agent 失败'
  }
}

function statusLabel(status: ChildAgentRecord['status']) {
  return {
    created: '已创建',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止',
  }[status]
}

function modeLabel(value: ChildAgentRecord['mode']) {
  return value === 'foreground' ? '前台' : '后台'
}

function accessModeLabel(value: ChildAgentRecord['access_mode']) {
  return {
    readonly: '只读',
    sandbox: '沙盒',
    full_access: '完整权限',
  }[value]
}

function shortRunId(runId: string) {
  return runId.length > 8 ? runId.slice(0, 8) : runId
}

function resultText(result: unknown) {
  if (result === undefined || result === null) return ''
  if (typeof result === 'string') return result
  try {
    return JSON.stringify(result, null, 2)
  } catch {
    return String(result)
  }
}

watch(() => props.sessionId, () => {
  void reload()
})

onMounted(() => {
  void reload()
  timer = window.setInterval(() => void reload(), 2000)
})

onBeforeUnmount(() => {
  if (timer !== null) window.clearInterval(timer)
})
</script>

<template>
  <aside class="child-agent-drawer" :class="{ open: props.open }" aria-label="子 Agent 任务">
    <header class="child-agent-header">
      <div class="child-agent-title">
        <UsersRound :size="16" />
        <span>子 Agent</span>
        <span class="child-agent-count">{{ activeChildren.length }} 个运行中</span>
      </div>
      <button class="child-agent-close" type="button" title="关闭子 Agent 侧栏" @click="emit('close')">
        <X :size="15" />
      </button>
    </header>

    <div class="child-agent-content">
      <div v-if="children.length" class="child-agent-tasks">
        <article v-for="child in children" :key="child.run_id" class="child-agent-task">
          <button
            class="child-agent-task-head"
            type="button"
            :aria-expanded="isExpanded(child)"
            @click="toggleExpanded(child)"
          >
            <span class="child-agent-task-title">
              <ChevronDown v-if="isExpanded(child)" :size="15" />
              <ChevronRight v-else :size="15" />
              <strong>{{ child.goal }}</strong>
            </span>
            <span class="child-agent-status" :data-status="child.status">{{ statusLabel(child.status) }}</span>
          </button>

          <div class="child-agent-task-meta">
            <span>ID {{ shortRunId(child.run_id) }}</span>
            <span>{{ modeLabel(child.mode) }}</span>
            <span>{{ accessModeLabel(child.access_mode) }}</span>
            <span>{{ child.allowed_tools.length }} 项工具</span>
          </div>

          <p v-if="!isExpanded(child) && child.summary" class="child-agent-summary is-collapsed">{{ child.summary }}</p>
          <p v-if="!isExpanded(child) && child.error" class="child-agent-error is-collapsed">{{ child.error }}</p>

          <div v-if="isExpanded(child)" class="child-agent-detail">
            <section class="child-agent-section">
              <h4>任务目标</h4>
              <p>{{ child.goal }}</p>
            </section>

            <section class="child-agent-section-grid" aria-label="子 Agent 运行信息">
              <div>
                <span>状态</span>
                <strong>{{ statusLabel(child.status) }}</strong>
              </div>
              <div>
                <span>模式</span>
                <strong>{{ modeLabel(child.mode) }}</strong>
              </div>
              <div>
                <span>沙盒权限</span>
                <strong>{{ accessModeLabel(child.access_mode) }}</strong>
              </div>
              <div>
                <span>工具数量</span>
                <strong>{{ child.allowed_tools.length }}</strong>
              </div>
            </section>

            <section v-if="child.allowed_tools.length" class="child-agent-section">
              <h4>工具范围</h4>
              <p class="child-agent-tools">{{ child.allowed_tools.join(', ') }}</p>
            </section>

            <section v-if="child.summary" class="child-agent-section">
              <h4>阶段摘要</h4>
              <p>{{ child.summary }}</p>
            </section>

            <section v-if="resultText(child.result)" class="child-agent-section">
              <h4>产出结果</h4>
              <pre>{{ resultText(child.result) }}</pre>
            </section>

            <section v-if="child.error" class="child-agent-section">
              <h4>错误信息</h4>
              <p class="child-agent-error">{{ child.error }}</p>
            </section>

            <div v-if="isChildActive(child)" class="child-agent-actions">
              <button type="button" @click.stop="stopChild(child)">停止</button>
            </div>
          </div>
        </article>
      </div>
      <p v-if="error" class="child-agent-error">{{ error }}</p>
      <p v-if="!children.length && !error" class="child-agent-empty">暂无子 Agent 任务</p>
    </div>
  </aside>
</template>

<style scoped>
.child-agent-drawer {
  flex: 0 0 0px;
  display: flex;
  width: min(400px, 38vw);
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid var(--color-border);
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
  transition: flex-basis 220ms cubic-bezier(0.4, 0, 0.2, 1);
}

.child-agent-drawer.open {
  flex-basis: min(400px, 38vw);
}

.child-agent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 46px;
  padding: 0 var(--space-12);
  border-bottom: 1px solid var(--color-border);
}

.child-agent-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-8);
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
  font-weight: 650;
}

.child-agent-close {
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

.child-agent-close:hover {
  background: var(--color-primary-softer);
  color: var(--color-text);
}

.child-agent-content {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: var(--space-12);
  overflow-x: hidden;
  overflow-y: auto;
  padding: var(--space-12);
}

.child-agent-count,
.child-agent-task-meta {
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.child-agent-task {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-8);
  padding: var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  transition:
    border-color 180ms ease,
    background-color 180ms ease;
}

.child-agent-task:hover {
  border-color: var(--color-border-strong);
  background: var(--color-surface-raised);
}

.child-agent-empty {
  margin: 0;
  padding: var(--space-8) 0;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.child-agent-task-head,
.child-agent-task-meta {
  display: flex;
  align-items: center;
  gap: var(--space-8);
}

.child-agent-summary,
.child-agent-error {
  margin: 0;
  line-height: 1.45;
}

.child-agent-tasks {
  display: grid;
  gap: var(--space-8);
}

.child-agent-task-head {
  justify-content: space-between;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.child-agent-task-head:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.child-agent-task-title {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: var(--space-6);
}

.child-agent-task-title strong {
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--color-text-primary);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.45;
}

.child-agent-task-title svg {
  flex: 0 0 auto;
  margin-top: 1px;
  color: var(--color-text-muted);
  transition: transform 180ms ease;
}

.child-agent-task-meta {
  min-width: 0;
  flex-wrap: wrap;
}

.child-agent-task-meta span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.child-agent-status {
  flex: 0 0 auto;
  font-size: calc(11px * var(--font-scale));
  font-weight: 600;
}

.child-agent-summary.is-collapsed,
.child-agent-error.is-collapsed {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
  overflow-wrap: anywhere;
}

.child-agent-detail {
  display: grid;
  gap: var(--space-8);
  padding-top: var(--space-8);
  border-top: 1px solid var(--color-border);
}

.child-agent-section,
.child-agent-section-grid {
  min-width: 0;
}

.child-agent-section {
  display: grid;
  gap: var(--space-4);
}

.child-agent-section h4 {
  margin: 0;
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
  font-weight: 600;
}

.child-agent-section p,
.child-agent-section pre {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.5;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.child-agent-section pre {
  max-height: 220px;
  overflow: auto;
  padding: var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  font-family: var(--font-mono);
}

.child-agent-section-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-8);
}

.child-agent-section-grid div {
  display: grid;
  min-width: 0;
  gap: 2px;
  padding: var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
}

.child-agent-section-grid span {
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
}

.child-agent-section-grid strong {
  min-width: 0;
  color: var(--color-text-primary);
  font-size: calc(12px * var(--font-scale));
  font-weight: 600;
  overflow-wrap: anywhere;
}

.child-agent-tools {
  max-height: 92px;
  overflow: auto;
}

.child-agent-actions {
  display: flex;
  justify-content: flex-end;
}

.child-agent-actions button {
  min-height: 28px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition:
    border-color 180ms ease,
    color 180ms ease,
    background-color 180ms ease;
}

.child-agent-actions button:hover {
  border-color: var(--color-danger);
  background: color-mix(in srgb, var(--color-danger) 12%, transparent);
  color: var(--color-danger);
}

.child-agent-status[data-status='completed'] { color: var(--color-success); }
.child-agent-status[data-status='failed'], .child-agent-error { color: var(--color-danger); }
.child-agent-status[data-status='running'] { color: var(--color-primary); }

@media (max-width: 640px) {
  .child-agent-drawer,
  .child-agent-drawer.open { width: min(88vw, 400px); flex-basis: min(88vw, 400px); }
  .child-agent-section-grid { grid-template-columns: 1fr; }
}
</style>
