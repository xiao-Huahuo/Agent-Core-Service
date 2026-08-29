/*
 * Agent chat message store.
 *
 * Usage:
 * Owns streamed Agent messages for the editor right panel. The implementation
 * mirrors console chat behavior while staying typed for the editor front-end.
 */

import { computed, ref } from 'vue'
import { acceptHMRUpdate, defineStore } from 'pinia'

import { deleteAgentAttachment, fetchChildAgents, fetchTaskSuggestions, streamPrompt } from '@/api/agent'
import type { AgentAccessMode, AgentAttachmentUploadResponse, AgentLoopMode, ChildAgentRecord } from '@/api/agent'
import { fetchMessages } from '@/api/session'
import type { SessionMessageRecord } from '@/api/session'
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

/** Backend-reported token usage for the exact working context sent to the model. */
export interface AgentContextUsage {
  current_tokens: number
  max_context_tokens: number
  trigger_tokens: number
  target_tokens: number
}

/** Compression lifecycle rendered independently from generic Agent thinking. */
export type AgentCompressionStatus = 'idle' | 'compressing' | 'failed'

/** Runtime state for one tool call while its preview and result are streamed. */
interface ToolCallLifecycle {
  /** Stable backend call identity, also used as the rendered toolbar key. */
  key: string
  /** Action message that owns this call for the whole lifecycle. */
  message: AgentChatMessage
  /** Browser time when the preview first entered reactive state. */
  startedAtMs: number
  /** Prevents duplicate aggregate traces from scheduling the same result twice. */
  phase: 'pending' | 'ending' | 'completed'
  /** Most complete result received while the perceptible preview window is open. */
  endTrace?: Record<string, unknown>
  /** Pending completion timer, cleared when a stream is cancelled. */
  completionTimer?: number
  /** Resolves the per-call completion wait exactly once. */
  resolveCompletion?: () => void
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

function asContextUsage(value: unknown): AgentContextUsage | null {
  const record = asRecord(value)
  const currentTokens = asFiniteNumber(record.current_tokens)
  const maxContextTokens = asFiniteNumber(record.max_context_tokens)
  if (currentTokens === null || maxContextTokens === null || maxContextTokens <= 0) return null
  return {
    current_tokens: Math.max(0, currentTokens),
    max_context_tokens: maxContextTokens,
    trigger_tokens: Math.max(0, asFiniteNumber(record.trigger_tokens) ?? 0),
    target_tokens: Math.max(0, asFiniteNumber(record.target_tokens) ?? 0),
  }
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

/**
 * Builds one isolated chat store.  A queue task and the normal Agent page may
 * stream at the same time, so they must never share an AbortController or
 * message buffer.
 */
const createChatStore = (storeId: string) => defineStore(storeId, () => {
  const messages = ref<AgentChatMessage[]>([])
  const isStreaming = ref(false)
  /** Timestamp shared by all loading indicators for the active user turn. */
  const streamStartedAtMs = ref(0)
  const currentNode = ref('')
  const streamError = ref('')
  const loadedSessionId = ref('')
  const contextMirror = ref<unknown[]>([])
  const contextUsage = ref<AgentContextUsage | null>(null)
  const compressionStatus = ref<AgentCompressionStatus>('idle')
  const activeAgentMode = ref<AgentLoopMode>('auto')
  const currentKnowledgeSources = ref<SourceItem[]>([])
  const currentCitationMap = ref<Record<string, SourceItem>>({})
  const pendingAttachments = ref<AgentUploadedAttachment[]>([])
  const taskSuggestions = ref<string[]>([])
  const suggestionsLoading = ref(false)
  const loadingHistory = ref(false)
  /** Session currently owned by this isolated store's stream. */
  const streamingSessionId = ref('')

  let streamAbortController: AbortController | null = null
  let historyAbortController: AbortController | null = null
  let streamTimeoutId: number | null = null
  const streamTimeoutMs = 10 * 60 * 1000 // 10 minutes sliding window
  let suggestionRequestId = 0
  let suggestionAbortController: AbortController | null = null
  let historyRequestId = 0
  let historySyncing = false
  /** Buffered text is keyed by its owner so a later action cannot steal it. */
  const pendingContent = new Map<AgentChatMessage, string>()
  let flushTimer: number | null = null
  let turnStartedAtMs = 0
  const contentFlushMs = 50
  /** Fast tools keep one perceptible shimmer window before the result replaces it. */
  const toolPreviewMinMs = 800

  const lastMessage = computed(() => messages.value.length > 0 ? messages.value[messages.value.length - 1] : null)
  const canSend = computed(() => !isStreaming.value)

  function appendMessage(message: AgentChatMessage) {
    messages.value.push({ ...message })
  }

  function setContextUsage(value: unknown) {
    // Replace the meter only with a complete backend-reported usage payload.

    const parsed = asContextUsage(value)
    if (parsed) contextUsage.value = parsed
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

  /** Merges stream metadata into the message that received the same event. */
  function attachMetadataToMessage(message: AgentChatMessage, metadata: Record<string, unknown>) {
    if (Object.keys(metadata).length === 0) {
      return
    }
    const existing = message.metadata ?? {}
    const existingCitationMap = existing.citation_map as Record<string, unknown> | undefined
    const newCitationMap = metadata.citation_map as Record<string, unknown> | undefined
    const mergedCitationMap =
      existingCitationMap && newCitationMap
        ? { ...existingCitationMap, ...newCitationMap }
        : undefined
    message.metadata = {
      ...existing,
      ...metadata,
      ...(mergedCitationMap ? { citation_map: mergedCitationMap } : {}),
    }
  }

  /** Compatibility helper for stream-final metadata outside a node-local path. */
  function attachMetadataToLastAssistant(metadata: Record<string, unknown>) {
    const last = findLastAssistant()
    if (last) {
      attachMetadataToMessage(last, metadata)
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

  /** Flushes text only into the message captured when each delta arrived. */
  function flushStreamContent(target?: AgentChatMessage) {
    if (!target) {
      flushTimer = null
    }
    const entries = target
      ? [[target, pendingContent.get(target) ?? ''] as const]
      : Array.from(pendingContent.entries())
    for (const [message, content] of entries) {
      if (content) {
        message.content += content
      }
      pendingContent.delete(message)
    }
  }

  /** Schedules one shared render-friendly flush for all currently active owners. */
  function scheduleContentFlush() {
    if (flushTimer !== null) {
      return
    }
    flushTimer = window.setTimeout(flushStreamContent, contentFlushMs)
  }

  /** Buffers a delta against its immutable owner rather than the latest message. */
  function appendStreamContent(message: AgentChatMessage, content: string) {
    pendingContent.set(message, (pendingContent.get(message) ?? '') + content)
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

  /** Discards superseded buffered deltas for one authoritative full response. */
  function cancelPendingFlush(target?: AgentChatMessage) {
    if (target) {
      pendingContent.delete(target)
    } else {
      pendingContent.clear()
    }
    if (flushTimer !== null && pendingContent.size === 0) {
      window.clearTimeout(flushTimer)
      flushTimer = null
    }
  }

  /** Immediately commits buffered text, preserving other owners if one is selected. */
  function forceFlushContent(target?: AgentChatMessage) {
    if (flushTimer !== null) {
      window.clearTimeout(flushTimer)
      flushTimer = null
    }
    flushStreamContent(target)
    if (pendingContent.size > 0) {
      scheduleContentFlush()
    }
  }

  /** Convert persisted session rows into the exact message shape used by the Agent page. */
  function restoreHistoryMessages(history: SessionMessageRecord[]): AgentChatMessage[] {
    return history
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
      messages.value = restoreHistoryMessages(history)
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

  /**
   * Refresh a fixed external session without clearing the mounted Agent page.
   * Existing message objects are updated in place so scrolling and expanded
   * tool rows remain stable while queue workers persist new output.
   */
  async function syncHistory(sessionId: string, userId: string) {
    if (historySyncing || loadedSessionId.value !== sessionId) return
    historySyncing = true
    try {
      const restored = restoreHistoryMessages(await fetchMessages(sessionId, userId))
      const existingById = new Map(messages.value.map((message) => [message.message_id, message]))
      messages.value = restored.map((message) => {
        const existing = message.message_id ? existingById.get(message.message_id) : undefined
        if (!existing) return message
        Object.assign(existing, message)
        return existing
      })
    } catch (error) {
      console.debug('静默同步会话历史失败:', error)
    } finally {
      historySyncing = false
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
    compressionStatus.value = 'idle'
    streamingSessionId.value = targetSessionId || ''
    if (targetSessionId) sessionStore.setSessionStreaming(targetSessionId, true)
    streamError.value = ''
    activeAgentMode.value = agentMode
    currentKnowledgeSources.value = []
    currentCitationMap.value = {}

    // Start stream timeout — auto-cancel if stream stalls for >10 minutes
    resetStreamTimeout()

    const bufferedTraces: Array<Record<string, unknown>> = []
    let activeNode = ''
    let activeAssistant: AgentChatMessage | null = null
    let anonymousToolSequence = 0
    const toolLifecycles = new Map<string, ToolCallLifecycle>()
    const pendingToolCompletions = new Set<Promise<void>>()

    /** Returns the node-owned message and flushes the previous node before switching. */
    function ensureAssistant(node: string): AgentChatMessage {
      if (activeAssistant && activeNode === node) {
        return activeAssistant
      }
      if (activeAssistant) {
        forceFlushContent(activeAssistant)
      }
      const message: AgentChatMessage = {
        role: 'assistant',
        content: '',
        node,
        tool_calls: [],
        trace: [...bufferedTraces],
        metadata: { turn_started_at_ms: streamStartedAtMs.value },
        created_at: new Date().toISOString(),
      }
      appendMessage(message)
      activeNode = node
      activeAssistant = messages.value[messages.value.length - 1] ?? message
      bufferedTraces.length = 0
      return activeAssistant
    }

    /** Appends traces idempotently to their captured owner. */
    function appendTraceToMessage(message: AgentChatMessage, trace: Array<Record<string, unknown>>) {
      message.trace ??= []
      const seen = new Set(message.trace.map(traceIdentity))
      const fresh = trace.filter((item) => {
        const key = traceIdentity(item)
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
      message.trace.push(...fresh)
    }

    /** Appends non-tool traces to the currently active node message. */
    function appendTraceToCurrentAssistant(node: string, trace: Array<Record<string, unknown>>) {
      appendTraceToMessage(ensureAssistant(node), trace)
    }

    /** Finds a known call by id, or an id-less result's oldest compatible call. */
    function findToolLifecycle(trace: Record<string, unknown>): ToolCallLifecycle | undefined {
      const callId = asString(trace.tool_call_id)
      if (callId) {
        return toolLifecycles.get(callId)
      }
      if (trace.event !== 'tool_call_end') {
        return undefined
      }
      const toolName = asString(trace.tool_name)
      return Array.from(toolLifecycles.values()).find((lifecycle) => {
        if (lifecycle.phase === 'completed') return false
        const start = lifecycle.message.trace?.find((item) => asString(item.tool_call_id) === lifecycle.key)
        return asString(start?.tool_name) === toolName
      })
    }

    /** Finds the oldest pending preview created before a provider supplied its id. */
    function findAnonymousToolLifecycle(toolName: string): ToolCallLifecycle | undefined {
      return Array.from(toolLifecycles.values()).find((lifecycle) => {
        if (lifecycle.phase === 'completed' || !lifecycle.key.startsWith('anonymous:')) return false
        const start = lifecycle.message.trace?.find((item) => asString(item.tool_call_id) === lifecycle.key)
        return asString(start?.tool_name) === toolName
      })
    }

    /** Upserts a running trace without moving an existing call to a later message. */
    function upsertToolStart(trace: Record<string, unknown>): ToolCallLifecycle | null {
      const toolName = asString(trace.tool_name)
      if (!toolName) return null
      const callId = asString(trace.tool_call_id)
      const existing = findToolLifecycle(trace) || (callId ? findAnonymousToolLifecycle(toolName) : undefined)
      if (existing) {
        if (callId && !toolLifecycles.has(callId)) {
          toolLifecycles.delete(existing.key)
          toolLifecycles.set(callId, existing)
        }
        if (existing.phase !== 'completed') {
          appendTraceToMessage(existing.message, [{ ...trace, tool_call_id: existing.key }])
        }
        return existing
      }
      const key = callId || `anonymous:${toolName}:${++anonymousToolSequence}`
      const message = ensureAssistant('action')
      appendTraceToMessage(message, [{ ...trace, tool_call_id: key }])
      const lifecycle: ToolCallLifecycle = {
        key,
        message,
        startedAtMs: nowMs(),
        phase: 'pending',
      }
      toolLifecycles.set(key, lifecycle)
      return lifecycle
    }

    /** Commits a received result to its original toolbar and resolves its waiter. */
    function finishToolLifecycle(lifecycle: ToolCallLifecycle) {
      if (lifecycle.phase === 'completed') return
      if (lifecycle.completionTimer !== undefined) {
        window.clearTimeout(lifecycle.completionTimer)
        lifecycle.completionTimer = undefined
      }
      const resolve = lifecycle.resolveCompletion
      lifecycle.resolveCompletion = undefined
      try {
        if (lifecycle.endTrace) {
          appendTraceToMessage(lifecycle.message, [lifecycle.endTrace])
        }
      } finally {
        // A render/update exception must never leave send() awaiting forever.
        lifecycle.phase = 'completed'
        resolve?.()
      }
    }

    /**
     * Defers only sub-frame results. This lets Vue paint the locked running row
     * while independent tool calls and later Agent messages keep streaming.
     */
    function scheduleToolEnd(trace: Record<string, unknown>) {
      let lifecycle = findToolLifecycle(trace)
      if (!lifecycle) {
        lifecycle = upsertToolStart({
          node: 'action',
          event: 'tool_call_start',
          tool_call_id: asString(trace.tool_call_id),
          tool_name: asString(trace.tool_name),
          display_name: asString(trace.display_name),
          tool_args_summary: asString(trace.tool_args_summary),
          terminal_command: asString(trace.terminal_command),
          chat_visible: true,
        }) ?? undefined
      }
      if (!lifecycle || lifecycle.phase === 'completed') return
      const knownStart = lifecycle.message.trace?.find((item) => (
        item.event === 'tool_call_start' && asString(item.tool_call_id) === lifecycle.key
      ))
      lifecycle.endTrace = {
        ...trace,
        tool_call_id: lifecycle.key,
        tool_name: asString(trace.tool_name) || asString(knownStart?.tool_name),
        display_name: asString(trace.display_name) || asString(knownStart?.display_name),
        tool_args_summary: asString(trace.tool_args_summary) || asString(knownStart?.tool_args_summary),
      }
      if (lifecycle.phase === 'ending') return
      lifecycle.phase = 'ending'
      const delayMs = Math.max(0, toolPreviewMinMs - (nowMs() - lifecycle.startedAtMs))
      if (delayMs === 0) {
        finishToolLifecycle(lifecycle)
        return
      }
      const completion = new Promise<void>((resolve) => {
        lifecycle.resolveCompletion = resolve
        lifecycle.completionTimer = window.setTimeout(() => finishToolLifecycle(lifecycle), delayMs)
      })
      pendingToolCompletions.add(completion)
      void completion.then(() => pendingToolCompletions.delete(completion))
    }

    /** Reduces individual and aggregate action traces through one lifecycle path. */
    function handleActionTraces(trace: Array<Record<string, unknown>>) {
      for (const item of trace) {
        if (item.event === 'tool_call_start') {
          upsertToolStart(item)
        } else if (item.event === 'tool_call_end') {
          scheduleToolEnd(item)
        } else {
          appendTraceToCurrentAssistant('action', [item])
        }
      }
    }

    signal.addEventListener('abort', () => {
      // A result already received must not disappear merely because the user
      // cancels during its short preview window.
      for (const lifecycle of toolLifecycles.values()) {
        if (lifecycle.phase === 'ending') finishToolLifecycle(lifecycle)
      }
    }, { once: true })

    try {
      if (!targetSessionId) {
        targetSessionId = await sessionStore.create(userId)
        sessionStore.select(targetSessionId)
        streamingSessionId.value = targetSessionId
        sessionStore.setSessionStreaming(targetSessionId, true)
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
        const reportedUsage = asContextUsage(metadata.context_usage)
        if (reportedUsage) contextUsage.value = reportedUsage
        if (chunk.type === 'compression_started') compressionStatus.value = 'compressing'
        if (chunk.type === 'compression_applied' || chunk.type === 'compression_cancelled') compressionStatus.value = 'idle'
        if (chunk.type === 'compression_failed') compressionStatus.value = 'failed'
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
            handleActionTraces(trace)
          }
          continue
        }

        const announcedToolCalls = asArray(chunk.tool_calls)

        if (content) {
          const message = ensureAssistant(node)
          if (chunk.type === 'delta') {
            appendStreamContent(message, content)
            markThinkingDurationIfNeeded(message, true)
          } else {
            cancelPendingFlush(message)
            // A complete response is authoritative when it extends or repairs
            // the streamed prefix; shorter unrelated text never erases it.
            if (!message.content) {
              message.content = content
            } else if (
              content.startsWith(message.content)
              || content.length > message.content.length
            ) {
              message.content = content
            }
            markThinkingDurationIfNeeded(message)
          }
          attachMetadataToMessage(message, metadata)
          const backendFirstDeltaMs = asFiniteNumber(asRecord(message.metadata?.latency).first_agent_delta_ms)
          if (backendFirstDeltaMs !== null) {
            message.metadata = {
              ...(message.metadata ?? {}),
              backend_first_delta_seconds: Math.round((backendFirstDeltaMs / 1000) * 10) / 10,
            }
          }
          message.tool_calls = announcedToolCalls
          appendTraceToMessage(message, trace)
        }

        // Tool announcements are handled after content from the same envelope,
        // so creating the action row can never hide or steal Agent prose.
        for (const toolCall of announcedToolCalls.map(asRecord)) {
          const toolName = asString(toolCall.name)
          if (!toolName) continue
          upsertToolStart({
            node: 'action',
            event: 'tool_call_start',
            tool_call_id: asString(toolCall.id),
            tool_name: toolName,
            display_name: '',
            tool_args_summary: JSON.stringify(toolCall.args ?? {}),
            human_readable: `正在调用工具「${toolName}」`,
            chat_visible: true,
          })
        }

        if (!content && announcedToolCalls.length === 0 && trace.length > 0) {
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
      const errorMessage = ensureAssistant('error')
      errorMessage.content = streamError.value
    } finally {
      clearStreamTimeout()
      if (!signal.aborted) {
        await Promise.all(Array.from(pendingToolCompletions))
        forceFlushContent()
        attachCitationMapToLastFinalAssistant()
        isStreaming.value = false
        if (targetSessionId) sessionStore.setSessionStreaming(targetSessionId, false)
        streamingSessionId.value = ''
        streamStartedAtMs.value = 0
        // EditorPane listens once per completed streamed turn to refresh its persisted patch markers.
        window.dispatchEvent(new CustomEvent('agent-turn-finished'))
        currentNode.value = ''
        loadedSessionId.value = targetSessionId ?? ''
        if (targetSessionId) {
          try {
            await sessionStore.load(userId, true)
          } catch {
            // Session reload is non-critical for the active stream result.
          }
          // Suggestions belong to the completed persisted turn, so refresh
          // them here for every chat surface instead of relying on a UI watcher.
          void refreshTaskSuggestions(userId, targetSessionId)
          sessionStore.settleFreshSession(targetSessionId)
        }
      }
    }
  }

  function clear() {
    streamAbortController?.abort()
    historyAbortController?.abort()
    cancelPendingFlush()
    streamAbortController = null
    historyAbortController = null
    clearStreamTimeout()
    messages.value = []
    contextMirror.value = []
    contextUsage.value = null
    compressionStatus.value = 'idle'
    activeAgentMode.value = 'auto'
    isStreaming.value = false
    if (streamingSessionId.value) useSessionStore().setSessionStreaming(streamingSessionId.value, false)
    streamingSessionId.value = ''
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
   * Aborts the fetch and flushes buffered content. Agent prose is marked as
   * interrupted, while action/child rows keep their renderer-specific node.
   */
  function cancelStream() {
    if (!isStreaming.value) return
    clearStreamTimeout()
    streamAbortController?.abort()
    forceFlushContent()
    isStreaming.value = false
    const lastAssistant = findLastAssistant()
    if (lastAssistant && lastAssistant.node !== 'action' && lastAssistant.node !== 'child_agent') {
      lastAssistant.node = 'interrupted'
    }
    attachCitationMapToLastFinalAssistant()
    currentNode.value = ''
  }

  function addPendingAttachment(attachment: AgentUploadedAttachment) {
    pendingAttachments.value.push(attachment)
  }

  function replacePendingAttachment(attachmentId: string, attachment: AgentUploadedAttachment) {
    pendingAttachments.value = pendingAttachments.value.map((item) => (
      item.attachment_id === attachmentId ? attachment : item
    ))
  }

  function updateAttachmentLocal(attachment: AgentUploadedAttachment) {
    pendingAttachments.value = pendingAttachments.value.map((item) => (
      item.attachment_id === attachment.attachment_id ? attachment : item
    ))
    messages.value = messages.value.map((message) => ({
      ...message,
      attachments: message.attachments?.map((item) => (
        item.attachment_id === attachment.attachment_id ? attachment : item
      )),
    }))
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

    if (attachmentId.startsWith('local-upload-')) {
      return
    }

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
    contextUsage,
    compressionStatus,
    activeAgentMode,
    pendingAttachments,
    taskSuggestions,
    suggestionsLoading,
    streamingSessionId,
    lastMessage,
    canSend,
    setContextUsage,
    loadHistory,
    syncHistory,
    refreshTaskSuggestions,
    send,
    cancelStream,
    clear,
    addPendingAttachment,
    replacePendingAttachment,
    updateAttachmentLocal,
    deleteAttachment,
    currentKnowledgeSources,
    currentCitationMap,
    startChildAgentWatcher,
    stopChildAgentWatcher,
  }
})

/** Minimal incremental payload relayed between the two Electron Agent views. */
interface AgentChatWindowState {
  sessionId: string
  messageCount: number
  messagePatches: Array<{ index: number; message: AgentChatMessage }>
  isStreaming: boolean
  streamStartedAtMs: number
  currentNode: string
  streamError: string
  loadedSessionId: string
  activeAgentMode: AgentLoopMode
  pendingAttachments: AgentUploadedAttachment[]
  taskSuggestions: string[]
  suggestionsLoading: boolean
  streamingSessionId: string
  contextUsage: AgentContextUsage | null
  compressionStatus: AgentCompressionStatus
}

type AgentChatStoreInstance = ReturnType<ReturnType<typeof createChatStore>>

const windowSyncedStores = new Map<string, AgentChatStoreInstance>()
const previousMessageSignatures = new Map<string, string[]>()
const previousStateSignatures = new Map<string, string>()
const applyingRemoteState = new Set<string>()
let windowSyncListenerInstalled = false

/** Clone Vue state into Electron-safe plain data without sending the full history. */
function cloneForWindowSync<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

/** Build and send only messages changed since the previous render flush. */
function broadcastChatState(sessionId: string, store: AgentChatStoreInstance, forceFull = false) {
  if (!window.agentEditorDesktop?.windowSync || applyingRemoteState.has(sessionId)) return
  const nextMessageSignatures = store.messages.map((message) => JSON.stringify(message))
  const previous = previousMessageSignatures.get(sessionId) ?? []
  const messagePatches = store.messages.flatMap((message, index) => (
    forceFull || nextMessageSignatures[index] !== previous[index]
      ? [{ index, message: cloneForWindowSync(message) }]
      : []
  ))
  const scalarState = {
    isStreaming: store.isStreaming,
    streamStartedAtMs: store.streamStartedAtMs,
    currentNode: store.currentNode,
    streamError: store.streamError,
    loadedSessionId: store.loadedSessionId,
    activeAgentMode: store.activeAgentMode,
    pendingAttachments: store.pendingAttachments,
    taskSuggestions: store.taskSuggestions,
    suggestionsLoading: store.suggestionsLoading,
    streamingSessionId: store.streamingSessionId,
    contextUsage: store.contextUsage,
    compressionStatus: store.compressionStatus,
  }
  const stateSignature = JSON.stringify(scalarState)
  if (!forceFull && messagePatches.length === 0 && previous.length === store.messages.length
    && previousStateSignatures.get(sessionId) === stateSignature) return

  previousMessageSignatures.set(sessionId, nextMessageSignatures)
  previousStateSignatures.set(sessionId, stateSignature)
  window.agentEditorDesktop.windowSync('chat-state', {
    sessionId,
    messageCount: store.messages.length,
    messagePatches,
    ...cloneForWindowSync(scalarState),
  } satisfies AgentChatWindowState)
}

/** Apply one remote incremental snapshot without echoing it back to its owner. */
function applyRemoteChatState(payload: AgentChatWindowState) {
  if (!payload.sessionId || !Number.isInteger(payload.messageCount)) return
  const store = useSessionChatStore(payload.sessionId)
  const messages = store.messages.slice(0, payload.messageCount)
  for (const patch of payload.messagePatches ?? []) {
    if (Number.isInteger(patch.index) && patch.index >= 0 && patch.index < payload.messageCount) {
      messages[patch.index] = cloneForWindowSync(patch.message)
    }
  }
  if (messages.some((message) => !message)) return

  applyingRemoteState.add(payload.sessionId)
  store.$patch((state) => {
    state.messages = messages
    state.isStreaming = Boolean(payload.isStreaming)
    state.streamStartedAtMs = Number.isFinite(payload.streamStartedAtMs) ? payload.streamStartedAtMs : 0
    state.currentNode = payload.currentNode || ''
    state.streamError = payload.streamError || ''
    state.loadedSessionId = payload.loadedSessionId || ''
    state.activeAgentMode = payload.activeAgentMode
    state.pendingAttachments = payload.pendingAttachments ?? []
    state.taskSuggestions = payload.taskSuggestions ?? []
    state.suggestionsLoading = Boolean(payload.suggestionsLoading)
    state.streamingSessionId = payload.streamingSessionId || ''
    state.contextUsage = payload.contextUsage ?? null
    state.compressionStatus = payload.compressionStatus || 'idle'
  })
  previousMessageSignatures.set(payload.sessionId, messages.map((message) => JSON.stringify(message)))
  previousStateSignatures.set(payload.sessionId, JSON.stringify({
    isStreaming: store.isStreaming,
    streamStartedAtMs: store.streamStartedAtMs,
    currentNode: store.currentNode,
    streamError: store.streamError,
    loadedSessionId: store.loadedSessionId,
    activeAgentMode: store.activeAgentMode,
    pendingAttachments: store.pendingAttachments,
    taskSuggestions: store.taskSuggestions,
    suggestionsLoading: store.suggestionsLoading,
    streamingSessionId: store.streamingSessionId,
    contextUsage: store.contextUsage,
    compressionStatus: store.compressionStatus,
  }))
  window.setTimeout(() => applyingRemoteState.delete(payload.sessionId), 0)
}

/** Install the single renderer listener used by every session-scoped store. */
function installChatWindowSyncListener() {
  if (windowSyncListenerInstalled || !window.agentEditorDesktop?.onWindowSync) return
  windowSyncListenerInstalled = true
  window.agentEditorDesktop.onWindowSync(({ type, value }) => {
    const payload = value && typeof value === 'object' ? value as Record<string, unknown> : {}
    const sessionId = typeof payload.sessionId === 'string' ? payload.sessionId : ''
    if (type === 'chat-state') {
      applyRemoteChatState(payload as unknown as AgentChatWindowState)
    } else if (type === 'chat-sync-request' && sessionId) {
      const store = windowSyncedStores.get(sessionId)
      // A newly-created mirror has no authoritative state yet. Let the window
      // that loaded history or owns the live stream answer the request.
      if (store && (store.loadedSessionId === sessionId || store.messages.length > 0 || store.isStreaming)) {
        broadcastChatState(sessionId, store, true)
      }
    } else if (type === 'chat-cancel' && sessionId) {
      windowSyncedStores.get(sessionId)?.cancelStream()
    }
  })
}

/** Register one persisted session for incremental cross-window mirroring. */
function registerChatWindowSync(sessionId: string, store: AgentChatStoreInstance) {
  if (!sessionId || windowSyncedStores.get(sessionId) === store) return
  windowSyncedStores.set(sessionId, store)
  previousMessageSignatures.set(sessionId, store.messages.map((message) => JSON.stringify(message)))
  store.$subscribe(() => broadcastChatState(sessionId, store), { detached: true, flush: 'post' })
  installChatWindowSyncListener()
  window.agentEditorDesktop?.windowSync?.('chat-sync-request', { sessionId })
}

/** Ask the renderer that owns a stream to cancel it, then update this mirror. */
export function cancelSessionChatAcrossWindows(sessionId: string, store: AgentChatStoreInstance) {
  window.agentEditorDesktop?.windowSync?.('chat-cancel', { sessionId })
  store.cancelStream()
}

/** The primary Agent page chat store. */
export const useChatStore = createChatStore('chat')

// Pinia setup stores keep their action closures after a component-only Vite
// update unless the store explicitly accepts the replacement definition.
if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useChatStore, import.meta.hot))
}

/**
 * Returns the stable Pinia store for one persisted session.  Embedded queue
 * views use this instead of the primary page's singleton store.
 */
export function useSessionChatStore(sessionId: string) {
  const store = createChatStore(`chat-session:${sessionId}`)()
  registerChatWindowSync(sessionId, store)
  return store
}
