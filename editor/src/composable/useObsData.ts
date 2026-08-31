/*
 * Obs 数据派生组合式函数。
 *
 * 功能说明:
 * 基于 chat/session store 的当前会话消息、trace 与会话列表，统一派生 Obs 面板需要的
 * 节点轨迹、工具轨迹、上下文来源、RAG 指标、Token 趋势、耗时趋势和调度状态。
 * 这一层只做前端聚合，不直接发起额外网络请求，便于所有 Obs 卡片共享同一份观测视图。
 *
 * 使用说明:
 * import { useObsData } from '@/composable/useObsData'
 * const obs = useObsData()
 */

import { computed } from 'vue'
import { buildRagHistory, buildRagMetrics } from '@/composable/useObsMetrics'
import { useChatStore, type AgentChatMessage } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'

export { buildRagHistory, buildRagMetrics } from '@/composable/useObsMetrics'

/* ---- 类型定义 ---- */

/** 上下文来源条目 */
export interface ContextSource {
  id: string
  type: string
  label: string
  accent: string
  text: string
}

/** 上下文拼装块 */
export interface AssemblyBlock {
  id: string
  type: string
  title: string
  accent: string
  status: string
  lines: string[]
  preview: string
  lineCount: number
  order?: number
}

/** 上下文拼装统计 */
export interface AssemblyStats {
  blockCount: number
  lineCount: number
  memoryCount: number
  knowledgeCount: number
  importantCount?: number
  historyCount?: number
}

/** 上下文拼装结果 */
export interface ContextAssembly {
  blocks: AssemblyBlock[]
  stats: AssemblyStats
}

/** Secret-free model request shape emitted immediately before invocation. */
interface ModelRequestSnapshot {
  messages?: Array<Record<string, unknown>>
  tools?: Array<Record<string, unknown>>
}

/** 节点时间线条目 */
export interface NodeTimelineItem {
  id: string
  index: number
  node: string
  event: string
  humanReadable: string
  toolName: string
  isCurrent: boolean
  modelTier: 'small' | 'large' | 'runtime'
}

/** 工具执行记录 */
export interface ToolRun {
  id: string
  toolName: string
  input: string
  output: string
  status: 'success' | 'pending'
}

/** Observation 决策记录 */
export interface ObservationDecisionItem {
  id: string
  index: number
  decision: string
  reason: string
  nextAction: string
  confidence: number
  isCurrent: boolean
}

/** 带增强字段的 Trace 记录 */
export interface EnrichedTrace extends Record<string, unknown> {
  traceKey: string
  messageIndex: number
  createdAt: string | null
  messageContent: string
}

/** 调度器池状态 */
export interface PoolState {
  id: string
  label: string
  state: 'active' | 'standby' | 'queued' | 'idle'
  detail: string
}

/** 调度器快照 */
export interface SchedulerSnapshot {
  globalState: 'running' | 'idle'
  pools: PoolState[]
}

/** RAG 指标 */
export interface RagMetrics {
  fillRate: number
  avgRelevance: number
  confidence: number
  memoryCount: number
  knowledgeCount: number
  importantCount: number
  turnCount: number
}

/** RAG 历史数据点 */
export interface RagHistoryPoint {
  turn: number
  fillRate: number
  avgRelevance: number
  confidence: number
}

/** Token 时序条目 */
export interface TokenSeriesItem {
  id: string
  label: string
  modelTokens: Record<string, number>
  totalTokens: number
  modelTotals: Record<string, number>
}

/** 节点耗时占比 */
export interface NodeBreakdownItem {
  node: string
  count: number
  durationMs: number
  seconds: number
  share: number
}

/** 延迟轮次 */
export interface LatencyTurn {
  id: string
  index: number
  userPrompt: string
  assistantOutput: string
  seconds: number
  cumulativeSeconds: number
  estimated: boolean
  traceCount: number
  toolCount: number
  nodeBreakdown: NodeBreakdownItem[]
  sessionId?: string
  sessionName?: string
  createdAt?: string
}

/** One persisted session and the messages used to derive its latency turns. */
export interface ObsSessionHistory {
  sessionId: string
  sessionName: string
  messages: { role: string; content?: unknown; created_at?: unknown; trace?: unknown; tool_calls?: unknown; node?: unknown }[]
}

/** 延迟摘要 */
export interface LatencySummary {
  avg: number
  max: number
  total: number
}

/** 会话统计 */
export interface SessionStats {
  totalSessions: number
  currentSessionName: string
  currentSessionId: string
}

/* ---- 常量 ---- */

