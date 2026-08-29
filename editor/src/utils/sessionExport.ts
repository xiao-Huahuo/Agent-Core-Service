/*
 * 会话导出工具。
 *
 * 从后端获取会话完整消息列表，整理为结构化的 YAML 格式，
 * 包含会话元信息、用户提问、Agent 工具调用、中间回答和最终回答，
 * 并触发浏览器下载。
 */

import { toYaml } from '@/utils/yamlExport'
import { fetchMessages, fetchSessionState } from '@/api/session'
import { fetchChildAgents } from '@/api/agent'
import { fetchSessionTaskList } from '@/api/taskList'
import type { AgentTaskList } from '@/api/taskList'
import type { SessionRecord, SessionMessageRecord } from '@/api/session'

interface ExportMessage {
  role: string
  content: string
  created_at: string
  node?: string
  reference?: string
  attachments?: Array<Record<string, unknown>>
  tool_calls?: unknown[]
  trace_human_readable?: string[]
  trace_details?: unknown[]
  child_agent_event?: unknown
  tool_call_id?: string
  metadata?: Record<string, unknown>
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
  child_agents?: unknown[]
}

function formatMessages(records: SessionMessageRecord[]): ExportMessage[] {
  return records
    .map((msg) => {
      const metadata = (msg.metadata ?? {}) as Record<string, unknown>
      const exportMsg: ExportMessage = {
        role: msg.role,
        content: msg.content || '',
        created_at: msg.created_at,
      }
      exportMsg.metadata = metadata

      if (metadata.node) {
        exportMsg.node = String(metadata.node)
      }
      if (metadata.reference) {
        exportMsg.reference = String(metadata.reference)
      }
      if (Array.isArray(metadata.attachments)) {
        exportMsg.attachments = metadata.attachments.filter(
          (attachment): attachment is Record<string, unknown> => Boolean(attachment && typeof attachment === 'object'),
        )
      }
      if (metadata.child_agent_event && typeof metadata.child_agent_event === 'object') {
        exportMsg.child_agent_event = metadata.child_agent_event
      }
      if (msg.tool_calls && Array.isArray(msg.tool_calls) && msg.tool_calls.length > 0) {
        exportMsg.tool_calls = msg.tool_calls
      }
      if (typeof msg.tool_call_id === 'string') exportMsg.tool_call_id = msg.tool_call_id

      // Extract trace details
      const trace = metadata.trace
      if (trace && Array.isArray(trace) && trace.length > 0) {
        exportMsg.trace_human_readable = trace
          .map((t: Record<string, unknown>) => String(t.human_readable ?? ''))
          .filter(Boolean)
        exportMsg.trace_details = trace
      }

      return exportMsg
    })
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
  limit?: number,
): Promise<void> {
  const [messages, taskListResponse, stateResponse, childResponse] = await Promise.all([
    fetchMessages(session.session_id, userId, limit),
    fetchSessionTaskList(session.session_id).catch(() => null),
    fetchSessionState(session.session_id).catch(() => null),
    fetchChildAgents(session.session_id).catch(() => null),
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
    session_state: stateResponse?.session_state ?? null,
    child_agents: childResponse?.children ?? [],
  }

  const yamlContent = toYaml(data)
  const safeName = sanitizeFilename(data.session.name)
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  triggerDownload(yamlContent, `session-${safeName}-${timestamp}.yaml`)
}
