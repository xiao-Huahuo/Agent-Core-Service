/*
 * Lazy cross-session observability history loader.
 *
 * Usage:
 * RAG and latency cards independently select a recent user-turn range and call
 * loadRag()/loadLatency(). Only the selected range is requested and computed.
 */

import { computed, ref } from 'vue'

import { fetchUserMessageHistory, type SessionMessageRecord, type SessionRecord } from '@/api/session'
import { buildAllSessionLatencyTurns, type ObsSessionHistory } from '@/composable/useObsData'
import { buildRagHistory } from '@/composable/useObsMetrics'
import type { AgentChatMessage } from '@/stores/chat'

/** Supported recent-turn ranges shared by both Dashboard curve selectors. */
export const OBS_HISTORY_RANGE_OPTIONS = [5, 10, 20, 50, 100, 200, 500, 1000, 'all'] as const
export type ObsHistoryRange = typeof OBS_HISTORY_RANGE_OPTIONS[number]

/** Format a selector value with its classifier and measured subject. */
export function formatObsHistoryRange(
  range: ObsHistoryRange,
  classifier: '次' | '条',
  subject: 'RAG' | 'message',
): string {
  return range === 'all' ? `全部 ${subject}` : `最近 ${range} ${classifier} ${subject}`
}

const ragMessages = ref<AgentChatMessage[]>([])
const latencyMessages = ref<AgentChatMessage[]>([])
const latencySessions = ref<ObsSessionHistory[]>([])
const ragLoading = ref(false)
const latencyLoading = ref(false)
const ragError = ref('')
const latencyError = ref('')
const ragLoaded = ref(false)
const latencyLoaded = ref(false)
const ragLimit = ref<ObsHistoryRange>(20)
const latencyLimit = ref<ObsHistoryRange>(20)

let ragRequestId = 0
let latencyRequestId = 0
let ragLoadedUserId = ''
let latencyLoadedUserId = ''
let activeRagKey = ''
let activeLatencyKey = ''
let activeRagPromise: Promise<void> | null = null
let activeLatencyPromise: Promise<void> | null = null
const activeFetches = new Map<string, Promise<SessionMessageRecord[]>>()

/** Convert a persisted message to the same observability shape used by chat history. */
function normalizeMessage(message: SessionMessageRecord): AgentChatMessage | null {
  const metadata = message.metadata ?? {}
  if (message.role === 'tool' && metadata.node !== 'action') return null
  if (metadata.node === 'planner' || metadata.node === 'observation') return null
  if (
    message.role === 'assistant'
    && !message.content
    && (!message.tool_calls || message.tool_calls.length === 0)
    && metadata.node !== 'action'
  ) {
    return null
  }
  return {
    role: message.role === 'tool' ? 'assistant' : message.role as AgentChatMessage['role'],
    content: message.content,
    message_id: message.message_id,
    node: typeof metadata.node === 'string' ? metadata.node : '',
    tool_calls: message.tool_calls,
    metadata,
    trace: Array.isArray(metadata.trace) ? metadata.trace as Record<string, unknown>[] : [],
    created_at: message.created_at,
  }
}

/** Group chronological messages by session without pairing turns across sessions. */
function groupSessions(
  history: AgentChatMessage[],
  records: SessionMessageRecord[],
  sessionRecords: SessionRecord[],
): ObsSessionHistory[] {
  const names = new Map(sessionRecords.map((session) => [session.session_id, session.session_name]))
  const sessionIds = new Map(records.map((record) => [record.message_id, record.session_id]))
  const grouped = new Map<string, ObsSessionHistory>()
  for (const message of history) {
    const sessionId = sessionIds.get(message.message_id || '') || ''
    if (!sessionId) continue
    const group = grouped.get(sessionId) ?? {
      sessionId,
      sessionName: names.get(sessionId) || sessionId,
      messages: [],
    }
    group.messages.push(message)
    grouped.set(sessionId, group)
  }
  return [...grouped.values()]
}

/** Convert the "all" selector value to the omitted REST/gRPC limit convention. */
function numericLimit(range: ObsHistoryRange): number | undefined {
  return range === 'all' ? undefined : range
}

/** Share identical in-flight HTTP requests between the two charts. */
function fetchRange(
  userId: string,
  sessionRecords: SessionRecord[],
  range: ObsHistoryRange,
): Promise<SessionMessageRecord[]> {
  const key = `${userId}:${range}`
  const active = activeFetches.get(key)
  if (active) return active
  const request = fetchUserMessageHistory(userId, numericLimit(range))
  activeFetches.set(key, request)
  const clearRequest = () => {
    if (activeFetches.get(key) === request) activeFetches.delete(key)
  }
  void request.then(clearRequest, clearRequest)
  return request
}

