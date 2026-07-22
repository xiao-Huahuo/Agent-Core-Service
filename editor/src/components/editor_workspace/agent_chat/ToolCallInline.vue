<!--
  Inline tool call summary with per-tool expandable detail.

  Usage:
  Tool mode consumes action-node traces and merges each tool by name, matching
  the console display contract. Each completed tool shows an expand button that
  reveals its full return content, rendered per tool type.
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
  rawContents: string[]
  toolName: string
}

interface ToolEntry {
  tool_name: string
  display_name: string
  args_summary: string
  terminal_command: string
  result_count?: number
  call_count: number
  filenames: string[]
  raw_contents: string[]
}

interface TerminalSegmentResult {
  index: number
  command: string
  exitCode: number
  timedOut: boolean
  stdout: string
  stderr: string
  truncated: boolean
}

interface TerminalResultDisplay {
  ok: boolean
  shell: string
  cwd: string
  truncated: boolean
  segments: TerminalSegmentResult[]
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
  run_terminal_command: '终端命令',
}

function asString(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function asNumber(value: unknown) {
  return typeof value === 'number' ? value : undefined
}

function extractFilename(trace: Record<string, unknown>, toolName: string) {
  const rawContent = asString(trace.raw_content)
  if (toolName === 'write_knowledge_file') {
    const m = rawContent.match(/已保存文件:\s*(.+?)\s*\(/)
    return m ? m[1] : null
  }
  if (toolName === 'delete_knowledge_file') {
    const m = rawContent.match(/已删除:\s*(.+)/)
    return m ? m[1] : null
  }
  if (toolName === 'rename_knowledge_file') {
    const m = rawContent.match(/已重命名:\s*(.+)/)
    return m ? m[1] : null
  }
  if (toolName === 'create_knowledge_folder') {
    const m = rawContent.match(/已创建文件夹:\s*(.+)/)
    return m ? m[1] : null
  }
  return null
}

function extractQuotedListItems(value: string) {
  return Array.from(value.matchAll(/['"]([^'"]+)['"]/g)).map((match) => match[1] ?? '').filter(Boolean)
}

function terminalCommandSummary(argsSummary: string, terminalCommand = '', fallbackShell = '') {
  const shell = (argsSummary.match(/(?:^|,\s*)shell=([^,]+)/)?.[1] ?? fallbackShell).trim()
  if (terminalCommand) {
    return `运行了${shell || '终端'}命令: ${terminalCommand}`
  }
  const program = (argsSummary.match(/['"]?program['"]?\s*:\s*['"]([^'"]+)['"]/)?.[1] ?? '').trim()
  const rawArgs = argsSummary.match(/['"]?args['"]?\s*:\s*\[([^\]]*)\]/)?.[1] ?? ''
  const args = extractQuotedListItems(rawArgs)
  const command = [program, ...args].filter(Boolean).join(' ').trim()
  if (!shell && !command) {
    return '运行了终端命令'
  }
  if (!command) {
    return `运行了${shell || '终端'}命令`
  }
  return `运行了${shell || '终端'}命令: ${command}`
}

function toolSummary(entry: ToolEntry) {
  if (entry.tool_name === 'run_terminal_command') {
    const summary = terminalCommandSummary(entry.args_summary, entry.terminal_command)
    return entry.call_count > 1 ? `${summary} × ${entry.call_count}` : summary
  }

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

function toolMergeKey(toolName: string, argsSummary: string, terminalCommand: string) {
  if (toolName !== 'run_terminal_command') {
    return toolName
  }
  return `${toolName}:${terminalCommand || argsSummary || 'terminal'}`
}

function parseSearchResults(content: string) {
  const lines = content.split('\n').filter((l) => l.trim())
  const items: { index: number; source: string; content: string }[] = []
  let current: { index: number; source: string; content: string[] } | null = null
  for (const line of lines) {
    const m = line.match(/^(\d+)\.\s*\[([^\]]+)\]\s*来源:\s*(.+)/)
    if (m) {
      if (current) {
        items.push({ index: current.index, source: current.source, content: current.content.join('\n').trim() })
      }
      current = { index: parseInt(m[1] ?? '0', 10), source: (m[2] ?? '').trim(), content: [] }
      const afterSource = (m[3] ?? '').trim()
      if (afterSource) current.content.push(afterSource)
    } else if (current) {
      current.content.push(line)
    }
  }
  if (current) {
    items.push({ index: current.index, source: current.source, content: current.content.join('\n').trim() })
  }
  if (items.length === 0) {
    // fallback: just treat whole content as text
    return null
  }
  return items
}

function parseFileList(content: string) {
  const lines = content.split('\n').filter((l) => l.trim())
  const result: { type: 'dir' | 'file'; name: string; indent: number }[] = []
  for (const line of lines) {
    if (line.startsWith('[DIR] ')) {
      result.push({ type: 'dir', name: line.slice(6), indent: 0 })
    } else if (line.startsWith('[FILE] ')) {
      result.push({ type: 'file', name: line.slice(7), indent: 0 })
    }
  }
  return result.length > 0 ? result : null
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
}

function parseTerminalResult(content: string): TerminalResultDisplay | null {
  try {
    const parsed = asRecord(JSON.parse(content))
    if (!parsed || !Array.isArray(parsed.results)) {
      return null
    }
    const segments = parsed.results
      .map((item) => {
        const result = asRecord(item)
        if (!result) return null
        const rawArgs = Array.isArray(result.args) ? result.args.map((arg) => String(arg)) : []
        const program = asString(result.program)
        return {
          index: asNumber(result.index) ?? 0,
          command: [program, ...rawArgs].filter(Boolean).join(' '),
          exitCode: asNumber(result.exit_code) ?? -1,
          timedOut: result.timed_out === true,
          stdout: asString(result.stdout),
          stderr: asString(result.stderr),
          truncated: result.truncated === true,
        }
      })
      .filter((item): item is TerminalSegmentResult => item !== null)
    return {
      ok: parsed.ok === true,
      shell: asString(parsed.shell) || '终端',
      cwd: asString(parsed.cwd) || '-',
      truncated: parsed.truncated === true,
      segments,
    }
  } catch {
    return null
  }
}

const toolEntries = computed(() => {
  const pendingStarts = new Map<string, { key: string; text: string; argsSummary: string }>()
  const startArgsByToolName = new Map<string, string>()
  const startCommandByToolName = new Map<string, string>()
  ;(props.traces ?? [])
    .filter((trace) => trace.event === 'tool_call_start' && trace.tool_name)
    .forEach((trace) => {
      const toolName = asString(trace.tool_name)
      const argsSummary = asString(trace.tool_args_summary)
      const terminalCommand = asString(trace.terminal_command)
      const mergeKey = toolMergeKey(toolName, argsSummary, terminalCommand)
      startArgsByToolName.set(mergeKey, argsSummary)
      startCommandByToolName.set(mergeKey, terminalCommand)
      pendingStarts.set(mergeKey, {
        key: `${mergeKey}-pending`,
        text: toolName === 'run_terminal_command'
          ? terminalCommandSummary(argsSummary, terminalCommand)
          : asString(trace.human_readable) || `正在调用工具「${asString(trace.display_name) || FALLBACK_DISPLAY[toolName] || toolName}」`,
        argsSummary,
      })
    })
  const merged = new Map<string, ToolEntry>()
  ;(props.traces ?? [])
    .filter((trace) => trace.event === 'tool_call_end' && trace.tool_name)
    .forEach((trace) => {
      const toolName = asString(trace.tool_name)
      const argsSummary = asString(trace.tool_args_summary)
      const terminalCommand = asString(trace.terminal_command)
      const mergeKey = toolMergeKey(toolName, argsSummary, terminalCommand)
      pendingStarts.delete(mergeKey)
      const existing = merged.get(mergeKey)
      const resultCount = asNumber(trace.result_count)
      const fn = extractFilename(trace, toolName)
      const rawContent = asString(trace.raw_content)
      if (existing) {
        if (resultCount !== undefined) {
          existing.result_count = (existing.result_count ?? 0) + resultCount
        }
        existing.call_count++
        if (fn && !existing.filenames.includes(fn)) {
          existing.filenames.push(fn)
        }
        if (rawContent && !existing.raw_contents.includes(rawContent)) {
          existing.raw_contents.push(rawContent)
        }
      } else {
        merged.set(mergeKey, {
          tool_name: toolName,
          display_name: asString(trace.display_name) || FALLBACK_DISPLAY[toolName] || toolName,
          args_summary: startArgsByToolName.get(mergeKey) || argsSummary,
          terminal_command: terminalCommand || startCommandByToolName.get(mergeKey) || '',
          result_count: resultCount,
          call_count: 1,
          filenames: fn ? [fn] : [],
          raw_contents: rawContent ? [rawContent] : [],
        })
      }
    })
  return [
    ...Array.from(pendingStarts.values()).map((entry) => ({
      ...entry,
      pending: true,
      rawContents: [],
      toolName: '',
    })),
    ...Array.from(merged.values())
    .map((entry) => ({
      key: `${entry.tool_name}-${entry.terminal_command || entry.call_count}`,
      text: toolSummary(entry),
      pending: false,
      rawContents: entry.raw_contents,
      toolName: entry.tool_name,
    }))
    .filter((entry): entry is ToolDisplayEntry => Boolean(entry.text)),
  ]
})
</script>

<template>
  <div v-for="entry in toolEntries" :key="entry.key" class="tool-call-box" :class="{ expandable: !entry.pending && entry.rawContents.length > 0 }">
    <div class="tool-call-header">
      <span v-if="entry.pending" class="tool-loader" aria-hidden="true"></span>
      <span class="tool-text">{{ entry.text }}</span>
      <button
        v-if="!entry.pending && entry.rawContents.length > 0"
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
      v-if="!entry.pending && entry.rawContents.length > 0"
      class="tool-result-collapse"
      :class="{ open: expanded.has(entry.key) }"
    >
      <div class="tool-result-content">
        <template v-for="(rawContent, idx) in entry.rawContents" :key="idx">
          <!-- Search results: numbered items with source -->
          <div v-if="(entry.toolName === 'search_knowledge' || entry.toolName === 'get_knowledge_context') && parseSearchResults(rawContent)" class="search-results">
            <div v-for="item in parseSearchResults(rawContent)!" :key="item.index" class="search-result-item">
              <span class="search-result-citation">[{{ item.source }}]</span>
              <span class="search-result-source">{{ item.index }}.</span>
              <pre class="search-result-body">{{ item.content }}</pre>
            </div>
          </div>
          <!-- File list -->
          <div v-else-if="entry.toolName === 'list_knowledge_files' && parseFileList(rawContent)" class="file-tree">
            <div v-for="(item, fi) in parseFileList(rawContent)!" :key="fi" class="file-tree-row" :class="item.type">
              <span v-if="item.type === 'dir'" class="tree-icon tree-dir">▸</span>
              <span v-else class="tree-icon tree-file">·</span>
              <span class="tree-name">{{ item.name }}</span>
            </div>
          </div>
          <!-- File read: code block -->
          <div v-else-if="entry.toolName === 'read_knowledge_file'">
            <pre class="tool-result-code">{{ rawContent }}</pre>
          </div>
          <!-- JSON parse/pick: formatted -->
          <div v-else-if="entry.toolName === 'json_parse' || entry.toolName === 'json_pick'">
            <pre class="tool-result-text">{{ rawContent }}</pre>
          </div>
          <!-- Calculate / time / UUID / echo: simple result -->
          <div v-else-if="entry.toolName === 'calculate' || entry.toolName === 'get_current_time' || entry.toolName === 'get_current_utc_time' || entry.toolName === 'generate_uuid' || entry.toolName === 'echo_text' || entry.toolName === 'text_stats'">
            <pre class="tool-result-text">{{ rawContent }}</pre>
          </div>
          <!-- File operations: write/delete/rename/create folder -->
          <div v-else-if="entry.toolName === 'write_knowledge_file' || entry.toolName === 'delete_knowledge_file' || entry.toolName === 'rename_knowledge_file' || entry.toolName === 'create_knowledge_folder'">
            <pre class="tool-result-text">{{ rawContent }}</pre>
          </div>
          <!-- Long-term memory -->
          <div v-else-if="entry.toolName === 'get_long_term_memory'">
            <pre class="tool-result-text">{{ rawContent }}</pre>
          </div>
          <!-- Terminal command result -->
          <div v-else-if="entry.toolName === 'run_terminal_command' && parseTerminalResult(rawContent)" class="terminal-result">
            <div class="terminal-summary">
              <span class="terminal-status" :class="{ ok: parseTerminalResult(rawContent)!.ok, failed: !parseTerminalResult(rawContent)!.ok }">
                {{ parseTerminalResult(rawContent)!.ok ? '执行成功' : '执行失败' }}
              </span>
              <span>终端: {{ parseTerminalResult(rawContent)!.shell }}</span>
              <span>工作目录: {{ parseTerminalResult(rawContent)!.cwd }}</span>
              <span v-if="parseTerminalResult(rawContent)!.truncated">输出已截断</span>
            </div>
            <div
              v-for="segment in parseTerminalResult(rawContent)!.segments"
              :key="segment.index"
              class="terminal-segment"
            >
              <div class="terminal-segment-head">
                <span>第 {{ segment.index }} 段</span>
                <code>{{ segment.command || '内部指令' }}</code>
                <span :class="{ 'exit-ok': segment.exitCode === 0, 'exit-failed': segment.exitCode !== 0 }">
                  退出码 {{ segment.exitCode }}
                </span>
                <span v-if="segment.timedOut">已超时</span>
                <span v-if="segment.truncated">本段输出已截断</span>
              </div>
              <div v-if="segment.stdout" class="terminal-stream">
                <div class="terminal-stream-label">标准输出</div>
                <pre>{{ segment.stdout }}</pre>
              </div>
              <div v-if="segment.stderr" class="terminal-stream error">
                <div class="terminal-stream-label">错误输出</div>
                <pre>{{ segment.stderr }}</pre>
              </div>
              <div v-if="!segment.stdout && !segment.stderr" class="terminal-empty">没有输出</div>
            </div>
          </div>
          <!-- Default: raw text -->
          <div v-else>
            <pre class="tool-result-text">{{ rawContent }}</pre>
          </div>
        </template>
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
  font-family: var(--font-ui);
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
  font-family: var(--font-text);
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

/* Code block for file content */
.tool-result-code {
  margin: 0;
  padding: var(--space-10) var(--space-12);
  background: rgba(0, 0, 0, 0.12);
  color: var(--color-text-secondary);
  font-family: var(--font-text);
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: auto;
  max-height: 600px;
  scrollbar-width: thin;
}

/* Search results list */
.search-results {
  display: flex;
  flex-direction: column;
  padding: var(--space-6) 0;
}

.search-result-item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-4) var(--space-8);
  padding: var(--space-6) var(--space-12);
  border-bottom: 1px solid rgba(148, 163, 184, 0.06);
}

.search-result-item:last-child {
  border-bottom: 0;
}

.search-result-citation {
  grid-column: 1;
  grid-row: 1;
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 var(--space-4);
  border-radius: 3px;
  background: rgba(66, 36, 235, 0.12);
  color: var(--color-primary);
  font-family: var(--font-ui);
  font-size: 9px;
  font-weight: 600;
}

.search-result-source {
  grid-column: 2;
  grid-row: 1;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: 10px;
  align-self: center;
}

.search-result-body {
  grid-column: 2;
  grid-row: 2;
  margin: 0;
  color: var(--color-text-secondary);
  font-family: var(--font-text);
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

/* File tree */
.file-tree {
  display: flex;
  flex-direction: column;
  padding: var(--space-6) 0;
}

.file-tree-row {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  padding: var(--space-3) var(--space-12);
  font-family: var(--font-ui);
  font-size: 11px;
  line-height: 1.5;
}

.tree-icon {
  flex-shrink: 0;
  width: 10px;
  text-align: center;
}

.tree-dir {
  color: var(--color-primary);
}

.tree-file {
  color: var(--color-text-muted);
}

.tree-name {
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-tree-row.dir .tree-name {
  color: var(--color-primary);
  font-weight: 600;
}

.terminal-result {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
  padding: var(--space-10) var(--space-12);
}

.terminal-summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-8);
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: 11px;
  line-height: 1.5;
}

.terminal-status,
.terminal-segment-head span {
  color: var(--color-text-secondary);
}

.terminal-status.ok,
.exit-ok {
  color: var(--color-success);
}

.terminal-status.failed,
.exit-failed {
  color: var(--color-error);
}

.terminal-segment {
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.terminal-segment-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-8);
  padding: var(--space-6) var(--space-8);
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
  background: rgba(148, 163, 184, 0.05);
  font-family: var(--font-ui);
  font-size: 11px;
}

.terminal-segment-head code {
  max-width: 100%;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
}

.terminal-stream {
  padding: var(--space-8);
}

.terminal-stream + .terminal-stream {
  border-top: 1px dashed rgba(148, 163, 184, 0.08);
}

.terminal-stream-label {
  margin-bottom: var(--space-4);
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: 10px;
}

.terminal-stream pre {
  margin: 0;
  color: var(--color-text-secondary);
  font-family: var(--font-text);
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 420px;
  overflow: auto;
  scrollbar-width: thin;
}

.terminal-stream.error pre {
  color: var(--color-error);
}

.terminal-empty {
  padding: var(--space-8);
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: 11px;
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
