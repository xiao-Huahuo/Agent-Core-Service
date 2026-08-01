<!--
  子 Agent 生命周期事件条。

  用途：在主 Agent 对话区展示子 Agent 的 created/running/completed/failed/stopped
  等事件。事件条默认紧凑显示，用户可展开查看目标、权限、工具和结果。
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

interface ChildAgentEventChild {
  run_id: string
  goal: string
  mode: 'foreground' | 'background'
  status: 'created' | 'running' | 'completed' | 'failed' | 'stopped'
  access_mode: string
  allowed_tools: string[]
  result?: unknown
  summary?: string
  error?: string | null
}

const props = defineProps<{
  event?: Record<string, unknown>
}>()

const expanded = ref(false)

const child = computed(() => {
  const value = props.event?.child
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as ChildAgentEventChild
    : null
})

const eventName = computed(() => typeof props.event?.event_name === 'string' ? props.event.event_name : '')

const statusLabel = computed(() => {
  const status = child.value?.status ?? 'created'
  return {
    created: '已创建',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止',
  }[status]
})

const actionLabel = computed(() => {
  const goal = child.value?.goal || '未命名任务'
  if (eventName.value === 'child_agent.started') return `子 Agent 开始任务：${goal}`
  if (eventName.value === 'child_agent.completed') return `子 Agent 完成任务：${goal}`
  if (eventName.value === 'child_agent.failed') return `子 Agent 任务失败：${goal}`
  if (eventName.value === 'child_agent.stopped') return `子 Agent 已停止：${goal}`
  if (eventName.value === 'child_agent.stop_requested') return `子 Agent 收到停止请求：${goal}`
  return `子 Agent 已创建：${goal}`
})

const modeLabel = computed(() => child.value?.mode === 'foreground' ? '前台' : '后台')

const resultText = computed(() => {
  const result = child.value?.result
  if (result === undefined || result === null) return ''
  if (typeof result === 'string') return result
  try {
    return JSON.stringify(result, null, 2)
  } catch {
    return String(result)
  }
})

const shortRunId = computed(() => {
  const runId = child.value?.run_id ?? ''
  return runId.length > 8 ? runId.slice(0, 8) : runId
})
</script>

<template>
  <article v-if="child" class="child-agent-event" :data-status="child.status">
    <button
      class="child-agent-event-head"
      type="button"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <ChevronDown class="child-agent-chevron" :class="{ expanded }" :size="15" />
      <span class="child-agent-event-title">{{ actionLabel }}</span>
      <span class="child-agent-event-status">{{ statusLabel }}</span>
    </button>

    <div v-if="expanded" class="child-agent-event-detail">
      <div class="child-agent-event-grid">
        <div>
          <span>ID</span>
          <strong>{{ shortRunId }}</strong>
        </div>
        <div>
          <span>模式</span>
          <strong>{{ modeLabel }}</strong>
        </div>
        <div>
          <span>权限</span>
          <strong>{{ child.access_mode }}</strong>
        </div>
        <div>
          <span>工具</span>
          <strong>{{ child.allowed_tools.length }}</strong>
        </div>
      </div>
      <section class="child-agent-event-section">
        <span>任务目标</span>
        <p>{{ child.goal }}</p>
      </section>
      <section v-if="child.allowed_tools.length" class="child-agent-event-section">
        <span>工具范围</span>
        <p>{{ child.allowed_tools.join(', ') }}</p>
      </section>
      <section v-if="child.summary" class="child-agent-event-section">
        <span>阶段摘要</span>
        <p>{{ child.summary }}</p>
      </section>
      <section v-if="resultText" class="child-agent-event-section">
        <span>产出结果</span>
        <pre>{{ resultText }}</pre>
      </section>
      <section v-if="child.error" class="child-agent-event-section">
        <span>错误信息</span>
        <p class="is-error">{{ child.error }}</p>
      </section>
    </div>
  </article>
</template>

<style scoped>
.child-agent-event {
  align-self: stretch;
  width: min(100%, 760px);
  margin: var(--space-6) 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  animation: child-agent-event-in 180ms ease-out;
}

.child-agent-event-head {
  display: flex;
  width: 100%;
  min-width: 0;
  align-items: center;
  gap: var(--space-8);
  min-height: 34px;
  padding: var(--space-6) var(--space-10);
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.child-agent-event-head:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.child-agent-chevron {
  flex: 0 0 auto;
  color: var(--color-text-muted);
  transition: transform 180ms ease;
}

.child-agent-chevron.expanded {
  transform: rotate(180deg);
}

.child-agent-event-title {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.child-agent-event-status {
  flex: 0 0 auto;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  font-weight: 600;
}

.child-agent-event[data-status='running'] .child-agent-event-status {
  color: var(--color-primary);
}

.child-agent-event[data-status='completed'] .child-agent-event-status {
  color: var(--color-success);
}

.child-agent-event[data-status='failed'] .child-agent-event-status,
.child-agent-event[data-status='stopped'] .child-agent-event-status,
.is-error {
  color: var(--color-danger);
}

.child-agent-event-detail {
  display: grid;
  gap: var(--space-8);
  padding: 0 var(--space-10) var(--space-10);
}

.child-agent-event-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-6);
}

.child-agent-event-grid div {
  display: grid;
  min-width: 0;
  gap: 2px;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
}

.child-agent-event-grid span,
.child-agent-event-section span {
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
}

.child-agent-event-grid strong {
  min-width: 0;
  color: var(--color-text-primary);
  font-size: calc(11px * var(--font-scale));
  overflow-wrap: anywhere;
}

.child-agent-event-section {
  display: grid;
  min-width: 0;
  gap: var(--space-4);
}

.child-agent-event-section p,
.child-agent-event-section pre {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
  line-height: 1.5;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.child-agent-event-section pre {
  max-height: 240px;
  overflow: auto;
  padding: var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  font-family: var(--font-mono);
}

@keyframes child-agent-event-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 640px) {
  .child-agent-event-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