const SMALL_MODEL_NODES = new Set(['compress', 'planner', 'observation', 'summary'])
const LARGE_MODEL_NODES = new Set(['agent'])
const MODEL_TOKEN_NODES = new Set([...SMALL_MODEL_NODES, ...LARGE_MODEL_NODES])
const MODEL_TIER_LABELS: Record<'large' | 'small', string> = {
  large: '\u5927\u6a21\u578b',
  small: '\u5c0f\u6a21\u578b',
}
/* ---- 工具函数 ---- */

function safeArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : []
}

function estimateTextTokens(text: unknown): number {
  return Math.max(0, Math.ceil(String(text || '').length / 4))
}

function parseDate(value: unknown): Date | null {
  if (!value) return null
  const date = new Date(value as string)
  return Number.isNaN(date.getTime()) ? null : date
}

function roundNumber(value: unknown, digits = 1): number {
  return Number.parseFloat(Number(value || 0).toFixed(digits))
}

function modelTierForTrace(trace: Record<string, unknown>): 'small' | 'large' | 'runtime' {
  if (trace.model_tier === 'small' || trace.model_tier === 'large' || trace.model_tier === 'runtime') {
    return trace.model_tier
  }
  if (SMALL_MODEL_NODES.has(trace.node as string)) return 'small'
  if (LARGE_MODEL_NODES.has(trace.node as string)) return 'large'
  return 'runtime'
}

function normalizeTokenUsage(usage: unknown): { inputTokens: number; outputTokens: number; totalTokens: number } {
  if (!usage || typeof usage !== 'object') {
    return { inputTokens: 0, outputTokens: 0, totalTokens: 0 }
  }
  const source = usage as Record<string, unknown>
  const inputTokens = Number(source.input_tokens || source.prompt_tokens || 0)
  const outputTokens = Number(source.output_tokens || source.completion_tokens || 0)
  const totalTokens = Number(source.total_tokens || inputTokens + outputTokens || 0)
  return {
    inputTokens,
    outputTokens,
    totalTokens,
  }
}

export function buildTokenSeries(
  messages: Array<{ role: string; trace?: unknown; created_at?: unknown }>,
): TokenSeriesItem[] {
  const assistantMessages = safeArray<{ role: string; trace?: unknown; created_at?: unknown }>(messages)
    .filter((message) => message.role === 'assistant')
  const modelTotals: Record<string, number> = {}

  return assistantMessages.map((message, index) => {
    const traces = safeArray<Record<string, unknown>>(message.trace)
    const modelTokens: Record<string, number> = {}
    for (const trace of traces) {
      const usage = normalizeTokenUsage(trace.token_usage)
      if (usage.totalTokens <= 0) continue
      const tier = modelTierForTrace(trace)
      if (tier === 'runtime') continue
      if (!MODEL_TOKEN_NODES.has(trace.node as string)) continue
      const name = MODEL_TIER_LABELS[tier]
      if (!name) continue
      modelTokens[name] = (modelTokens[name] || 0) + usage.totalTokens
      modelTotals[name] = (modelTotals[name] || 0) + usage.totalTokens
    }
    const totalTokens = Object.values(modelTokens).reduce((sum, value) => sum + value, 0)

    let label = `#${index + 1}`
    if (message.created_at) {
      const d = new Date(message.created_at as string)
      label = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    }

    return {
      id: `token-${index}`,
      label,
      modelTokens,
      totalTokens,
      modelTotals: { ...modelTotals },
    }
  }).filter((item) => item.totalTokens > 0)
}

function toTitle(type: string): string {
  const map: Record<string, string> = {
    important_summary: '重要事实摘要',
    memory: '长期记忆',
    knowledge: '知识库',
    history: '短期历史',
    prompt: '当前问题',
    skills: 'Skill 候选',
    system: '系统提示',
  }
  return map[type] || '上下文'
}

function sourceAccent(type: string): string {
  const map: Record<string, string> = {
    important_summary: 'var(--color-accent)',
    memory: 'var(--color-blue)',
    knowledge: 'var(--color-green)',
    history: 'var(--color-sky)',
    prompt: 'var(--color-accent)',
    skills: 'var(--color-accent)',
    system: 'var(--color-text-tertiary)',
  }
  return map[type] || 'var(--color-text-tertiary)'
}

function sourceStatus(type: string): string {
  const map: Record<string, string> = {
    important_summary: '直接注入',
    memory: '索引提示',
    knowledge: '索引提示',
    history: '会话历史',
    prompt: '当前输入',
    skills: '路由候选',
    system: '系统约束',
  }
  return map[type] || '上下文'
}

