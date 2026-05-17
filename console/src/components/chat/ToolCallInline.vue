<!--
  ToolCallInline —— 工具模式下的工具调用内联展示。
  从 message.trace 中提取工具调用条目，简洁显示 "检索到 X 条记忆" 等。
  整行灰白色圆角矩形框。
-->

<script setup>
import { computed } from 'vue'

const props = defineProps({
  traces: { type: Array, default: () => [] },
})

const TOOL_DESC = {
  get_long_term_memory: { verb: '检索', noun: '记忆' },
  get_knowledge_context: { verb: '检索', noun: '知识' },
}

function toolSummary(trace) {
  const desc = TOOL_DESC[trace.tool_name]
  if (!desc) return null
  if (trace.result_count != null) {
    return `${desc.verb}到 ${trace.result_count} 条${desc.noun}`
  }
  return `${desc.verb}${desc.noun}`
}

const toolEntries = computed(() => {
  const endTraces = props.traces.filter(t => t.event === 'tool_call_end' && t.tool_name)
  const merged = new Map()
  for (const t of endTraces) {
    const existing = merged.get(t.tool_name)
    if (existing) {
      if (t.result_count != null) {
        existing.result_count = (existing.result_count || 0) + t.result_count
      }
    } else {
      merged.set(t.tool_name, { tool_name: t.tool_name, result_count: t.result_count })
    }
  }
  return Array.from(merged.values())
    .map(t => ({
      key: `${t.tool_name}-${t.result_count ?? ''}`,
      text: toolSummary(t),
    }))
    .filter(e => e.text)
})
</script>

<template>
  <div
    v-for="entry in toolEntries"
    :key="entry.key"
    class="tool-call-box"
  >
    <span class="tool-icon">$</span>
    <span class="tool-text">{{ entry.text }}</span>
  </div>
</template>

<style scoped>
.tool-call-box {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-8);
  width: 100%;
  background: none;
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: var(--space-8) var(--space-12);
  margin-bottom: var(--space-6);
  animation: count-pop 0.35s ease;
}

@keyframes count-pop {
  0% { opacity: 0.6; transform: scaleY(0.95); }
  100% { opacity: 1; transform: scaleY(1); }
}

.tool-icon {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-accent);
  flex-shrink: 0;
}

.tool-text {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: var(--line-height-normal);
}
</style>
