<!--
  思考过程内联展示 — DeepSeek 风格。
  无边框、无底色、无节点标签,每条思考作为悬空 "- " 条目。
  工具调用显示简要摘要,不展开参数/返回详情。
-->

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  traces: { type: Array, default: () => [] },
  isStreaming: { type: Boolean, default: false },
  defaultExpanded: { type: Boolean, default: false },
})

const emit = defineEmits(['collapse'])

const isExpanded = ref(props.defaultExpanded)

function handleToggle(event) {
  const open = event.target.open
  isExpanded.value = open
  if (!open) {
    emit('collapse')
  }
}

/** 需要隐藏的 trace 事件: 工具调用开始只显示结束结果 */
const SKIP_EVENTS = new Set(['tool_call_start'])

/** 工具名兜底展示名；后端 human_readable/display_name 优先。 */
const FALLBACK_DISPLAY = {
  get_long_term_memory: '检索记忆',
  get_knowledge_context: '检索知识',
}

function toolSummary(trace) {
  const displayName = trace.display_name || FALLBACK_DISPLAY[trace.tool_name] || trace.tool_name || '调用工具'
  if (trace.result_count != null) {
    return trace.human_readable || `${displayName}：${trace.result_count} 条结果`
  }
  return trace.human_readable || displayName
}

/** 筛选并格式化条目 */
function entryText(trace) {
  if (trace.event === 'tool_call_end') {
    return toolSummary(trace)
  }
  return trace.human_readable || trace.event || ''
}

const entries = computed(() => {
  return props.traces
    .filter(t => {
      const isChatVisible = t.chat_visible === true || t.event === 'tool_call_end'
      return isChatVisible && !SKIP_EVENTS.has(t.event) && (t.human_readable || t.event === 'tool_call_end')
    })
    .map(t => ({
      key: `${t.node}-${t.event}-${t.tool_name || ''}`,
      text: entryText(t),
      isTool: t.event === 'tool_call_end',
    }))
})
</script>

<template>
  <details v-if="entries.length > 0" class="thinking-inline" :open="isExpanded" @toggle="handleToggle">
    <summary class="toggle-bar">
      <span class="bar-chevron" :class="{ expanded: isExpanded }">></span>
      <span v-if="!isExpanded && isStreaming" class="bar-label">思考中...</span>
      <span v-else-if="!isExpanded && !isStreaming" class="bar-label">思考完成</span>
      <span v-else class="bar-label">思考过程</span>
    </summary>

    <!-- 展开: 悬空条目列表 -->
    <Transition name="inline-list">
      <div v-if="isExpanded" class="entry-list">
        <p
          v-for="(entry, idx) in entries"
          :key="entry.key"
          class="entry-line"
          :class="{ 'is-tool': entry.isTool, 'is-new': idx === entries.length - 1 && entries.length > 1 && isStreaming }"
        >
          <span class="entry-bullet">-</span>
          <span class="entry-text">{{ entry.text }}</span>
        </p>
      </div>
    </Transition>
  </details>
</template>

<style scoped>
/* ========== 根容器 ========== */
.thinking-inline {
  margin-bottom: var(--space-8);
}

.thinking-inline > summary {
  list-style: none;
}

.thinking-inline > summary::-webkit-details-marker {
  display: none;
}

/* ========== 折叠栏 ========== */
.toggle-bar {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: fit-content;
  min-height: 24px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(148, 163, 184, 0.06);
  color: #8a93a3;
  cursor: pointer;
  user-select: none;
  padding: var(--space-4) var(--space-8);
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.toggle-bar:hover {
  border-color: rgba(148, 163, 184, 0.34);
  background: rgba(148, 163, 184, 0.1);
  color: #a3adbd;
}

.bar-chevron {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: currentColor;
  flex-shrink: 0;
  transition: transform 0.25s ease;
  display: inline-block;
}

.bar-chevron.expanded {
  transform: rotate(90deg);
}

.bar-label {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: currentColor;
  opacity: 0.9;
  transition: opacity var(--transition-fast);
}

.toggle-bar:hover .bar-label {
  opacity: 1;
}

/* ========== 条目列表过渡 ========== */
.inline-list-enter-active {
  transition: max-height 0.35s ease, opacity 0.3s ease;
  overflow: hidden;
}

.inline-list-leave-active {
  transition: max-height 0.25s ease, opacity 0.2s ease;
  overflow: hidden;
}

.inline-list-enter-from,
.inline-list-leave-to {
  max-height: 0;
  opacity: 0;
}

.inline-list-enter-to,
.inline-list-leave-from {
  max-height: 2000px;
  opacity: 1;
}

/* ========== 条目列表 ========== */
.entry-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-left: var(--space-12);
}

.entry-line {
  display: flex;
  gap: var(--space-6);
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}

.entry-bullet {
  flex-shrink: 0;
  color: var(--color-text-secondary);
  opacity: 0.6;
}

.entry-text {
  color: var(--color-text-secondary);
  opacity: 0.85;
}

.entry-line.is-tool .entry-text {
  color: var(--color-blue);
  opacity: 0.7;
}

/* 最新条目滑入 */
.is-new {
  animation: entry-slide-in 0.4s ease-out;
}

@keyframes entry-slide-in {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
