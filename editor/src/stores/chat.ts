/*
 * Agent chat message store.
 *
 * Usage:
 * Owns streamed Agent messages for the editor right panel. The implementation
 * mirrors console chat behavior while staying typed for the editor front-end.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { deleteAgentAttachment, fetchTaskSuggestions, streamPrompt } from '@/api/agent'
import type { AgentAccessMode, AgentAttachmentUploadResponse, AgentLoopMode } from '@/api/agent'
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
    asString(trace.tool_name),
    asString(trace.human_readable),
  ].join('|')
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<AgentChatMessage[]>([])
  const isStreaming = ref(false)
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
  let historyRequestId = 0
  let pendingContent = ''
  let flushTimer: number | null = null
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

  async function loadHistory(sessionId: string, userId: string, limit = 50) {
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
        })
        .map((message) => ({
          role: message.role === 'tool' ? 'assistant' : message.role as AgentChatMessage['role'],
          content: message.content,
          message_id: message.message_id,
          node: asString(message.metadata?.node),
          tool_calls: message.tool_calls,
          metadata: message.metadata ?? {},
          trace: asTrace(message.metadata?.trace),
          created_at: message.created_at,
          reference: asString(message.metadata?.reference) || undefined,
        }))
      loadedSessionId.value = sessionId
      void useTaskListStore().load(sessionId)
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
    suggestionsLoading.value = true
    try {
      const result = await fetchTaskSuggestions(userId, sessionId)
      if (requestId === suggestionRequestId) {
        taskSuggestions.value = result.suggestions ?? []
      }
    } catch (error) {
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
    suggestionRequestId += 1
    appendMessage({
      role: 'user',
      content: prompt,
      reference: reference || undefined,
      attachments: attachmentsForTurn,
      created_at: new Date().toISOString(),
    })

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

        if (content) {
          ensureAssistant(node)
          if (chunk.type === 'delta') {
            appendStreamContent(content)
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
            }
          }
          attachMetadataToLastAssistant(metadata)
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
    streamError.value = ''
    currentNode.value = ''
    loadedSessionId.value = ''
    currentKnowledgeSources.value = []
    currentCitationMap.value = {}
    pendingAttachments.value = []
    taskSuggestions.value = []
    suggestionsLoading.value = false
    suggestionRequestId += 1
    useTaskListStore().clear()
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
  }
})
