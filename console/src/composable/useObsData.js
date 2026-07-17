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
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'

const SMALL_MODEL_NODES = new Set(['compress', 'planner', 'observation', 'summary'])
const LARGE_MODEL_NODES = new Set(['agent'])
const MODEL_TOKEN_NODES = new Set([...SMALL_MODEL_NODES, ...LARGE_MODEL_NODES])
const MODEL_TIER_LABELS = {
  large: '\u5927\u6a21\u578b',
  small: '\u5c0f\u6a21\u578b',
}
const KNOWLEDGE_RECALL_TOOLS = new Set([
  'get_knowledge_context',
  'search_knowledge',
  'read_knowledge_file',
  'read_multimodal_file_info',
])

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function estimateTextTokens(text) {
  return Math.max(0, Math.ceil(String(text || '').length / 4))
}

function parseDate(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function roundNumber(value, digits = 1) {
  return Number.parseFloat(Number(value || 0).toFixed(digits))
}

function extractTopKFromArgs(summary, fallback = 3) {
  const text = String(summary || '')
  const match = text.match(/top_k\s*[:=]\s*(\d+)/i) || text.match(/"top_k"\s*:\s*(\d+)/i)
  const value = match ? Number(match[1]) : fallback
  return Number.isFinite(value) && value > 0 ? value : fallback
}

function extractConfidenceFromText(text, fallback) {
  const source = String(text || '')
  const match = source.match(/(?:confidence|rerank|score|merged_score|final_score)\D*(\d+(?:\.\d+)?)/i)
  if (!match) return fallback
  const raw = Number(match[1])
  if (!Number.isFinite(raw)) return fallback
  return roundNumber(raw <= 1 ? raw * 100 : Math.min(raw, 100), 1)
}

function isEmptyToolResult(text) {
  const source = String(text || '').trim().toLowerCase()
  if (!source) return true
  return [
    '未找到',
    '没有找到',
    '无相关',
    'no result',
    'not found',
    '执行失败',
    '失败',
    'error',
  ].some((pattern) => source.includes(pattern))
}

function inferKnowledgeResultCount(trace, toolName) {
  const explicit = Number(trace.result_count || 0)
  if (explicit > 0) return explicit
  const summary = String(trace.result_summary || '')
  if (isEmptyToolResult(summary)) return 0

  const citationMatches = summary.match(/\[[A-Z]?\d+\]/g)
  if (citationMatches?.length) return citationMatches.length
  const numberedMatches = summary.match(/(?:^|\n)\s*\d+\.\s+/g)
  if (numberedMatches?.length) return numberedMatches.length
  const fileMatches = summary.match(/(?:^|\n)\s*(?:[-*]\s*)?[\w./\\\-\u4e00-\u9fa5]+\.(?:md|txt|pdf|docx?|xlsx?|csv|png|jpe?g)\b/gi)
  if (fileMatches?.length) return fileMatches.length

  return toolName.startsWith('read_') || toolName === 'search_knowledge' ? 1 : 0
}

function metricSampleFromKnowledgeTool(trace, startTrace) {
  const toolName = String(trace.tool_name || '')
  if (trace.event !== 'tool_call_end' || !KNOWLEDGE_RECALL_TOOLS.has(toolName)) return null
  const resultCount = inferKnowledgeResultCount(trace, toolName)
  const topK = toolName.startsWith('read_') ? 1 : extractTopKFromArgs(startTrace?.tool_args_summary, 3)
  const hitRate = resultCount > 0 ? 100 : 0
  return {
    recall: roundNumber(Math.min((resultCount / topK) * 100, 100), 1),
    hit_rate: hitRate,
    confidence: extractConfidenceFromText(trace.result_summary, hitRate),
    memory_count: 0,
    knowledge_count: resultCount,
    important_count: 0,
  }
}

function collectRagMetrics(messages) {
  const metrics = []
  for (const message of safeArray(messages)) {
    if (message.role === 'system') {
      const systemMetrics = message.metadata?.rag_metrics
      if (systemMetrics) metrics.push(systemMetrics)
      continue
    }
    if (message.role !== 'assistant') continue
    const starts = new Map()
    for (const trace of safeArray(message.trace)) {
      const callId = String(trace.tool_call_id || '')
      if (trace.event === 'tool_call_start' && callId) {
        starts.set(callId, trace)
        continue
      }
      const toolMetrics = metricSampleFromKnowledgeTool(trace, starts.get(callId))
      if (toolMetrics) metrics.push(toolMetrics)
    }
  }
  return metrics
}

function modelTierForTrace(trace) {
  if (trace.model_tier === 'small' || trace.model_tier === 'large' || trace.model_tier === 'runtime') {
    return trace.model_tier
  }
  if (SMALL_MODEL_NODES.has(trace.node)) return 'small'
  if (LARGE_MODEL_NODES.has(trace.node)) return 'large'
  return 'runtime'
}

function toTitle(type) {
  const map = {
    important_summary: '重要事实摘要',
    memory: '长期记忆',
    knowledge: '知识库',
    history: '短期历史',
    prompt: '当前问题',
    system: '系统提示',
  }
  return map[type] || '上下文'
}

function sourceAccent(type) {
  const map = {
    important_summary: 'var(--color-accent)',
    memory: 'var(--color-blue)',
    knowledge: 'var(--color-green)',
    history: 'var(--color-sky)',
    prompt: 'var(--color-accent)',
    system: 'var(--color-text-tertiary)',
  }
  return map[type] || 'var(--color-text-tertiary)'
}

function sourceStatus(type) {
  const map = {
    important_summary: '直接注入',
    memory: '索引提示',
    knowledge: '索引提示',
    history: '会话历史',
    prompt: '当前输入',
    system: '系统约束',
  }
  return map[type] || '上下文'
}

function buildTraceKey(trace, messageIndex, traceIndex) {
  return `${trace.node || 'node'}-${trace.event || 'event'}-${messageIndex}-${traceIndex}`
}

function buildContextSources(messages) {
  const sources = []
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

function pushAssemblyBlock(blocks, type, title, lines, meta = {}) {
  const normalizedLines = safeArray(lines)
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
  })
}

