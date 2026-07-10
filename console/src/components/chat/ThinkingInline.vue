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

function togglePanel() {
  if (isExpanded.value) {
    emit('collapse')
  } else {
    isExpanded.value = true
  }
}

/** 需要隐藏的 trace 事件: 工具调用开始只显示结束结果 */
const SKIP_EVENTS = new Set(['tool_call_start'])

/** 工具名 → {动词, 名词},result_count 存在时拼为 "检索到 X 条记忆" */
const TOOL_DESC = {
  get_long_term_memory: { verb: '检索', noun: '记忆' },
  get_knowledge_context: { verb: '检索', noun: '知识' },
}

function toolSummary(trace) {
  const desc = TOOL_DESC[trace.tool_name]
  if (!desc) return trace.tool_name || '调用工具'
  if (trace.result_count) {
    return `${desc.verb}到 ${trace.result_count} 条${desc.noun}`
  }
  return `${desc.verb}${desc.noun}`
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
    .filter(t => !SKIP_EVENTS.has(t.event) && t.human_readable)
    .map(t => ({
      key: `${t.node}-${t.event}-${t.tool_name || ''}`,
      text: entryText(t),
      isTool: t.event === 'tool_call_end',
    }))
})
</script>

<template>
  <div v-if="entries.length > 0" class="thinking-inline">
    <!-- 折叠栏 -->
    <div class="toggle-bar" @click="togglePanel">
      <span class="bar-chevron" :class="{ expanded: isExpanded }">></span>
      <span v-if="!isExpanded && isStreaming" class="bar-label">思考中...</span>
      <span v-else-if="!isExpanded && !isStreaming" class="bar-label">思考完成</span>
      <span v-else class="bar-label">思考过程</span>
    </div>

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
  </div>
</template>

<style scoped>
/* ========== 根容器 ========== */
.thinking-inline {
  margin-bottom: var(--space-8);
}

/* ========== 折叠栏 ========== */
.toggle-bar {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  cursor: pointer;
  user-select: none;
  padding: var(--space-4) 0;
}

.bar-chevron {
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
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
  color: var(--color-text-secondary);
  opacity: 0.7;
  transition: opacity var(--transition-fast);
}

.toggle-bar:hover .bar-label {
  opacity: 0.9;
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
