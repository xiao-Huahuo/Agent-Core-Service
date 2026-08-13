/*
 * Agent chat message store.
 *
 * Usage:
 * Owns streamed Agent messages for the editor right panel. The implementation
 * mirrors console chat behavior while staying typed for the editor front-end.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { deleteAgentAttachment, fetchChildAgents, fetchTaskSuggestions, streamPrompt } from '@/api/agent'
import type { AgentAccessMode, AgentAttachmentUploadResponse, AgentLoopMode, ChildAgentRecord } from '@/api/agent'
import { fetchMessages } from '@/api/session'
import type { AgentTaskList } from '@/api/taskList'
import { useSessionStore } from '@/stores/session'
import { useTaskListStore } from '@/stores/taskList'
import { useWorkspaceStore } from '@/stores/workspace'
import type { MarkdownHtmlVisualizationPayload } from '@/types/knowledge'

export interface AgentChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  message_id?: string
  node?: string
  tool_calls?: unknown[]
  metadata?: Record<string, unknown>
  trace?: Array<Record<string, unknown>>
  created_at?: string
  reference?: string
  attachments?: AgentUploadedAttachment[]
  thinking_seconds?: number
}

export type AgentUploadedAttachment = AgentAttachmentUploadResponse['attachment']

export interface SourceItem {
  source_uri: string
  content: string
  source?: string
  title?: string
  citation_id?: string
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asTrace(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object') as Array<Record<string, unknown>> : []
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asSourceMap(value: unknown): Record<string, SourceItem> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  const result: Record<string, SourceItem> = {}
  for (const [key, source] of Object.entries(value as Record<string, unknown>)) {
    if (!source || typeof source !== 'object' || Array.isArray(source)) {
      continue
    }
    const record = source as Record<string, unknown>
    result[key] = {
      source_uri: asString(record.source_uri),
      content: asString(record.content),
      source: asString(record.source) || undefined,
      title: asString(record.title) || undefined,
    }
  }
  return result
}

function traceIdentity(trace: Record<string, unknown>): string {
  return [
    asString(trace.node),
    asString(trace.event),
    asString(trace.tool_call_id),
    asString(trace.tool_name),
    asString(trace.human_readable),
  ].join('|')
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<AgentChatMessage[]>([])
  const isStreaming = ref(false)
  /** Timestamp shared by all loading indicators for the active user turn. */
  const streamStartedAtMs = ref(0)
  const currentNode = ref('')
  const streamError = ref('')
  const loadedSessionId = ref('')
  const contextMirror = ref<unknown[]>([])
  const activeAgentMode = ref<AgentLoopMode>('auto')
  const currentKnowledgeSources = ref<SourceItem[]>([])
  const currentCitationMap = ref<Record<string, SourceItem>>({})
  const pendingAttachments = ref<AgentUploadedAttachment[]>([])
  const taskSuggestions = ref<string[]>([])
  const suggestionsLoading = ref(false)
  const loadingHistory = ref(false)

  let streamAbortController: AbortController | null = null
  let historyAbortController: AbortController | null = null
  let streamTimeoutId: number | null = null
  const streamTimeoutMs = 10 * 60 * 1000 // 10 minutes sliding window
  let suggestionRequestId = 0
  let suggestionAbortController: AbortController | null = null
  let historyRequestId = 0
  let pendingContent = ''
  let flushTimer: number | null = null
  let turnStartedAtMs = 0
  const contentFlushMs = 50

  const lastMessage = computed(() => messages.value.length > 0 ? messages.value[messages.value.length - 1] : null)
  const canSend = computed(() => !isStreaming.value)

  function appendMessage(message: AgentChatMessage) {
    messages.value.push({ ...message })
  }

  function findLastAssistant() {
    for (let index = messages.value.length - 1; index >= 0; index -= 1) {
      const message = messages.value[index]
      if (message?.role === 'assistant') {
        return message
      }
    }
    return null
  }

  function findLastFinalAssistant() {
    for (let index = messages.value.length - 1; index >= 0; index -= 1) {
      const message = messages.value[index]
      if (message?.role !== 'assistant' || !message.content?.trim()) {
        continue
      }
      const node = asString(message.node) || asString(message.metadata?.node)
      if (node === 'agent' || node === 'error' || node === 'interrupted' || !node) {
        return message
      }
    }
    return null
  }

  function updateLastMessage(
    content?: string,
    node?: string,
    toolCalls?: unknown[],
    trace?: Array<Record<string, unknown>>,
  ) {
    const last = findLastAssistant()
    if (!last) {
      return
    }
    if (content !== undefined) {
      last.content = content
    }
    if (node !== undefined) {
      last.node = node
    }
    if (toolCalls !== undefined) {
      last.tool_calls = toolCalls
    }
    if (trace && trace.length > 0) {
      last.trace ??= []
      last.trace.push(...trace)
    }
  }

  function mergeCurrentCitationMap(value: unknown) {
    const citationMap = asSourceMap(value)
    if (Object.keys(citationMap).length === 0) {
      return
    }
    currentCitationMap.value = {
      ...currentCitationMap.value,
      ...citationMap,
    }
  }

  function attachMetadataToLastAssistant(metadata: Record<string, unknown>) {
    if (Object.keys(metadata).length === 0) {
      return
    }
    const last = findLastAssistant()
    if (!last) {
      return
    }
    const existing = last.metadata ?? {}
    const existingCitationMap = existing.citation_map as Record<string, unknown> | undefined
    const newCitationMap = metadata.citation_map as Record<string, unknown> | undefined
    const mergedCitationMap =
      existingCitationMap && newCitationMap
        ? { ...existingCitationMap, ...newCitationMap }
        : undefined
    last.metadata = {
      ...existing,
      ...metadata,
      ...(mergedCitationMap ? { citation_map: mergedCitationMap } : {}),
    }
  }

  function attachCitationMapToLastFinalAssistant() {
    if (Object.keys(currentCitationMap.value).length === 0) {
      return
    }
    const last = findLastFinalAssistant()
    if (!last) {
      return
    }
    const existing = last.metadata ?? {}
    const existingCitationMap = asSourceMap(existing.citation_map)
    last.metadata = {
      ...existing,
      citation_map: {
        ...existingCitationMap,
        ...currentCitationMap.value,
      },
    }
  }

  function flushStreamContent() {
    flushTimer = null
    if (!pendingContent) {
      return
    }
    const last = findLastAssistant()
    if (last) {
      last.content += pendingContent
    }
    pendingContent = ''
  }

  function scheduleContentFlush() {
    if (flushTimer !== null) {
      return
    }
    flushTimer = window.setTimeout(flushStreamContent, contentFlushMs)
  }

  function appendStreamContent(content: string) {
    pendingContent += content
    scheduleContentFlush()
  }

  function nowMs() {
    return typeof performance !== 'undefined' && typeof performance.now === 'function'
      ? performance.now()
      : Date.now()
  }

  function markThinkingDurationIfNeeded(message: AgentChatMessage, hasFinalContent = Boolean(message.content?.trim())) {
    if (!turnStartedAtMs || message.thinking_seconds !== undefined) {
      return
    }
    const node = asString(message.node) || asString(message.metadata?.node)
    const isFinalAssistantNode = node === 'agent' || node === 'agent_simple' || node === 'error' || node === 'interrupted' || !node
    if (!isFinalAssistantNode || !hasFinalContent) {
      return
    }
    const elapsedSeconds = Math.max(0, (nowMs() - turnStartedAtMs) / 1000)
    message.thinking_seconds = Math.round(elapsedSeconds * 10) / 10
  }

  function cancelPendingFlush() {
    if (flushTimer !== null) {
      window.clearTimeout(flushTimer)
      flushTimer = null
    }
    pendingContent = ''
  }

  function forceFlushContent() {
    if (flushTimer !== null) {
      window.clearTimeout(flushTimer)
      flushTimer = null
    }
    flushStreamContent()
    pendingContent = ''
  }

  async function loadHistory(sessionId: string, userId: string, limit?: number) {
    const requestId = ++historyRequestId
    historyAbortController?.abort()
    historyAbortController = new AbortController()
    loadingHistory.value = true
    messages.value = []
    try {
      const history = await fetchMessages(sessionId, userId, limit, { signal: historyAbortController.signal })
      if (requestId !== historyRequestId) return
      messages.value = history
        .filter((message) => message.role !== 'tool' || message.metadata?.node === 'action')
        .filter((message) => message.metadata?.node !== 'planner' && message.metadata?.node !== 'observation')
        .filter((message) => {
          return message.role !== 'assistant'
            || message.content
            || (message.tool_calls && message.tool_calls.length > 0)
            || message.metadata?.node === 'action'
            || message.metadata?.node === 'child_agent'
        })
        .map((message) => ({
          role: message.role === 'tool' ? 'assistant' : message.role as AgentChatMessage['role'],
          content: message.content,
          message_id: message.message_id,
          node: asString(message.metadata?.node),
          tool_calls: message.tool_calls,
          metadata: {
            ...(message.metadata ?? {}),
            ...(message.tool_call_id ? { tool_call_id: message.tool_call_id } : {}),
          },
          trace: asTrace(message.metadata?.trace),
          created_at: message.created_at,
          reference: asString(message.metadata?.reference) || undefined,
        }))
      loadedSessionId.value = sessionId
      // History restoration must never behave like a live task-list update:
      // otherwise it opens the sidebar without enabling a matching card.
      void useTaskListStore().load(sessionId, { open: false })
      void refreshTaskSuggestions(userId, sessionId)
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return
      }
      console.error('加载历史消息失败:', error)
      messages.value = []
      loadedSessionId.value = ''
    } finally {
      if (requestId === historyRequestId) {
        loadingHistory.value = false
      }
    }
  }

  async function refreshTaskSuggestions(userId: string, sessionId: string) {
    const requestId = ++suggestionRequestId
    suggestionAbortController?.abort()
    suggestionAbortController = new AbortController()
    suggestionsLoading.value = true
    try {
      const result = await fetchTaskSuggestions(userId, sessionId, {
        signal: suggestionAbortController.signal,
      })
      if (requestId === suggestionRequestId) {
        taskSuggestions.value = result.suggestions ?? []
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return
      }
      console.debug('生成任务推荐失败:', error)
      if (requestId === suggestionRequestId) {
        taskSuggestions.value = []
      }
    } finally {
      if (requestId === suggestionRequestId) {
        suggestionsLoading.value = false
      }
    }
  }

  async function send(
    userId: string,
    sessionId: string | null,
    prompt: string,
    reference = '',
    agentMode: AgentLoopMode = 'auto',
    agentAccessMode: AgentAccessMode = 'sandbox',
    options: { wakeup?: boolean; childAgentEvent?: Record<string, unknown> } = {},
  ) {
    if (!prompt.trim()) {
      return
    }
    const sessionStore = useSessionStore()
    let targetSessionId = sessionId || sessionStore.currentSessionId

    if (isStreaming.value) {
      cancelStream()
    }

    const attachmentsForTurn = [...pendingAttachments.value]
    pendingAttachments.value = []
    taskSuggestions.value = []
    // 用户气泡推出时立即阻断进行中的小模型任务推荐,避免旧结果回填与资源浪费
    suggestionRequestId += 1
    suggestionAbortController?.abort()
    suggestionAbortController = null
    appendMessage({
      role: 'user',
      content: prompt,
      reference: reference || undefined,
      attachments: attachmentsForTurn,
      metadata: options.wakeup ? { wakeup: true, child_agent_event: options.childAgentEvent } : undefined,
      created_at: new Date().toISOString(),
    })
    turnStartedAtMs = nowMs()
    streamStartedAtMs.value = turnStartedAtMs

    streamAbortController = new AbortController()
    const signal = streamAbortController.signal
    isStreaming.value = true
    streamError.value = ''
    activeAgentMode.value = agentMode
    currentKnowledgeSources.value = []
    currentCitationMap.value = {}

    // Start stream timeout — auto-cancel if stream stalls for >10 minutes
    resetStreamTimeout()

    const bufferedTraces: Array<Record<string, unknown>> = []
    let assistantCreated = false
    let activeNode = ''

    function ensureAssistant(node: string) {
      if (assistantCreated && activeNode === node) {
        return
      }
      appendMessage({
        role: 'assistant',
        content: '',
        node,
        tool_calls: [],
        trace: [...bufferedTraces],
        metadata: { turn_started_at_ms: streamStartedAtMs.value },
        created_at: new Date().toISOString(),
      })
      assistantCreated = true
      activeNode = node
      bufferedTraces.length = 0
    }

    function appendTraceToCurrentAssistant(node: string, trace: Array<Record<string, unknown>>) {
      ensureAssistant(node)
      const lastAssistant = findLastAssistant()
      if (lastAssistant) {
        lastAssistant.trace ??= []
        const seen = new Set(lastAssistant.trace.map(traceIdentity))
        const fresh = trace.filter((item) => {
          const key = traceIdentity(item)
          if (seen.has(key)) return false
          seen.add(key)
          return true
        })
        lastAssistant.trace.push(...fresh)
        if (node === 'action') {
          lastAssistant.node = 'action'
        }
      }
    }

    try {
      if (!targetSessionId) {
        targetSessionId = await sessionStore.create(userId)
        sessionStore.select(targetSessionId)
      }

      for await (const rawChunk of streamPrompt(
        userId,
        targetSessionId,
        prompt,
        { signal, reference, agentMode, agentAccessMode },
      )) {
        const chunk = asRecord(rawChunk)
        const node = asString(chunk.node)
        const content = asString(chunk.content)
        const trace = asTrace(chunk.trace)
        const metadata = asRecord(chunk.metadata)
        const actualMode = asString(metadata.agent_mode)
        if (actualMode === 'simple' || actualMode === 'react' || actualMode === 'plan') {
          activeAgentMode.value = actualMode
        }
        currentNode.value = node
        mergeCurrentCitationMap(metadata.citation_map)
        for (const traceItem of trace) {
          mergeCurrentCitationMap(traceItem.citation_map)
          const changeSnapshot = asRecord(traceItem.change_snapshot)
          if (changeSnapshot) {
            window.dispatchEvent(new CustomEvent('agent-change-updated', { detail: changeSnapshot }))
          }
        }
        resetStreamTimeout() // 每次收到新 chunk 重置超时计时器

        if (chunk.type === 'system_prompt' && content) {
          messages.value = messages.value.filter((message) => message.role !== 'system')
          messages.value.push({ role: 'system', content, metadata })
          // Extract knowledge sources for citation display
          currentKnowledgeSources.value = []
          currentCitationMap.value = {}
          const citationMap = asSourceMap(metadata.citation_map)
          if (Object.keys(citationMap).length > 0) {
            currentCitationMap.value = citationMap
            // Populate knowledge sources list from citation_map
            const seen = new Set<string>()
            for (const [, source] of Object.entries(citationMap)) {
              if (source.source_uri && !seen.has(source.source_uri)) {
                seen.add(source.source_uri)
                currentKnowledgeSources.value.push(source)
              }
            }
          }
          continue
        }

        if (chunk.type === 'context_mirror' && Array.isArray(chunk.context_messages)) {
          contextMirror.value = chunk.context_messages
          continue
        }

        if (chunk.type === 'task_list_updated') {
          useTaskListStore().setTaskList(chunk.task_list as AgentTaskList | null)
          continue
        }

        if (chunk.type === 'markdown_html_visualization' && chunk.visualization) {
          useWorkspaceStore().showMarkdownHtmlVisualization(chunk.visualization as MarkdownHtmlVisualizationPayload)
          continue
        }

        if (chunk.type === 'child_agent_event') {
          // 流内 SSE 实时推送的子 Agent 事件。同一 run_id 的终态事件只渲染一次:
          // 唤醒流启动时后端会重推会话队列里残留的 completed 事件,若此前已见过
          // 该 run_id 的终态(如 wakeUpAgentForChild 已设过),直接跳过避免重复"已完成"条。
          const childEvent = metadata.child_agent_event as { child?: Record<string, unknown> } | undefined
          const childPayload = childEvent?.child
          if (childPayload && typeof childPayload.run_id === 'string') {
            const childStatus = childPayload.status as ChildAgentRecord['status']
            if (isTerminalChildStatus(childStatus)) {
              const previous = seenChildStatus.get(childPayload.run_id)
              if (previous !== undefined && isTerminalChildStatus(previous)) {
                seenChildStatus.set(childPayload.run_id, childStatus)
                continue
              }
              seenChildStatus.set(childPayload.run_id, childStatus)
            }
          }
          appendMessage({
            role: 'assistant',
            content: '',
            node: 'child_agent',
            metadata,
            trace,
            created_at: new Date().toISOString(),
          })
          continue
        }

        if (chunk.type === 'session_renamed') {
          const newName = asString(chunk.session_name)
          if (newName) {
            sessionStore.renameLocal(targetSessionId ?? '', newName)
          }
          continue
        }

        if (node === 'action') {
          if (trace.length > 0) {
            appendTraceToCurrentAssistant('action', trace)
          }
          continue
        }

        // The model's tool_calls update arrives before the action node and may
        // have no text. Turn it into running traces immediately instead of
        // waiting for the tool result callback.
        const announcedToolCalls = asArray(chunk.tool_calls)
        if (announcedToolCalls.length > 0) {
          const previews = announcedToolCalls
            .map(asRecord)
            .filter((toolCall) => asString(toolCall.name))
            .map((toolCall) => ({
              node: 'action',
              event: 'tool_call_start',
              tool_call_id: asString(toolCall.id),
              tool_name: asString(toolCall.name),
              // Let the shared tool renderer use its localized display name.
              display_name: '',
              tool_args_summary: JSON.stringify(toolCall.args ?? {}),
              human_readable: `正在调用工具「${asString(toolCall.name)}」`,
              chat_visible: true,
            }))
          if (previews.length > 0) {
            appendTraceToCurrentAssistant('action', previews)
            continue
          }
        }

        if (content) {
          ensureAssistant(node)
          if (chunk.type === 'delta') {
            appendStreamContent(content)
            const last = findLastAssistant()
            if (last) {
              markThinkingDurationIfNeeded(last, true)
            }
          } else {
            cancelPendingFlush()
            const last = findLastAssistant()
            if (last) {
              // 完整 content 分支:仅当没有已累积正文、或新内容以累积正文为前缀
              // (流被拦截时后端会补发完整正文)时才整体替换,避免文本跳变/缩短。
              if (!last.content) {
                last.content = content
              } else if (
                content.startsWith(last.content)
                || content.length > last.content.length
              ) {
                last.content = content
              }
              markThinkingDurationIfNeeded(last)
            }
          }
          attachMetadataToLastAssistant(metadata)
          const last = findLastAssistant()
          const backendFirstDeltaMs = asFiniteNumber(asRecord(last?.metadata?.latency).first_agent_delta_ms)
          if (last && backendFirstDeltaMs !== null) {
            last.metadata = {
              ...(last.metadata ?? {}),
              backend_first_delta_seconds: Math.round((backendFirstDeltaMs / 1000) * 10) / 10,
            }
          }
          updateLastMessage(undefined, node, asArray(chunk.tool_calls), trace)
        } else if (trace.length > 0) {
          appendTraceToCurrentAssistant(node || asString(trace[0]?.node) || 'agent', trace)
          attachMetadataToLastAssistant(metadata)
        }
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return
      }
      forceFlushContent()
      streamError.value = error instanceof Error ? error.message : 'Stream connection failed'
      if (assistantCreated) {
        updateLastMessage(streamError.value)
      }
    } finally {
      clearStreamTimeout()
      if (!signal.aborted) {
        forceFlushContent()
        attachCitationMapToLastFinalAssistant()
        isStreaming.value = false
        streamStartedAtMs.value = 0
        // EditorPane listens once per completed streamed turn to refresh its persisted patch markers.
        window.dispatchEvent(new CustomEvent('agent-turn-finished'))
        currentNode.value = ''
        loadedSessionId.value = targetSessionId ?? ''
        if (targetSessionId) {
          try {
            await sessionStore.load(userId)
          } catch {
            // Session reload is non-critical for the active stream result.
          }
        }
      }
    }
  }

  function clear() {
    streamAbortController?.abort()
    historyAbortController?.abort()
    streamAbortController = null
    historyAbortController = null
    clearStreamTimeout()
    messages.value = []
    contextMirror.value = []
    activeAgentMode.value = 'auto'
    isStreaming.value = false
    streamStartedAtMs.value = 0
    streamError.value = ''
    currentNode.value = ''
    loadedSessionId.value = ''
    currentKnowledgeSources.value = []
    currentCitationMap.value = {}
    pendingAttachments.value = []
    taskSuggestions.value = []
    suggestionsLoading.value = false
    suggestionRequestId += 1
    suggestionAbortController?.abort()
    suggestionAbortController = null
    useTaskListStore().clear()
  }

  // ------------------------------------------------------------------
  // 子 Agent 完成检测与唤醒（"死而复生"）
  // ------------------------------------------------------------------
  let childWatcherTimer: number | null = null
  let childWatcherUserId = ''
  let childWatcherSessionId = ''
  const seenChildStatus = new Map<string, ChildAgentRecord['status']>()

  function isTerminalChildStatus(status: ChildAgentRecord['status']) {
    return status === 'completed' || status === 'failed' || status === 'stopped'
  }

  function terminalChildStatusLabel(status: ChildAgentRecord['status']) {
    return {
      completed: '已完成',
      failed: '失败',
      stopped: '已停止',
    }[status] || status
  }

  async function wakeUpAgentForChild(child: ChildAgentRecord) {
    const title = child.name?.trim() || child.goal
    const summary = (child.summary || '').trim()
    let resultText = ''
    if (child.result !== undefined && child.result !== null) {
      resultText = typeof child.result === 'string'
        ? child.result
        : (() => {
          try {
            return JSON.stringify(child.result)
          } catch {
            return String(child.result)
          }
        })()
    }
    const prompt = [
      `【子任务完成提醒】后台子Agent「${title}」已完成（状态：${terminalChildStatusLabel(child.status)}）。`,
      summary ? `摘要：${summary}` : '',
      resultText ? `结果：${resultText}` : '',
      '请结合以上产出继续当前任务，给用户一个完整答复。',
    ].filter(Boolean).join('\n')
    try {
      await send(childWatcherUserId, childWatcherSessionId, prompt, '', 'auto', 'sandbox', {
        wakeup: true,
        childAgentEvent: {
          event_name: `child_agent.${child.status}`,
          child: {
            run_id: child.run_id,
            goal: child.goal,
            name: child.name,
            mode: child.mode,
            status: child.status,
            access_mode: child.access_mode,
            category: child.category,
            allowed_tools: child.allowed_tools,
            result: child.result,
            summary: child.summary,
            error: child.error,
          },
        },
      })
    } catch (error) {
      console.error('唤醒主 Agent 失败:', error)
    }
  }

  async function checkChildAgentsForWakeup() {
    if (!childWatcherSessionId || !childWatcherUserId) {
      return
    }
    let records: ChildAgentRecord[]
    try {
      const response = await fetchChildAgents(childWatcherSessionId)
      records = response.children
    } catch (error) {
      console.debug('子 Agent 完成检测失败:', error)
      return
    }
    for (const child of records) {
      const previous = seenChildStatus.get(child.run_id)
      if (previous === undefined) {
        // 首次见到:仅记录当前状态;若已是终态(历史会话),不触发唤醒
        seenChildStatus.set(child.run_id, child.status)
        continue
      }
      if (isTerminalChildStatus(previous)) {
        continue
      }
      if (!isTerminalChildStatus(child.status)) {
        seenChildStatus.set(child.run_id, child.status)
        continue
      }
      // 活动态 → 终态转变
      if (isStreaming.value) {
        // 主 Agent 流仍活动:SSE 已实时推送,保持 seen 为活动态,流结束后补触发
        continue
      }
      // 主 Agent 空闲:触发唤醒并记录终态,避免重复唤醒
      seenChildStatus.set(child.run_id, child.status)
      await wakeUpAgentForChild(child)
    }
  }

  function startChildAgentWatcher(userId: string, sessionId: string) {
    if (childWatcherTimer !== null) {
      window.clearInterval(childWatcherTimer)
      childWatcherTimer = null
    }
    childWatcherUserId = userId
    childWatcherSessionId = sessionId
    seenChildStatus.clear()
    void checkChildAgentsForWakeup()
    childWatcherTimer = window.setInterval(() => void checkChildAgentsForWakeup(), 2000)
  }

  function stopChildAgentWatcher() {
    if (childWatcherTimer !== null) {
      window.clearInterval(childWatcherTimer)
      childWatcherTimer = null
    }
    seenChildStatus.clear()
    childWatcherSessionId = ''
    childWatcherUserId = ''
  }

  function clearStreamTimeout() {
    if (streamTimeoutId !== null) {
      window.clearTimeout(streamTimeoutId)
      streamTimeoutId = null
    }
  }

  function resetStreamTimeout() {
    clearStreamTimeout()
    streamTimeoutId = window.setTimeout(() => {
      cancelStream()
    }, streamTimeoutMs)
  }

  /**
   * Cancel the current streaming response.
   * Aborts the fetch, flushes buffered content, and marks the last assistant
   * message as 'interrupted' so it's preserved in context.
   */
  function cancelStream() {
    if (!isStreaming.value) return
    clearStreamTimeout()
    streamAbortController?.abort()
    forceFlushContent()
    isStreaming.value = false
    const lastAssistant = findLastAssistant()
    if (lastAssistant) {
      lastAssistant.node = 'interrupted'
    }
    attachCitationMapToLastFinalAssistant()
    currentNode.value = ''
  }

  function addPendingAttachment(attachment: AgentUploadedAttachment) {
    pendingAttachments.value.push(attachment)
  }

  function removeAttachmentLocal(attachmentId: string) {
    pendingAttachments.value = pendingAttachments.value.filter((item) => item.attachment_id !== attachmentId)
    messages.value = messages.value.map((message) => {
      if (!message.attachments?.length) {
        return message
      }
      return {
        ...message,
        attachments: message.attachments.filter((item) => item.attachment_id !== attachmentId),
      }
    })
  }

  async function deleteAttachment(attachment: AgentUploadedAttachment) {
    const attachmentId = attachment.attachment_id
    if (!attachmentId) {
      return
    }
    removeAttachmentLocal(attachmentId)

    const userId = attachment.user_id
    const sessionId = attachment.session_id
    if (!userId || !sessionId) {
      return
    }
    try {
      await deleteAgentAttachment(userId, sessionId, attachmentId)
    } catch (error) {
      console.error('删除上传附件失败:', error)
    }
  }

  return {
    messages,
    isStreaming,
    streamStartedAtMs,
    currentNode,
    streamError,
    loadedSessionId,
    contextMirror,
    activeAgentMode,
    pendingAttachments,
    taskSuggestions,
    suggestionsLoading,
    lastMessage,
    canSend,
    loadHistory,
    refreshTaskSuggestions,
    send,
    cancelStream,
    clear,
    addPendingAttachment,
    deleteAttachment,
    currentKnowledgeSources,
    currentCitationMap,
    startChildAgentWatcher,
    stopChildAgentWatcher,
  }
})
