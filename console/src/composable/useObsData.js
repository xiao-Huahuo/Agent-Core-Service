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

function safeArray(value) {
  return Array.isArray(value) ? value : []
}

function estimateTextTokens(text) {
  return Math.max(0, Math.ceil(String(text || '').length / 4))
}

function estimateToolTokens(toolCalls) {
  return estimateTextTokens(JSON.stringify(safeArray(toolCalls)))
}

function parseDate(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function roundNumber(value, digits = 1) {
  return Number.parseFloat(Number(value || 0).toFixed(digits))
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
    let seconds = 0
    let estimated = false

    if (userTime && assistantTime) {
      seconds = Math.max(0.1, (assistantTime.getTime() - userTime.getTime()) / 1000)
    } else {
      seconds = Math.max(
        0.8,
        traceCount * 0.45 + toolCount * 0.35 + estimateTextTokens(combinedOutput) / 25
      )
      estimated = true
    }

    turns.push({
      id: `turn-${turnIndex}`,
      index: turnIndex + 1,
      userPrompt: pendingUser.content || '',
      assistantOutput: combinedOutput,
      seconds: roundNumber(seconds, 2),
      estimated,
      traceCount,
      toolCount,
      nodeBreakdown: summarizeNodeBreakdown(allTraces),
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
    turns.push({
      id: `turn-${turnIndex}`,
      index: turnIndex + 1,
      userPrompt: pendingUser.content || '',
      assistantOutput: lastAssistant?.content || '',
      seconds: roundNumber(
        Math.max(0.8, traceCount * 0.45 + toolCount * 0.35 + estimateTextTokens(lastAssistant?.content || '') / 25),
        2
      ),
      estimated: true,
      traceCount,
      toolCount,
      nodeBreakdown: summarizeNodeBreakdown(lastAssistant?.trace),
    })
  }

  return turns
}

function summarizeNodeBreakdown(traces) {
  const list = safeArray(traces)
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
        share: roundNumber((elapsed / totalElapsed) * 100, 1),
      }))
    }
  }

  const counts = {}
  for (const trace of list) {
    const node = trace.node || 'unknown'
    counts[node] = (counts[node] || 0) + 1
  }
  const total = Object.values(counts).reduce((sum, value) => sum + value, 0) || 1
  return Object.entries(counts).map(([node, count]) => ({
    node,
    count,
    share: roundNumber((count / total) * 100, 1),
  }))
}

function buildToolRuns(traces) {
  const runs = []
  const pendingStarts = new Map()

  for (const trace of traces) {
    if (!trace.tool_name) continue
    if (trace.event === 'tool_call_start') {
      pendingStarts.set(trace.tool_name, trace)
      continue
    }
    if (trace.event === 'tool_call_end') {
      const start = pendingStarts.get(trace.tool_name)
      runs.push({
        id: `${trace.tool_name}-${runs.length}`,
        toolName: trace.tool_name,
        input: start?.tool_args_summary || '无参数',
        output: trace.result_summary || '',
        status: 'success',
      })
      pendingStarts.delete(trace.tool_name)
    }
  }

  for (const [toolName, start] of pendingStarts.entries()) {
    runs.push({
      id: `${toolName}-${runs.length}`,
      toolName,
      input: start?.tool_args_summary || '无参数',
      output: '等待工具返回',
      status: 'pending',
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
      modelTier: SMALL_MODEL_NODES.has(trace.node) ? 'small' : LARGE_MODEL_NODES.has(trace.node) ? 'large' : 'runtime',
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

  const ragMetrics = computed(() => {
    const latestSystem = [...messages.value].reverse().find((m) => m.role === 'system')
    const m = latestSystem?.metadata?.rag_metrics || {}

    return {
      recall: roundNumber(m.recall || 0, 1),
      hitRate: roundNumber(m.hit_rate || 0, 1),
      confidence: roundNumber(m.confidence || 0, 1),
      memoryCount: m.memory_count || 0,
      knowledgeCount: m.knowledge_count || 0,
      importantCount: m.important_count || 0,
      turnCount: messages.value.filter((msg) => msg.role === 'system').length,
    }
  })

  /** 会话级 RAG 历史：每轮的三率，供曲线图使用 */
  const ragHistory = computed(() => {
    const points = []
    let turnIndex = 0
    for (const msg of messages.value) {
      if (msg.role !== 'system') continue
      const m = msg.metadata?.rag_metrics
      if (!m) continue
      turnIndex++
      points.push({
        turn: turnIndex,
        recall: roundNumber(m.recall || 0, 1),
        hitRate: roundNumber(m.hit_rate || 0, 1),
        confidence: roundNumber(m.confidence || 0, 1),
      })
    }
    return points
  })

  const tokenSeries = computed(() => {
    const assistantMessages = messages.value.filter((message) => message.role === 'assistant')
    const modelTotals = {}

    return assistantMessages.map((message, index) => {
      const traces = safeArray(message.trace)
      const baseTokens = estimateTextTokens(message.content || '') + estimateToolTokens(message.tool_calls)

      /* 从 trace 中收集模型名,去重;无 model_name 时回退到 node 名 */
      const modelNames = []
      const seen = new Set()
      for (const trace of traces) {
        const name = trace.model_name || trace.node
        if (name && !seen.has(name)) {
          seen.add(name)
          modelNames.push(name)
        }
      }

      /* 将 token 均分给参与的各模型 */
      const modelTokens = {}
      if (modelNames.length === 0) {
        modelTokens['--'] = baseTokens
        modelTotals['--'] = (modelTotals['--'] || 0) + baseTokens
      } else {
        const perModel = Math.max(1, Math.round(baseTokens / modelNames.length))
        for (const name of modelNames) {
          modelTokens[name] = perModel
          modelTotals[name] = (modelTotals[name] || 0) + perModel
        }
      }

      /* 时间轴标签 */
      let label = `#${index + 1}`
      if (message.created_at) {
        const d = new Date(message.created_at)
        label = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      }

      return {
        id: `token-${index}`,
        label,
        modelTokens,
        totalTokens: baseTokens,
        modelTotals: { ...modelTotals },
      }
    })
  })

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
      modelTier: SMALL_MODEL_NODES.has(trace.node) ? 'small' : LARGE_MODEL_NODES.has(trace.node) ? 'large' : 'runtime',
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