function buildHistoryBlock(messages) {
  const conversationalMessages = messages.filter((message) => ['user', 'assistant', 'tool'].includes(message.role))
  if (conversationalMessages.length === 0) {
    return []
  }

  const latestUserIndex = [...conversationalMessages]
    .map((message, index) => ({ message, index }))
    .filter((entry) => entry.message.role === 'user')
    .at(-1)?.index

  const historyMessages = latestUserIndex === undefined
    ? conversationalMessages
    : conversationalMessages.slice(0, latestUserIndex)

  return historyMessages.map((message) => {
    const roleMap = {
      user: '用户',
      assistant: 'Agent',
      tool: '工具',
    }
    return `${roleMap[message.role] || message.role}: ${String(message.content || '').trim() || '（空内容）'}`
  })
}

function buildCurrentPromptBlock(messages) {
  const latestUser = [...messages].reverse().find((message) => message.role === 'user')
  if (!latestUser?.content) {
    return []
  }
  return [String(latestUser.content).trim()]
}

function buildSystemContextBlocks(messages) {
  const blocks = []
  const systemMessages = messages.filter((message) => message.role === 'system')

  for (const message of systemMessages) {
    const rawLines = String(message.content || '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)

    if (rawLines.length === 0) continue

    const prefaceLines = []
    let importantLines = []
    let memoryLines = []
    let knowledgeLines = []
    let insideRefs = false
    let mode = 'preface'

    for (const line of rawLines) {
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

      prefaceLines.push(line)
    }

    pushAssemblyBlock(blocks, 'system', '系统提示', prefaceLines)
    pushAssemblyBlock(blocks, 'important_summary', '重要事实摘要', importantLines)
    pushAssemblyBlock(blocks, 'memory', '长期记忆索引', memoryLines)
    pushAssemblyBlock(blocks, 'knowledge', '知识库索引', knowledgeLines)
  }

  return blocks
}

function buildContextAssembly(messages) {
  const blocks = []

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

  const counts = blocks.reduce((accumulator, block) => {
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

function isAssistantRenderable(message) {
  if (message.role !== 'assistant') return false
  if (String(message.content || '').trim()) return true
  if (safeArray(message.trace).length > 0) return true
  if (safeArray(message.tool_calls).length > 0) return true
  return Boolean(message.node)
}

function buildLatencyTurns(messages, isStreaming = false) {
  const turns = []
  let pendingUser = null
  let pendingAssistants = []
  const cumulativeTraces = []
  let cumulativeSeconds = 0
  let turnIndex = 0

  function flushTurn() {
    if (!pendingUser || pendingAssistants.length === 0) return
    const lastAssistant = pendingAssistants[pendingAssistants.length - 1]
    const userTime = parseDate(pendingUser.created_at)
    const assistantTime = parseDate(lastAssistant.created_at)
    const allTraces = pendingAssistants.flatMap((m) => safeArray(m.trace))
    const allToolCalls = pendingAssistants.flatMap((m) => safeArray(m.tool_calls))
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
        traceCount * 0.45 + toolCount * 0.35 + estimateTextTokens(combinedOutput) / 25
      )
      estimated = true
    }
    cumulativeSeconds += seconds
    cumulativeTraces.push(...allTraces)

    turns.push({
      id: `turn-${turnIndex}`,
      index: turnIndex + 1,
      userPrompt: pendingUser.content || '',
      assistantOutput: combinedOutput,
      seconds: roundNumber(seconds, 2),
      cumulativeSeconds: roundNumber(cumulativeSeconds, 2),
      estimated,
      traceCount,
      toolCount,
      nodeBreakdown: summarizeNodeBreakdown(cumulativeTraces),
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
      traceCount * 0.45 + toolCount * 0.35 + estimateTextTokens(lastAssistant?.content || '') / 25
    )
    const streamingTraces = safeArray(lastAssistant?.trace)
    turns.push({
      id: `turn-${turnIndex}`,
      index: turnIndex + 1,
      userPrompt: pendingUser.content || '',
      assistantOutput: lastAssistant?.content || '',
      seconds: roundNumber(streamingSeconds, 2),
      cumulativeSeconds: roundNumber(cumulativeSeconds + streamingSeconds, 2),
      estimated: true,
      traceCount,
      toolCount,
      nodeBreakdown: summarizeNodeBreakdown([...cumulativeTraces, ...streamingTraces]),
    })
  }

  return turns
}

function summarizeNodeBreakdown(traces) {
  const list = safeArray(traces)
  const durationByNode = {}
  const counts = {}
  for (const trace of list) {
    const node = trace.node || 'unknown'
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
    .sort((a, b) => a.ts - b.ts)

  if (timed.length >= 2) {
    const nodeElapsed = {}
    let totalElapsed = 0
    for (let i = 0; i < timed.length - 1; i++) {
      const elapsed = Math.max(0, (timed[i + 1].ts - timed[i].ts) * 1000)
      const node = timed[i].node || 'unknown'
      nodeElapsed[node] = (nodeElapsed[node] || 0) + elapsed
      totalElapsed += elapsed
    }
    const counts = {}
    for (const t of timed) {
      const node = t.node || 'unknown'
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

function sumTraceDuration(traces) {
  return safeArray(traces).reduce((sum, trace) => {
    const duration = Number(trace.duration_ms || 0)
    return duration > 0 ? sum + duration : sum
  }, 0)
}

function normalizeTokenUsage(usage) {
  if (!usage || typeof usage !== 'object') {
    return { inputTokens: 0, outputTokens: 0, totalTokens: 0 }
  }
  const inputTokens = Number(usage.input_tokens || usage.prompt_tokens || 0)
  const outputTokens = Number(usage.output_tokens || usage.completion_tokens || 0)
  const totalTokens = Number(usage.total_tokens || inputTokens + outputTokens || 0)
  return {
    inputTokens,
    outputTokens,
    totalTokens,
  }
}

export function buildRagMetrics(messages) {
  const metrics = collectRagMetrics(messages)
  if (metrics.length === 0) {
    return {
      recall: 0,
      hitRate: 0,
      confidence: 0,
      memoryCount: 0,
      knowledgeCount: 0,
      importantCount: 0,
      turnCount: 0,
    }
  }

  const totals = metrics.reduce((acc, m) => ({
    recall: acc.recall + Number(m.recall || 0),
    hitRate: acc.hitRate + Number(m.hit_rate || 0),
    confidence: acc.confidence + Number(m.confidence || 0),
    memoryCount: acc.memoryCount + Number(m.memory_count || 0),
    knowledgeCount: acc.knowledgeCount + Number(m.knowledge_count || 0),
    importantCount: acc.importantCount + Number(m.important_count || 0),
  }), {
    recall: 0,
    hitRate: 0,
    confidence: 0,
    memoryCount: 0,
    knowledgeCount: 0,
    importantCount: 0,
  })

  return {
    recall: roundNumber(totals.recall / metrics.length, 1),
    hitRate: roundNumber(totals.hitRate / metrics.length, 1),
    confidence: roundNumber(totals.confidence / metrics.length, 1),
    memoryCount: totals.memoryCount,
    knowledgeCount: totals.knowledgeCount,
    importantCount: totals.importantCount,
    turnCount: metrics.length,
  }
}

export function buildRagHistory(messages) {
  const points = []
  let turnIndex = 0
  let recallTotal = 0
  let hitRateTotal = 0
  let confidenceTotal = 0
  for (const m of collectRagMetrics(messages)) {
    turnIndex++
    recallTotal += Number(m.recall || 0)
    hitRateTotal += Number(m.hit_rate || 0)
    confidenceTotal += Number(m.confidence || 0)
    points.push({
      turn: turnIndex,
      recall: roundNumber(recallTotal / turnIndex, 1),
      hitRate: roundNumber(hitRateTotal / turnIndex, 1),
      confidence: roundNumber(confidenceTotal / turnIndex, 1),
    })
  }
  return points
}

export function buildTokenSeries(messages) {
  const assistantMessages = safeArray(messages).filter((message) => message.role === 'assistant')
  const modelTotals = {}

  return assistantMessages.map((message, index) => {
    const traces = safeArray(message.trace)
    const modelTokens = {}
    for (const trace of traces) {
      const usage = normalizeTokenUsage(trace.token_usage)
      if (usage.totalTokens <= 0) continue
      const tier = modelTierForTrace(trace)
      if (tier === 'runtime') continue
      if (!MODEL_TOKEN_NODES.has(trace.node)) continue
      const name = MODEL_TIER_LABELS[tier]
      if (!name) continue
      modelTokens[name] = (modelTokens[name] || 0) + usage.totalTokens
      modelTotals[name] = (modelTotals[name] || 0) + usage.totalTokens
    }
    const totalTokens = Object.values(modelTokens).reduce((sum, value) => sum + value, 0)

    let label = `#${index + 1}`
    if (message.created_at) {
      const d = new Date(message.created_at)
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

function buildToolRuns(traces) {
  const runs = []
  const pendingStarts = new Map()

  for (const trace of traces) {
    if (!trace.tool_name) continue
    const traceKey = trace.tool_call_id || trace.tool_name
    if (trace.event === 'tool_call_start') {
      pendingStarts.set(traceKey, trace)
      continue
    }
    if (trace.event === 'tool_call_end') {
      const start = pendingStarts.get(traceKey)
      runs.push({
        id: `${traceKey}-${runs.length}`,
        toolName: trace.tool_name,
        input: start?.tool_args_summary || '无参数',
        output: trace.result_summary || '',
        status: 'success',
        durationMs: Number(trace.duration_ms || 0),
      })
      pendingStarts.delete(traceKey)
    }
  }

  for (const [traceKey, start] of pendingStarts.entries()) {
    runs.push({
      id: `${traceKey}-${runs.length}`,
      toolName: start.tool_name || traceKey,
      input: start?.tool_args_summary || '无参数',
      output: '等待工具返回',
      status: 'pending',
      durationMs: 0,
    })
  }

  return runs
}

export function useObsData() {
  const chatStore = useChatStore()
  const sessionStore = useSessionStore()

  const messages = computed(() => safeArray(chatStore.messages))
  const currentNode = computed(() => chatStore.currentNode || '')
  const allTraces = computed(() => {
    const traces = []
    messages.value.forEach((message, messageIndex) => {
      safeArray(message.trace).forEach((trace, traceIndex) => {
        traces.push({
          ...trace,
          traceKey: buildTraceKey(trace, messageIndex, traceIndex),
          messageIndex,
          createdAt: message.created_at || null,
          messageContent: message.content || '',
        })
      })
    })
    return traces
  })

  const thinkingTraces = computed(() => {
    const seen = new Set()
    return allTraces.value.filter((trace) => {
      const readable = trace.human_readable
      if (!readable || seen.has(readable)) return false
      seen.add(readable)
      return true
    })
  })

  const contextSources = computed(() => buildContextSources(messages.value))

  /*
   * 上下文拼装: 优先使用 agent 节点传来的完整上下文镜像 (模型收到的真实消息列表),
   * 回退到从消息列表中解析系统消息的方式。
   * 镜像消息格式为 [{role, content, ...}], 与 messages 格式兼容,
   * 可直接传入 buildContextAssembly。
   */
  const contextAssembly = computed(() => {
    const mirror = chatStore.contextMirror
    if (mirror && mirror.length > 0) {
      return buildContextAssembly(mirror)
    }
    return buildContextAssembly(messages.value)
  })

  /** 模型收到的完整上下文镜像, 由 agent 节点在调用 LLM 前通过 SSE 下发。 */
  const contextMirror = computed(() => chatStore.contextMirror || [])
  const memorySources = computed(() =>
    contextSources.value.filter((source) => ['important_summary', 'memory'].includes(source.type))
  )
  const knowledgeSources = computed(() =>
    contextSources.value.filter((source) => source.type === 'knowledge')
  )

  const toolRuns = computed(() => buildToolRuns(allTraces.value))

  const nodeTimeline = computed(() =>
    allTraces.value.map((trace, index) => ({
      id: trace.traceKey,
      index: index + 1,
      node: trace.node || 'unknown',
      event: trace.event || 'event',
      humanReadable: trace.human_readable || trace.event || '事件',
      toolName: trace.tool_name || '',
      isCurrent: currentNode.value !== '' && currentNode.value === trace.node,
      modelTier: modelTierForTrace(trace),
    }))
  )

  const schedulerSnapshot = computed(() => {
    const lastNode = currentNode.value || nodeTimeline.value.at(-1)?.node || ''
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

  const ragMetrics = computed(() => buildRagMetrics(messages.value))

  /** 会话级 RAG 历史：每轮的三率，供曲线图使用 */
  const ragHistory = computed(() => buildRagHistory(messages.value))

  const tokenSeries = computed(() => buildTokenSeries(messages.value))

  const latencyTurns = computed(() => buildLatencyTurns(messages.value, chatStore.isStreaming))
  const latencySummary = computed(() => {
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
    const path = []
    const seen = new Set()
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
    const traces = []
    /*
     * 从尾部向前扫描: 收集最后一条 user 消息之后的所有 assistant trace。
     * 这样只包含当前轮次, 不混入历史轮次的旧轨迹。
     */
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i]
      if (msg.role === 'user') break
      if (msg.role === 'assistant') {
        traces.unshift(...safeArray(msg.trace))
      }
    }
    return traces
  })

  const currentMessageThinkingTraces = computed(() => {
    const seen = new Set()
    return currentMessageTraces.value.filter((trace) => {
      const readable = trace.human_readable
      if (!readable || seen.has(readable)) return false
      seen.add(readable)
      return true
    })
  })

  const currentMessageNodeTimeline = computed(() =>
    currentMessageTraces.value.map((trace, index) => ({
      id: `${trace.node || 'node'}-${trace.event || 'event'}-${index}`,
      index: index + 1,
      node: trace.node || 'unknown',
      event: trace.event || 'event',
      humanReadable: trace.human_readable || trace.event || '事件',
      toolName: trace.tool_name || '',
      isCurrent: currentNode.value !== '' && currentNode.value === trace.node,
      modelTier: modelTierForTrace(trace),
    }))
  )

  const currentMessageToolRuns = computed(() => buildToolRuns(currentMessageTraces.value))

  const currentMessageRuntimePath = computed(() => {
    const path = []
    const seen = new Set()
    for (const trace of currentMessageTraces.value) {
      const node = trace.node || ''
      if (seen.has(node) || !node) continue
      seen.add(node)
      path.push(node)
    }
    return path
  })

  const sessionStats = computed(() => ({
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
    currentMessageRuntimePath,
    currentMessageThinkingTraces,
    contextSources,
    contextAssembly,
    contextMirror,
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