function buildTraceKey(trace: Record<string, unknown>, messageIndex: number, traceIndex: number): string {
  return `${trace.node || 'node'}-${trace.event || 'event'}-${messageIndex}-${traceIndex}`
}

function buildContextSources(messages: { role: string; content: unknown }[]): ContextSource[] {
  const sources: ContextSource[] = []
  const systemMessages = messages.filter((message) => message.role === 'system')
  for (const message of systemMessages) {
    const lines = String(message.content || '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)

    let currentType = 'system'
    for (const line of lines) {
      if (line.includes('重要事实摘要')) {
        currentType = 'important_summary'
        continue
      }
      if (line.includes('长期记忆')) {
        currentType = 'memory'
      } else if (line.includes('知识库')) {
        currentType = 'knowledge'
      } else if (line.includes('当前 session') || line.includes('历史')) {
        currentType = 'history'
      }

      sources.push({
        id: `${currentType}-${sources.length}`,
        type: currentType,
        label: toTitle(currentType),
        accent: sourceAccent(currentType),
        text: line,
      })
    }
  }
  return sources
}

function pushAssemblyBlock(
  blocks: AssemblyBlock[],
  type: string,
  title: string,
  lines: string[],
  meta: Record<string, unknown> = {},
): void {
  const normalizedLines = safeArray<string>(lines)
    .map((line) => String(line || '').trim())
    .filter(Boolean)
  if (normalizedLines.length === 0) return

  blocks.push({
    id: `${type}-${blocks.length}`,
    type,
    title,
    accent: sourceAccent(type),
    status: sourceStatus(type),
    lines: normalizedLines,
    preview: normalizedLines.join('\n'),
    lineCount: normalizedLines.length,
    ...meta,
  } as AssemblyBlock)
}

function buildHistoryBlock(messages: { role: string; content: unknown }[]): string[] {
  const conversationalMessages = messages.filter((message) => ['user', 'assistant', 'tool'].includes(message.role))
  if (conversationalMessages.length === 0) {
    return []
  }

  const filtered = [...conversationalMessages]
    .map((message, index) => ({ message, index }))
    .filter((entry) => entry.message.role === 'user')
  const latestUserIndex = filtered.length > 0 ? filtered[filtered.length - 1]!.index : undefined

  const historyMessages = latestUserIndex === undefined
    ? conversationalMessages
    : conversationalMessages.slice(0, latestUserIndex)

  return historyMessages.map((message) => {
    const roleMap: Record<string, string> = {
      user: '用户',
      assistant: 'Agent',
      tool: '工具',
    }
    return `${roleMap[message.role] || message.role}: ${String(message.content || '').trim() || '（空内容）'}`
  })
}

function buildCurrentPromptBlock(messages: { role: string; content: unknown }[]): string[] {
  const latestUser = [...messages].reverse().find((message) => message.role === 'user')
  if (!latestUser?.content) {
    return []
  }
  return [String(latestUser.content).trim()]
}

function buildSystemContextBlocks(messages: { role: string; content: unknown }[]): AssemblyBlock[] {
  const blocks: AssemblyBlock[] = []
  const systemMessages = messages.filter((message) => message.role === 'system')

  for (const message of systemMessages) {
    const rawLines = String(message.content || '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)

    if (rawLines.length === 0) continue

    const prefaceLines: string[] = []
    const importantLines: string[] = []
    const memoryLines: string[] = []
    const knowledgeLines: string[] = []
    const skillLines: string[] = []
    let insideRefs = false
    let mode = 'preface'

    for (const line of rawLines) {
      if (line === '[Skill routing]' || line === '[Candidate skills]' || line === '[Routed skills for this turn]') {
        mode = 'skills'
        skillLines.push(line)
        continue
      }
      if (line === '--- 参考材料开始 ---') {
        insideRefs = true
        mode = 'refs'
        continue
      }
      if (line === '--- 参考材料结束 ---') {
        insideRefs = false
        mode = 'tail'
        continue
      }
      if (line.startsWith('重要事实摘要')) {
        mode = 'important_summary'
        continue
      }
      if (line.startsWith('长期记忆索引')) {
        mode = 'memory'
        memoryLines.push(line)
        continue
      }
      if (line.startsWith('知识库索引')) {
        mode = 'knowledge'
        knowledgeLines.push(line)
        continue
      }

      if (!insideRefs && mode === 'preface') {
        prefaceLines.push(line)
        continue
      }

      if (mode === 'important_summary') {
        importantLines.push(line.replace(/^-+\s*/, ''))
        continue
      }

      if (mode === 'memory') {
        memoryLines.push(line)
        continue
      }

      if (mode === 'knowledge') {
        knowledgeLines.push(line)
        continue
      }

      if (mode === 'skills') {
        skillLines.push(line)
        continue
      }

      prefaceLines.push(line)
    }

    pushAssemblyBlock(blocks, 'system', '系统提示', prefaceLines)
    pushAssemblyBlock(blocks, 'important_summary', '重要事实摘要', importantLines)
    pushAssemblyBlock(blocks, 'memory', '长期记忆索引', memoryLines)
    pushAssemblyBlock(blocks, 'knowledge', '知识库索引', knowledgeLines)
    pushAssemblyBlock(blocks, 'skills', 'Skill 候选与正文', skillLines)
  }

  return blocks
}

export function buildContextAssembly(messages: { role: string; content: unknown }[]): ContextAssembly {
  const blocks: AssemblyBlock[] = []

  for (const systemBlock of buildSystemContextBlocks(messages)) {
    blocks.push({
      ...systemBlock,
      order: blocks.length + 1,
    })
  }

  const historyLines = buildHistoryBlock(messages)
  pushAssemblyBlock(blocks, 'history', '短期历史窗口', historyLines, {
    order: blocks.length + 1,
  })

  const promptLines = buildCurrentPromptBlock(messages)
  pushAssemblyBlock(blocks, 'prompt', '当前问题', promptLines, {
    order: blocks.length + 1,
  })

  const counts = blocks.reduce<Record<string, number>>((accumulator, block) => {
    accumulator[block.type] = (accumulator[block.type] || 0) + 1
    return accumulator
  }, {})

  return {
    blocks,
    stats: {
      blockCount: blocks.length,
      lineCount: blocks.reduce((sum, block) => sum + block.lineCount, 0),
      memoryCount: counts.memory || 0,
      knowledgeCount: counts.knowledge || 0,
      importantCount: counts.important_summary || 0,
      historyCount: counts.history || 0,
    },
  }
}

/** Build a lossless readable view without reclassifying or trimming request data. */
export function buildExactRequestAssembly(snapshot: ModelRequestSnapshot | undefined): ContextAssembly {
  const blocks: AssemblyBlock[] = []
  const pushExactBlock = (type: string, title: string, lines: string[], order: number) => {
    blocks.push({
      id: `${type}-${blocks.length}`,
      type,
      title,
      accent: sourceAccent(type),
      status: sourceStatus(type),
      lines,
      preview: lines.join('\n'),
      lineCount: lines.length,
      order,
    })
  }
  for (const [index, message] of safeArray<Record<string, unknown>>(snapshot?.messages).entries()) {
    const role = String(message.role || 'unknown')
    const detail = { ...message }
    delete detail.role
    const content = detail.content
    delete detail.content
    const lines = [String(content ?? '')]
    if (Object.keys(detail).length > 0) lines.push(JSON.stringify(detail, null, 2))
    pushExactBlock(`message_${role}`, `${role} message`, lines, index + 1)
  }
  for (const tool of safeArray<Record<string, unknown>>(snapshot?.tools)) {
    const functionDefinition = tool.function && typeof tool.function === 'object'
      ? tool.function as Record<string, unknown>
      : {}
    pushExactBlock(
      'tool_schema',
      `tool: ${String(functionDefinition.name || 'unknown')}`,
      [JSON.stringify(tool, null, 2)],
      blocks.length + 1,
    )
  }
  return {
    blocks,
    stats: {
      blockCount: blocks.length,
      lineCount: blocks.reduce((sum, block) => sum + block.lineCount, 0),
      memoryCount: 0,
      knowledgeCount: 0,
      importantCount: 0,
      historyCount: safeArray(snapshot?.messages).length,
    },
  }
}

function isAssistantRenderable(message: { role: string; content?: unknown; trace?: unknown; tool_calls?: unknown; node?: unknown }): boolean {
  if (message.role !== 'assistant') return false
  if (String(message.content || '').trim()) return true
  if (safeArray(message.trace).length > 0) return true
  if (safeArray(message.tool_calls).length > 0) return true
  return Boolean(message.node)
}

export function buildLatencyTurns(
  messages: { role: string; content?: unknown; created_at?: unknown; trace?: unknown; tool_calls?: unknown; node?: unknown }[],
  isStreaming = false,
): LatencyTurn[] {
  const turns: LatencyTurn[] = []
  let pendingUser: { content?: unknown; created_at?: unknown } | null = null
  let pendingAssistants: { content?: unknown; created_at?: unknown; trace?: unknown; tool_calls?: unknown; node?: unknown }[] = []
  let cumulativeSeconds = 0
  let turnIndex = 0

  function flushTurn(): void {
    if (!pendingUser || pendingAssistants.length === 0) return
    const lastAssistant = pendingAssistants[pendingAssistants.length - 1]!
    const userTime = parseDate(pendingUser.created_at)
    const assistantTime = parseDate(lastAssistant.created_at)
    // Persisted assistant rows carry cumulative trace snapshots; only the
    // latest non-empty snapshot may be summed or earlier nodes are duplicated.
    const latestTraceSnapshot = [...pendingAssistants]
      .reverse()
      .find((message) => safeArray<Record<string, unknown>>(message.trace).length > 0)
    const allTraces = safeArray<Record<string, unknown>>(latestTraceSnapshot?.trace)
    const allToolCalls = pendingAssistants.flatMap((m) => safeArray<unknown>(m.tool_calls))
    const combinedOutput = pendingAssistants
      .map((m) => String(m.content || '').trim())
      .filter(Boolean)
      .pop() || ''
    const traceCount = allTraces.length
    const toolCount = allToolCalls.length
    const durationMs = sumTraceDuration(allTraces)
    let seconds = 0
    let estimated = false

    if (durationMs > 0) {
      seconds = Math.max(0.01, durationMs / 1000)
    } else if (userTime && assistantTime) {
      seconds = Math.max(0.1, (assistantTime.getTime() - userTime.getTime()) / 1000)
      estimated = true
    } else {
      seconds = Math.max(
        0.8,
        traceCount * 0.45 + toolCount * 0.35 + estimateTextTokens(combinedOutput) / 25,
      )
      estimated = true
    }
    cumulativeSeconds += seconds
    turns.push({
      id: `turn-${turnIndex}`,
      index: turnIndex + 1,
      userPrompt: (pendingUser.content as string) || '',
      assistantOutput: combinedOutput,
      seconds: roundNumber(seconds, 2),
      cumulativeSeconds: roundNumber(cumulativeSeconds, 2),
      estimated,
      traceCount,
      toolCount,
      nodeBreakdown: summarizeNodeBreakdown(allTraces),
      createdAt: typeof pendingUser.created_at === 'string' ? pendingUser.created_at : '',
    })
    turnIndex += 1
  }

  for (const message of messages) {
    if (message.role === 'user') {
      flushTurn()
      pendingUser = message
      pendingAssistants = []
      continue
    }

    if (!pendingUser || !isAssistantRenderable(message)) {
      continue
    }

    pendingAssistants.push(message)
  }

  flushTurn()

  if (pendingUser && isStreaming && pendingAssistants.length === 0) {
    const lastAssistant = [...messages].reverse().find((message) => message.role === 'assistant')
    const traceCount = safeArray(lastAssistant?.trace).length
    const toolCount = safeArray(lastAssistant?.tool_calls).length
    const streamingSeconds = Math.max(
      0.8,
      traceCount * 0.45 + toolCount * 0.35 + estimateTextTokens(lastAssistant?.content || '') / 25,
    )
    const streamingTraces = safeArray<Record<string, unknown>>(lastAssistant?.trace)
    turns.push({
      id: `turn-${turnIndex}`,
      index: turnIndex + 1,
      userPrompt: (pendingUser.content as string) || '',
      assistantOutput: (lastAssistant?.content as string) || '',
      seconds: roundNumber(streamingSeconds, 2),
      cumulativeSeconds: roundNumber(cumulativeSeconds + streamingSeconds, 2),
      estimated: true,
      traceCount,
      toolCount,
      nodeBreakdown: summarizeNodeBreakdown(streamingTraces),
    })
  }

  return turns
}

/**
 * Flatten every session's message turns onto one chronological dashboard line.
 *
 * Session boundaries are preserved while deriving turns so a user message in
 * one session can never be paired with an assistant message from another.
 */
export function buildAllSessionLatencyTurns(sessions: ObsSessionHistory[]): LatencyTurn[] {
  const derivedTurns = sessions.flatMap((session) =>
    buildLatencyTurns(session.messages).map((turn) => ({
      ...turn,
      id: `${session.sessionId}:${turn.id}`,
      sessionId: session.sessionId,
      sessionName: session.sessionName,
    })),
  ).sort((left, right) => {
    const leftTime = Date.parse(left.createdAt || '')
    const rightTime = Date.parse(right.createdAt || '')
    if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) return 0
    return leftTime - rightTime
  })
  let cumulativeSeconds = 0
  return derivedTurns.map((turn, index) => {
    cumulativeSeconds += turn.seconds
    return {
      ...turn,
      index: index + 1,
      cumulativeSeconds: roundNumber(cumulativeSeconds, 2),
    }
  })
}

function summarizeNodeBreakdown(traces: Array<Record<string, unknown>> | undefined): NodeBreakdownItem[] {
  const list = safeArray<Record<string, unknown>>(traces)
  const durationByNode: Record<string, number> = {}
  const counts: Record<string, number> = {}
  for (const trace of list) {
    const node = (trace.node as string) || 'unknown'
    counts[node] = (counts[node] || 0) + 1
    const duration = Number(trace.duration_ms || 0)
    if (duration > 0) {
      durationByNode[node] = (durationByNode[node] || 0) + duration
    }
  }
  const durationTotal = Object.values(durationByNode).reduce((sum, value) => sum + value, 0)
  if (durationTotal > 0) {
    return Object.entries(durationByNode).map(([node, durationMs]) => ({
      node,
      count: counts[node] || 0,
      durationMs: roundNumber(durationMs, 2),
      seconds: roundNumber(durationMs / 1000, 2),
      share: roundNumber((durationMs / durationTotal) * 100, 1),
    }))
  }

  const timed = list
    .filter((t) => typeof t.ts === 'number')
    .sort((a, b) => (a.ts as number) - (b.ts as number))

  if (timed.length >= 2) {
    const nodeElapsed: Record<string, number> = {}
    let totalElapsed = 0
    for (let i = 0; i < timed.length - 1; i++) {
      const curr = timed[i]!
      const next = timed[i + 1]!
      const elapsed = Math.max(0, ((next.ts as number) - (curr.ts as number)) * 1000)
      const node = (curr.node as string) || 'unknown'
      nodeElapsed[node] = (nodeElapsed[node] || 0) + elapsed
      totalElapsed += elapsed
    }
    const counts: Record<string, number> = {}
    for (const t of timed) {
      const node = (t.node as string) || 'unknown'
      counts[node] = (counts[node] || 0) + 1
    }
    if (totalElapsed > 0) {
      return Object.entries(nodeElapsed).map(([node, elapsed]) => ({
        node,
        count: counts[node] || 0,
        durationMs: roundNumber(elapsed, 2),
        seconds: roundNumber(elapsed / 1000, 2),
        share: roundNumber((elapsed / totalElapsed) * 100, 1),
      }))
    }
  }

  const total = Object.values(counts).reduce((sum, value) => sum + value, 0) || 1
  return Object.entries(counts).map(([node, count]) => ({
    node,
    count,
    durationMs: 0,
    seconds: 0,
    share: roundNumber((count / total) * 100, 1),
  }))
}

function sumTraceDuration(traces: Array<Record<string, unknown>> | undefined): number {
  return safeArray<Record<string, unknown>>(traces).reduce((sum, trace) => {
    const duration = Number(trace.duration_ms || 0)
    return duration > 0 ? sum + duration : sum
  }, 0)
}

function buildToolRuns(traces: EnrichedTrace[]): ToolRun[] {
  const runs: ToolRun[] = []
  const pendingStarts = new Map<string, EnrichedTrace>()

  for (const trace of traces) {
    if (!trace.tool_name) continue
    if (trace.event === 'tool_call_start') {
      pendingStarts.set(trace.tool_name as string, trace)
      continue
    }
    if (trace.event === 'tool_call_end') {
      const start = pendingStarts.get(trace.tool_name as string)
      runs.push({
        id: `${trace.tool_name}-${runs.length}`,
        toolName: trace.tool_name as string,
        input: (start?.tool_args_summary as string) || '无参数',
        output: (trace.result_summary as string) || '',
        status: 'success',
      })
      pendingStarts.delete(trace.tool_name as string)
    }
  }

  for (const [toolName, start] of pendingStarts.entries()) {
    runs.push({
      id: `${toolName}-${runs.length}`,
      toolName,
      input: (start?.tool_args_summary as string) || '无参数',
      output: '等待工具返回',
      status: 'pending',
    })
  }

  return runs
}

/* ---- 导出组合式函数 ---- */

export function useObsData() {
  const chatStore = useChatStore()
  const sessionStore = useSessionStore()

  const messages = computed(() => safeArray(chatStore.messages) as AgentChatMessage[])

  const currentNode = computed(() => chatStore.currentNode || '')

  /** 所有消息的所有 trace 扁平化，带增强字段 */
  const allTraces = computed<EnrichedTrace[]>(() => {
    const traces: EnrichedTrace[] = []
    messages.value.forEach((message, messageIndex) => {
      safeArray<Record<string, unknown>>(message.trace).forEach((trace, traceIndex) => {
        traces.push({
          ...trace,
          traceKey: buildTraceKey(trace, messageIndex, traceIndex),
          messageIndex,
          createdAt: (message.created_at as string) || null,
          messageContent: (message.content as string) || '',
        } as EnrichedTrace)
      })
    })
    return traces
  })

  /** 去重后的思考轨迹（按 human_readable） */
  const thinkingTraces = computed(() => {
    const seen = new Set<string>()
    return allTraces.value.filter((trace) => {
      const readable = trace.human_readable as string | undefined
      if (!readable || seen.has(readable)) return false
      seen.add(readable)
      return true
    })
  })

  const contextSources = computed(() => buildContextSources(messages.value))

  /** 上下文拼装只接受后端最终请求快照，禁止从聊天消息猜测模型输入。 */
  const contextAssembly = computed<ContextAssembly>(() => {
    const latest = chatStore.contextSnapshots[chatStore.contextSnapshots.length - 1]
    return buildExactRequestAssembly(latest)
  })

  /** 模型收到的完整上下文镜像, 由 agent 节点在调用 LLM 前通过 SSE 下发。 */
  const contextMirror = computed(() => chatStore.contextMirror || [])
  const contextSnapshots = computed(() => chatStore.contextSnapshots || [])

  const memorySources = computed(() =>
    contextSources.value.filter((source) => ['important_summary', 'memory'].includes(source.type)),
  )

  const knowledgeSources = computed(() =>
    contextSources.value.filter((source) => source.type === 'knowledge'),
  )

  const toolRuns = computed(() => buildToolRuns(allTraces.value))

  const nodeTimeline = computed<NodeTimelineItem[]>(() =>
    allTraces.value.map((trace, index) => ({
      id: trace.traceKey,
      index: index + 1,
      node: (trace.node as string) || 'unknown',
      event: (trace.event as string) || 'event',
      humanReadable: (trace.human_readable as string) || (trace.event as string) || '事件',
      toolName: (trace.tool_name as string) || '',
      isCurrent: currentNode.value !== '' && currentNode.value === (trace.node as string),
      modelTier: (SMALL_MODEL_NODES.has(trace.node as string)
        ? 'small'
        : LARGE_MODEL_NODES.has(trace.node as string)
          ? 'large'
          : 'runtime') as NodeTimelineItem['modelTier'],
    })),
  )

  const schedulerSnapshot = computed<SchedulerSnapshot>(() => {
    const lastNode = currentNode.value || nodeTimeline.value[nodeTimeline.value.length - 1]?.node || ''
    const summaryScheduled = allTraces.value.some((trace) => trace.event === 'summary_scheduled')
    return {
      globalState: chatStore.isStreaming ? 'running' : 'idle',
      pools: [
        {
          id: 'large',
          label: '大模型池',
          state: LARGE_MODEL_NODES.has(lastNode) ? 'active' : 'standby',
          detail: LARGE_MODEL_NODES.has(lastNode) ? '当前由主 Agent 决策占用' : '等待前台推理任务',
        },
        {
          id: 'small',
          label: '小模型池',
          state: SMALL_MODEL_NODES.has(lastNode) ? 'active' : 'standby',
          detail: SMALL_MODEL_NODES.has(lastNode) ? '正在执行语义任务' : '等待压缩 / 摘要 / 事实抽取',
        },
        {
          id: 'background',
          label: '后台队列',
          state: summaryScheduled ? 'queued' : 'idle',
          detail: summaryScheduled ? '存在摘要任务等待异步执行' : '当前无后台任务积压',
        },
      ],
    }
  })

  const ragMetrics = computed<RagMetrics>(() => buildRagMetrics(messages.value))

  /** 会话级 RAG 历史：每轮的三率，供曲线图使用 */
  const ragHistory = computed<RagHistoryPoint[]>(() => buildRagHistory(messages.value))

  const tokenSeries = computed<TokenSeriesItem[]>(() => buildTokenSeries(messages.value))

  const latencyTurns = computed(() => buildLatencyTurns(messages.value, chatStore.isStreaming))

  const latencySummary = computed<LatencySummary>(() => {
    if (latencyTurns.value.length === 0) {
      return { avg: 0, max: 0, total: 0 }
    }
    const total = latencyTurns.value.reduce((sum, turn) => sum + turn.seconds, 0)
    const max = Math.max(...latencyTurns.value.map((turn) => turn.seconds))
    return {
      avg: roundNumber(total / latencyTurns.value.length, 2),
      max: roundNumber(max, 2),
      total: roundNumber(total, 2),
    }
  })

  const runtimePath = computed(() => {
    const path: string[] = []
    const seen = new Set<string>()
    for (const trace of nodeTimeline.value) {
      if (seen.has(trace.node)) continue
      seen.add(trace.node)
      path.push(trace.node)
    }
    return path
  })

  /*
   * 当前轮次 (自最后一条 user 消息以来) 所有 assistant 消息的轨迹聚合。
   * 在对话模式下只有一条 assistant 消息; 在工具模式下每个图节点单独产生一条
   * assistant 消息, 需要合并同一轮次内所有 assistant 的 trace 才能得到完整的
   * 语言轨迹、节点时间线和工具轨迹。
   */
  const currentMessageTraces = computed(() => {
    const traces: Record<string, unknown>[] = []
    /*
     * 从尾部向前扫描: 收集最后一条 user 消息之后的所有 assistant trace。
     * 这样只包含当前轮次, 不混入历史轮次的旧轨迹。
     */
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i]!
      if (msg.role === 'user') break
      if (msg.role === 'assistant') {
        traces.unshift(...safeArray<Record<string, unknown>>(msg.trace))
        if (msg.thinking?.trim()) {
          traces.unshift({
            node: msg.node || 'agent',
            event: 'reasoning_content',
            human_readable: msg.thinking,
            chat_visible: false,
          })
        }
      }
    }
    return traces
  })

  const currentMessageThinkingTraces = computed(() => {
    const seen = new Set<string>()
    return currentMessageTraces.value.filter((trace) => {
      const readable = trace.human_readable as string | undefined
      if (!readable || seen.has(readable)) return false
      seen.add(readable)
      return true
    })
  })

  const currentMessageNodeTimeline = computed<NodeTimelineItem[]>(() =>
    currentMessageTraces.value.map((trace, index) => ({
      id: `${trace.node || 'node'}-${trace.event || 'event'}-${index}`,
      index: index + 1,
      node: (trace.node as string) || 'unknown',
      event: (trace.event as string) || 'event',
      humanReadable: (trace.human_readable as string) || (trace.event as string) || '事件',
      toolName: (trace.tool_name as string) || '',
      isCurrent: currentNode.value !== '' && currentNode.value === (trace.node as string),
      modelTier: (SMALL_MODEL_NODES.has(trace.node as string)
        ? 'small'
        : LARGE_MODEL_NODES.has(trace.node as string)
          ? 'large'
          : 'runtime') as NodeTimelineItem['modelTier'],
    })),
  )

  const currentMessageToolRuns = computed(() => buildToolRuns(currentMessageTraces.value as unknown as EnrichedTrace[]))

  const currentMessageObservationDecisions = computed<ObservationDecisionItem[]>(() =>
    currentMessageTraces.value
      .filter((trace) => trace.node === 'observation' && trace.decision)
      .map((trace, index) => ({
        id: `observation-${index}-${trace.decision || 'decision'}`,
        index: index + 1,
        decision: String(trace.decision || 'continue'),
        reason: String(trace.reason || trace.human_readable || ''),
        nextAction: String(trace.next_action || ''),
        confidence: Number(trace.confidence || 0),
        isCurrent: currentNode.value === 'observation',
      })),
  )

  const currentMessageRuntimePath = computed(() => {
    const path: string[] = []
    const seen = new Set<string>()
    for (const trace of currentMessageTraces.value) {
      const node = (trace.node as string) || ''
      if (seen.has(node) || !node) continue
      seen.add(node)
      path.push(node)
    }
    return path
  })

  const sessionStats = computed<SessionStats>(() => ({
    totalSessions: sessionStore.sessions.length,
    currentSessionName: sessionStore.currentSession?.session_name || '未命名会话',
    currentSessionId: sessionStore.currentSessionId || '',
  }))

  return {
    messages,
    currentNode,
    thinkingTraces,
    allTraces,
    nodeTimeline,
    toolRuns,
    currentMessageNodeTimeline,
    currentMessageToolRuns,
    currentMessageObservationDecisions,
    currentMessageRuntimePath,
    currentMessageThinkingTraces,
    contextSources,
    contextAssembly,
    contextMirror,
    contextSnapshots,
    memorySources,
    knowledgeSources,
    schedulerSnapshot,
    ragMetrics,
    ragHistory,
    tokenSeries,
    latencyTurns,
    latencySummary,
    runtimePath,
    sessionStats,
    isStreaming: computed(() => chatStore.isStreaming),
  }
}
