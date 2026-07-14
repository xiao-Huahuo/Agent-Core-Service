<!--
  ToolCallInline —— 工具模式下的工具调用内联展示。
  从 message.trace 中提取工具调用条目，优先显示后端 human_readable/display_name，
  对未知工具也保留调用记录，避免工具执行了但前端静默丢失。
-->

<script setup>
import { computed } from 'vue'

const props = defineProps({
  traces: { type: Array, default: () => [] },
})

const FALLBACK_DISPLAY = {
  get_current_utc_time: '获取UTC时间',
  get_current_time: '获取当前时间',
  echo_text: '回显文本',
  generate_uuid: '生成UUID',
  calculate: '数学计算',
  json_parse: '解析JSON',
  json_pick: '提取JSON字段',
  text_stats: '文本统计',
  list_builtin_tools: '列出工具',
  get_long_term_memory: '检索记忆',
  write_long_term_memory: '写入记忆',
  get_knowledge_context: '检索知识',
  rebuild_knowledge_base: '重建知识库',
  get_current_viewing_document: '获取当前文档',
  list_knowledge_files: '列出文件',
  read_knowledge_file: '阅读文件',
  write_knowledge_file: '创作文件',
  delete_knowledge_file: '删除文件',
  rename_knowledge_file: '重命名文件',
  create_knowledge_folder: '创建文件夹',
  update_exploration_state: '更新探索状态',
}

function resolveDisplayName(trace) {
  return trace.display_name || FALLBACK_DISPLAY[trace.tool_name] || trace.tool_name || '工具'
}

function toolSummary(entry) {
  if (entry.human_readable) return entry.human_readable
  const displayName = entry.display_name || entry.tool_name
  if (!displayName) return null
  if (entry.result_count !== undefined) {
    return `${displayName}：${entry.result_count} 条结果`
  }
  if (entry.call_count > 1) {
    return `${displayName} × ${entry.call_count}`
  }
  return displayName
}

const toolEntries = computed(() => {
  const pendingStarts = new Map()
  props.traces
    .filter(t => t.event === 'tool_call_start' && t.tool_name)
    .forEach((t) => {
      pendingStarts.set(t.tool_name, {
        key: `${t.tool_name}-pending`,
        text: t.human_readable || `正在调用工具「${resolveDisplayName(t)}」`,
      })
    })
  const endTraces = props.traces.filter(t => t.event === 'tool_call_end' && t.tool_name)
  const merged = new Map()
  for (const t of endTraces) {
    pendingStarts.delete(t.tool_name)
    const existing = merged.get(t.tool_name)
    if (existing) {
      if (t.result_count != null) {
        existing.result_count = (existing.result_count || 0) + t.result_count
      }
      existing.call_count += 1
      existing.human_readable = t.human_readable || existing.human_readable
    } else {
      merged.set(t.tool_name, {
        tool_name: t.tool_name,
        display_name: resolveDisplayName(t),
        result_count: t.result_count,
        call_count: 1,
        human_readable: t.human_readable,
      })
    }
  }
  return [
    ...Array.from(pendingStarts.values()),
    ...Array.from(merged.values())
    .map(t => ({
      key: `${t.tool_name}-${t.call_count}-${t.result_count ?? ''}`,
      text: toolSummary(t),
    }))
    .filter(e => e.text),
  ]
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
