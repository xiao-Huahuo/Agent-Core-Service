<!--
  Inline tool call summary.

  Usage:
  Tool mode consumes action-node traces and merges each tool by name, matching
  the console display contract.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

const props = defineProps<{
  traces?: Array<Record<string, unknown>>
}>()

interface ToolDisplayEntry {
  key: string
  text: string
  pending: boolean
  resultSummaries: string[]
}

interface ToolEntry {
  tool_name: string
  display_name: string
  result_count?: number
  call_count: number
  filenames: string[]
  result_summaries: string[]
}

const expanded = ref(new Set<string>())

function toggleExpand(key: string) {
  const next = new Set(expanded.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expanded.value = next
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
        const rs = asString(trace.result_summary)
        if (rs && !existing.result_summaries.includes(rs)) {
          existing.result_summaries.push(rs)
        }
      } else {
        merged.set(toolName, {
          tool_name: toolName,
          display_name: asString(trace.display_name) || FALLBACK_DISPLAY[toolName] || toolName,
          result_count: resultCount,
          call_count: 1,
          filenames: fn ? [fn] : [],
          result_summaries: asString(trace.result_summary) ? [asString(trace.result_summary)] : [],
        })
      }
    })
  return [
    ...Array.from(pendingStarts.values()).map((entry) => ({ ...entry, pending: true, resultSummaries: [] })),
    ...Array.from(merged.values())
    .map((entry) => ({
      key: `${entry.tool_name}-${entry.call_count}`,
      text: toolSummary(entry),
      pending: false,
      resultSummaries: entry.result_summaries,
    }))
    .filter((entry): entry is ToolDisplayEntry => Boolean(entry.text)),
  ]
})
</script>

<template>
  <div v-for="entry in toolEntries" :key="entry.key" class="tool-call-box" :class="{ expandable: !entry.pending && entry.resultSummaries.length > 0 }">
    <div class="tool-call-header">
      <span v-if="entry.pending" class="tool-loader" aria-hidden="true"></span>
      <span class="tool-text">{{ entry.text }}</span>
      <button
        v-if="!entry.pending && entry.resultSummaries.length > 0"
        class="tool-expand-btn"
        type="button"
        :class="{ expanded: expanded.has(entry.key) }"
        :aria-label="expanded.has(entry.key) ? '收起结果' : '展开结果'"
        @click="toggleExpand(entry.key)"
      >
        <ChevronDown :size="16" />
      </button>
    </div>
    <div
      v-if="!entry.pending && entry.resultSummaries.length > 0"
      class="tool-result-collapse"
      :class="{ open: expanded.has(entry.key) }"
    >
      <div class="tool-result-content">
        <pre
          v-for="(summary, idx) in entry.resultSummaries"
          :key="idx"
          class="tool-result-text"
        >{{ summary }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tool-call-box {
  display: flex;
  flex-direction: column;
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
  animation: tool-slide-in 220ms ease-out;
}

.tool-call-box.expandable {
  padding: 0;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-8) var(--space-12);
  min-height: 32px;
}

.tool-loader {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  border: 2px solid rgba(148, 163, 184, 0.22);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: tool-loader-spin 720ms linear infinite;
}

.tool-text {
  flex: 1;
  min-width: 0;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: var(--line-height-normal);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-expand-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.tool-expand-btn:hover {
  color: var(--color-text-secondary);
  background: rgba(148, 163, 184, 0.12);
}

.tool-expand-btn svg {
  transition: transform 220ms ease;
}

.tool-expand-btn.expanded svg {
  transform: rotate(180deg);
}

.tool-result-collapse {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 280ms cubic-bezier(0.4, 0, 0.2, 1);
}

.tool-result-collapse.open {
  grid-template-rows: 1fr;
}

.tool-result-content {
  overflow: hidden;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
}

.tool-result-text {
  margin: 0;
  padding: var(--space-8) var(--space-12);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 600px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.tool-result-text + .tool-result-text {
  border-top: 1px dashed rgba(148, 163, 184, 0.08);
}

@keyframes tool-slide-in {
  0% {
    opacity: 0;
    transform: translateY(-10px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes tool-loader-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