/** Load only the selected RAG curve range. */
function loadRag(
  userId: string,
  sessionRecords: SessionRecord[],
  range: ObsHistoryRange = ragLimit.value,
): Promise<void> {
  const key = `${userId}:${range}`
  if (activeRagPromise && activeRagKey === key) return activeRagPromise
  ragLimit.value = range
  const activeRequest = ++ragRequestId
  const request = (async () => {
    if (!userId) {
      ragMessages.value = []
      ragLoaded.value = false
      ragLoadedUserId = ''
      return
    }
    if (ragLoadedUserId && ragLoadedUserId !== userId) ragMessages.value = []
    ragLoading.value = true
    ragError.value = ''
    try {
      const records = await fetchRange(userId, sessionRecords, range)
      if (activeRequest !== ragRequestId) return
      ragMessages.value = records
        .map(normalizeMessage)
        .filter((message): message is AgentChatMessage => message !== null)
      ragLoaded.value = true
      ragLoadedUserId = userId
    } catch (loadError) {
      if (activeRequest !== ragRequestId) return
      ragError.value = loadError instanceof Error ? loadError.message : '读取 RAG 历史失败'
    } finally {
      if (activeRequest === ragRequestId) ragLoading.value = false
    }
  })()
  activeRagKey = key
  activeRagPromise = request
  void request.finally(() => {
    if (activeRagPromise === request) {
      activeRagPromise = null
      activeRagKey = ''
    }
  })
  return request
}

/** Load only the selected message latency curve range. */
function loadLatency(
  userId: string,
  sessionRecords: SessionRecord[],
  range: ObsHistoryRange = latencyLimit.value,
): Promise<void> {
  const key = `${userId}:${range}`
  if (activeLatencyPromise && activeLatencyKey === key) return activeLatencyPromise
  latencyLimit.value = range
  const activeRequest = ++latencyRequestId
  const request = (async () => {
    if (!userId) {
      latencyMessages.value = []
      latencySessions.value = []
      latencyLoaded.value = false
      latencyLoadedUserId = ''
      return
    }
    if (latencyLoadedUserId && latencyLoadedUserId !== userId) {
      latencyMessages.value = []
      latencySessions.value = []
    }
    latencyLoading.value = true
    latencyError.value = ''
    try {
      const records = await fetchRange(userId, sessionRecords, range)
      if (activeRequest !== latencyRequestId) return
      const normalized = records
        .map(normalizeMessage)
        .filter((message): message is AgentChatMessage => message !== null)
      latencyMessages.value = normalized
      latencySessions.value = groupSessions(normalized, records, sessionRecords)
      latencyLoaded.value = true
      latencyLoadedUserId = userId
    } catch (loadError) {
      if (activeRequest !== latencyRequestId) return
      latencyError.value = loadError instanceof Error ? loadError.message : '读取 message 耗时历史失败'
    } finally {
      if (activeRequest === latencyRequestId) latencyLoading.value = false
    }
  })()
  activeLatencyKey = key
  activeLatencyPromise = request
  void request.finally(() => {
    if (activeLatencyPromise === request) {
      activeLatencyPromise = null
      activeLatencyKey = ''
    }
  })
  return request
}

/** Refresh only datasets that the user has already opened. */
async function refreshLoaded(userId: string, sessionRecords: SessionRecord[]): Promise<void> {
  const requests: Promise<void>[] = []
  if (ragLoaded.value) requests.push(loadRag(userId, sessionRecords, ragLimit.value))
  if (latencyLoaded.value) requests.push(loadLatency(userId, sessionRecords, latencyLimit.value))
  await Promise.all(requests)
}

const ragHistory = computed(() => buildRagHistory(ragMessages.value))
const latencyTurns = computed(() => buildAllSessionLatencyTurns(latencySessions.value))

/** Return singleton lazy history state shared by the Dashboard cards. */
export function useObsHistory() {
  return {
    ragMessages,
    latencyMessages,
    latencySessions,
    ragLoading,
    latencyLoading,
    ragError,
    latencyError,
    ragLoaded,
    latencyLoaded,
    ragLimit,
    latencyLimit,
    ragHistory,
    latencyTurns,
    loadRag,
    loadLatency,
    refreshLoaded,
  }
}
