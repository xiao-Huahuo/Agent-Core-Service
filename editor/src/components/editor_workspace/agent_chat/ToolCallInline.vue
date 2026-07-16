<!--
  Inline tool call summary.

  Usage:
  Tool mode consumes action-node traces and merges each tool by name, matching
  the console display contract.
-->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  traces?: Array<Record<string, unknown>>
}>()

interface ToolEntry {
  tool_name: string
  display_name: string
  result_count?: number
  call_count: number
  filenames: string[]
}

const FALLBACK_DISPLAY: Record<string, string> = {
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

function asString(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: unknown) {
  return typeof value === 'number' ? value : undefined
}

function extractFilename(trace: Record<string, unknown>, toolName: string) {
  const resultSummary = asString(trace.result_summary)
  if (toolName === 'write_knowledge_file') {
    const m = resultSummary.match(/已保存文件:\s*(.+?)\s*\(/)
    return m ? m[1] : null
  }
  if (toolName === 'delete_knowledge_file') {
    const m = resultSummary.match(/已删除:\s*(.+)/)
    return m ? m[1] : null
  }
  if (toolName === 'rename_knowledge_file') {
    const m = resultSummary.match(/已重命名:\s*(.+)/)
    return m ? m[1] : null
  }
  if (toolName === 'create_knowledge_folder') {
    const m = resultSummary.match(/已创建文件夹:\s*(.+)/)
    return m ? m[1] : null
  }
  return null
}

function toolSummary(entry: ToolEntry) {
  const displayName = entry.display_name || entry.tool_name
  if (!displayName) return null

  if (entry.result_count !== undefined && entry.result_count > 0) {
    return `${displayName}：${entry.result_count} 条结果`
  }

  if (entry.call_count > 1) {
    if (entry.filenames.length === 1) {
      return `${displayName}：${entry.filenames[0]}`
    }
    if (entry.filenames.length > 1) {
      return `${displayName} × ${entry.call_count}：${entry.filenames.join(', ')}`
    }
    return `${displayName} × ${entry.call_count}`
  }

  if (entry.filenames.length === 1) {
    return `${displayName}：${entry.filenames[0]}`
  }
  return displayName
}

const toolEntries = computed(() => {
  const pendingStarts = new Map<string, { key: string; text: string }>()
  ;(props.traces ?? [])
    .filter((trace) => trace.event === 'tool_call_start' && trace.tool_name)
    .forEach((trace) => {
      const toolName = asString(trace.tool_name)
      pendingStarts.set(toolName, {
        key: `${toolName}-pending`,
        text: asString(trace.human_readable) || `正在调用工具「${asString(trace.display_name) || FALLBACK_DISPLAY[toolName] || toolName}」`,
      })
    })
  const merged = new Map<string, ToolEntry>()
  ;(props.traces ?? [])
    .filter((trace) => trace.event === 'tool_call_end' && trace.tool_name)
    .forEach((trace) => {
      const toolName = asString(trace.tool_name)
      pendingStarts.delete(toolName)
      const existing = merged.get(toolName)
      const resultCount = asNumber(trace.result_count)
      const fn = extractFilename(trace, toolName)
      if (existing) {
        if (resultCount !== undefined) {
          existing.result_count = (existing.result_count ?? 0) + resultCount
        }
        existing.call_count++
        if (fn && !existing.filenames.includes(fn)) {
          existing.filenames.push(fn)
        }
      } else {
        merged.set(toolName, {
          tool_name: toolName,
          display_name: asString(trace.display_name) || FALLBACK_DISPLAY[toolName] || toolName,
          result_count: resultCount,
          call_count: 1,
          filenames: fn ? [fn] : [],
        })
      }
    })
  return [
    ...Array.from(pendingStarts.values()),
    ...Array.from(merged.values())
    .map((entry) => ({
      key: `${entry.tool_name}-${entry.call_count}`,
      text: toolSummary(entry),
    }))
    .filter((entry): entry is { key: string; text: string } => Boolean(entry.text)),
  ]
})
</script>

<template>
  <div v-for="entry in toolEntries" :key="entry.key" class="tool-call-box">
    <span class="tool-text">{{ entry.text }}</span>
  </div>
</template>

<style scoped>
.tool-call-box {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: var(--space-8);
  box-sizing: border-box;
  width: 100%;
  margin-bottom: var(--space-6);
  padding: var(--space-8) var(--space-12);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(148, 163, 184, 0.16), rgba(148, 163, 184, 0.07) 48%, transparent),
    rgba(255, 255, 255, 0.025);
  backdrop-filter: blur(10px);
  animation: count-pop 0.35s ease;
}

.tool-text {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: var(--line-height-normal);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes count-pop {
  0% {
    opacity: 0.6;
    transform: scaleY(0.95);
  }
  100% {
    opacity: 1;
    transform: scaleY(1);
  }
}
</style>
