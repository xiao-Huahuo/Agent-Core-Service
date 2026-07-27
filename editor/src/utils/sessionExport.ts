/*
 * 会话导出工具。
 *
 * 从后端获取会话完整消息列表，整理为结构化的 YAML 格式，
 * 包含会话元信息、用户提问、Agent 工具调用、中间回答和最终回答，
 * 并触发浏览器下载。
 */

import { toYaml } from '@/utils/yamlExport'
import { fetchMessages } from '@/api/session'
import { fetchSessionTaskList } from '@/api/taskList'
import type { AgentTaskList } from '@/api/taskList'
import type { SessionRecord, SessionMessageRecord } from '@/api/session'

interface ExportMessage {
  role: string
  content: string
  created_at: string
  node?: string
  reference?: string
  attachments?: Array<{ name: string; url: string }>
  tool_calls?: unknown[]
  trace_human_readable?: string[]
  trace_details?: unknown[]
}

interface ExportData {
  session: {
    id: string
    name: string
    user_id: string
    created_at: string
    updated_at: string
  }
  messages: ExportMessage[]
  task_list?: AgentTaskList | null
  session_state?: Record<string, unknown> | null
}

function formatMessages(records: SessionMessageRecord[]): ExportMessage[] {
  return records
    .filter((msg) => msg.role !== 'system')
    .map((msg) => {
      const metadata = (msg.metadata ?? {}) as Record<string, unknown>
      const exportMsg: ExportMessage = {
        role: msg.role,
        content: msg.content || '',
        created_at: msg.created_at,
      }

      if (metadata.node) {
        exportMsg.node = String(metadata.node)
      }
      if (metadata.reference) {
        exportMsg.reference = String(metadata.reference)
      }
      if (msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0) {
        exportMsg.tool_calls = msg.tool_calls.map(cleanToolCall)
      }

      // Extract trace details
      const trace = metadata.trace
      if (trace && Array.isArray(trace) && trace.length > 0) {
        exportMsg.trace_human_readable = trace
          .map((t: Record<string, unknown>) => String(t.human_readable ?? ''))
          .filter(Boolean)
        exportMsg.trace_details = trace.map(cleanTraceItem)
      }

      return exportMsg
    })
}

function cleanToolCall(call: unknown): unknown {
  if (typeof call !== 'object' || call === null) return call
  const c = call as Record<string, unknown>
  return {
    name: c.name ?? c.tool_name ?? '',
    arguments: c.arguments ?? c.args ?? c.parameters ?? {},
    result: c.result ?? c.output ?? '',
  }
}

function cleanTraceItem(trace: Record<string, unknown>): Record<string, unknown> {
  const cleaned: Record<string, unknown> = {}
  if (trace.event) cleaned.event = trace.event
  if (trace.node) cleaned.node = trace.node
  if (trace.tool_name) cleaned.tool_name = trace.tool_name
  if (trace.human_readable) cleaned.human_readable = trace.human_readable
  if (trace.input) cleaned.input = trace.input
  if (trace.output) cleaned.output = trace.output
  if (trace.duration_ms) cleaned.duration_ms = trace.duration_ms
  return cleaned
}

function triggerDownload(yaml: string, filename: string) {
  const blob = new Blob([yaml], { type: 'text/yaml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

function sanitizeFilename(name: string): string {
  return name.replace(/[/\\:*?"<>|]/g, '_').slice(0, 100) || 'session'
}

/**
 * 导出指定会话的全部内容为 YAML 文件并触发下载。
 *
 * @param session 会话元信息
 * @param userId  用户 ID
 * @param limit   拉取的最大消息数量
 */
export async function exportSession(
  session: SessionRecord,
  userId: string,
  limit = 200,
): Promise<void> {
  const [messages, taskListResponse] = await Promise.all([
    fetchMessages(session.session_id, userId, limit),
    fetchSessionTaskList(session.session_id).catch(() => null),
  ])

  const data: ExportData = {
    session: {
      id: session.session_id,
      name: session.session_name || session.session_id.slice(0, 8),
      user_id: session.user_id,
      created_at: session.created_at,
      updated_at: session.updated_at,
    },
    messages: formatMessages(messages),
    task_list: taskListResponse?.task_list ?? null,
  }

  const yamlContent = toYaml(data)
  const safeName = sanitizeFilename(data.session.name)
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  triggerDownload(yamlContent, `session-${safeName}-${timestamp}.yaml`)
}
