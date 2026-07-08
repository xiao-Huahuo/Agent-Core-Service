/*
 * 聊天消息 Store。
 *
 * 功能说明:
 * 管理当前会话的消息列表、流式对话状态和消息发送逻辑。
 * 发送消息时调用 SSE 流式接口,逐块更新助手回复内容。
 *
 * 使用说明:
 * import { useChatStore } from '@/stores/chat'
 * const chatStore = useChatStore()
 * await chatStore.send(userId, sessionId, prompt)
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { streamPrompt } from '@/api/agent'
import { fetchMessages } from '@/api/session'
import { useSessionStore } from '@/stores/session'

export const useChatStore = defineStore('chat', () => {
  /* ================================================================
   * 状态
   * ================================================================ */

  /** @type {import('vue').Ref<Array<{role:string,content:string,message_id?:string,node?:string,tool_calls?:Array,trace?:Array,created_at?:string}>>} */
  const messages = ref([])

  /** @type {import('vue').Ref<boolean>} */
  const isStreaming = ref(false)

  /** 当前流式事件所属节点名称 */
  const currentNode = ref('')

  /** 流式传输过程中的错误信息 */
  const streamError = ref('')

  /** 当前已加载到消息列表中的会话 ID,供观测面板判断是否需要补拉历史。 */
  const loadedSessionId = ref('')

  /** 模型收到的完整上下文镜像 (序列化后的消息列表), 供 Obs 面板 Raw 视图使用。 */
  const contextMirror = ref([])

  /** 用于取消正在进行的流式发送请求 */
  let _streamAbortController = null

  /** 用于取消正在进行的历史消息加载请求 */
  let _historyAbortController = null

  /* ================================================================
   * 计算属性
   * ================================================================ */

  /** 最后一条消息(通常是当前正在流式输出的助手消息) */
  const lastMessage = computed(() =>
    messages.value.length > 0 ? messages.value[messages.value.length - 1] : null
  )

  /** 是否可以发送新消息(非流式中) */
  const canSend = computed(() => !isStreaming.value)

  /* ================================================================
   * 内部方法
   * ================================================================ */

  /**
   * 向消息列表添加一条消息。
   */
  function appendMessage(msg) {
    messages.value.push({ ...msg })
  }

  function findLastAssistant() {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'assistant') return messages.value[i]
    }
    return null
  }

  function updateLastMessage(content, node, toolCalls, trace) {
    const last = findLastAssistant()
    if (!last) return
    if (content !== undefined) last.content = content
    if (node !== undefined) last.node = node
    if (toolCalls !== undefined) last.tool_calls = toolCalls
    if (trace !== undefined && trace.length > 0) {
      if (!last.trace) last.trace = []
      last.trace.push(...trace)
    }
  }

  /*
   * 流式内容节流: 避免每个 token 都触发完整 Vue 响应链
   * (visibleMessages 重算 → 模板重渲染 → vdom diff → scroll)。
   * content 以固定间隔 (~50ms) 写入响应式对象, 其它字段立即写入。
   */
  let _pendingContent = ''
  let _flushTimer = null
  const CONTENT_FLUSH_MS = 50

  function flushStreamContent() {
    _flushTimer = null
    if (!_pendingContent) return
    const last = findLastAssistant()
    if (last) last.content = _pendingContent
  }

  function scheduleContentFlush() {
    if (_flushTimer !== null) return
    _flushTimer = setTimeout(flushStreamContent, CONTENT_FLUSH_MS)
  }

  function updateStreamContent(content) {
    _pendingContent = content
    scheduleContentFlush()
  }

  function forceFlushContent() {
    if (_flushTimer !== null) clearTimeout(_flushTimer)
    flushStreamContent()
    _pendingContent = ''
  }

  /* ================================================================
   * 公开方法
   * ================================================================ */

  /**
   * 从服务端加载会话的历史消息。
   */
  async function loadHistory(sessionId, userId, limit = 50) {
    _historyAbortController?.abort()
    _historyAbortController = new AbortController()
    const { signal } = _historyAbortController

    messages.value = []
    try {
      const history = await fetchMessages(sessionId, userId, limit, { signal })
      messages.value = history
        .filter(m => m.role !== 'tool' || m.metadata?.node === 'action')
        .filter(m => m.role !== 'assistant' || m.content || (m.tool_calls && m.tool_calls.length > 0) || m.metadata?.node === 'action')
        .map(m => ({
          role: m.role === 'tool' ? 'assistant' : m.role,
          content: m.content,
          message_id: m.message_id,
          node: m.metadata?.node || '',
          tool_calls: m.tool_calls,
          metadata: m.metadata || {},
          trace: m.metadata?.trace || [],
          created_at: m.created_at,
        }))
      loadedSessionId.value = sessionId
    } catch (err) {
      if (err.name === 'AbortError') return
      console.error('加载历史消息失败:', err)
      messages.value = []
      loadedSessionId.value = ''
    }
  }

  /**
   * 发送用户消息并开始流式对话。
   *
   * 不预先创建 assistant 占位消息 — “思考中”的气泡由 MessageList 模板
   * 根据 isStreaming 标志直接渲染,不受任何异步时序影响。
   * trace 优先到达时暂存缓冲,第一条有内容或 tool_calls 的事件到达时才创建
   * assistant 消息,并将缓冲的 trace 一次性注入。
   */
  async function send(userId, sessionId, prompt) {
    if (!prompt.trim()) return
    const sessionStore = useSessionStore()
    let targetSessionId = sessionId || sessionStore.currentSessionId

    /* 如果正在流式输出,中断上一次请求 */
    if (isStreaming.value) {
      _streamAbortController?.abort()
      forceFlushContent()
      isStreaming.value = false
      const lastAssistant = findLastAssistant()
      if (lastAssistant) {
        lastAssistant.node = 'interrupted'
      }
    }

    /* 用户消息入列 */
    appendMessage({ role: 'user', content: prompt, created_at: new Date().toISOString() })

    _streamAbortController = new AbortController()
    const { signal } = _streamAbortController
    isStreaming.value = true
    streamError.value = ''

    const bufferedTraces = []
    let assistantCreated = false
    let activeNode = ''

    function ensureAssistant(node) {
      if (assistantCreated && activeNode === node) return
      appendMessage({
        role: 'assistant',
        content: '',
        node: node || '',
        tool_calls: [],
        trace: [...bufferedTraces],
        created_at: new Date().toISOString(),
      })
      assistantCreated = true
      activeNode = node
      bufferedTraces.length = 0
    }

    try {
      if (!targetSessionId) {
        targetSessionId = await sessionStore.create(userId)
        sessionStore.select(targetSessionId)
      }

      for await (const chunk of streamPrompt(userId, targetSessionId, prompt, { signal })) {
        currentNode.value = chunk.node || ''

        /* 系统提示事件: 将 system prompt 注入消息列表供 Obs 面板上下文拼装使用。
           每轮只保留最新一条, 避免旧轮次系统消息污染当前上下文拼装视图。 */
        if (chunk.type === 'system_prompt' && chunk.content) {
          messages.value = messages.value.filter(m => m.role !== 'system')
          messages.value.push({
            role: 'system',
            content: chunk.content,
            metadata: chunk.metadata || {},
          })
          continue
        }

        /* 上下文镜像: 模型收到的完整消息列表, 供 Obs 面板 Raw 视图展示真实 context */
        if (chunk.type === 'context_mirror' && chunk.context_messages) {
          contextMirror.value = chunk.context_messages
          continue
        }

        /* tool_trace 事件(action 节点): 仅 tool_call_end 才创建/更新气泡,实现数字滚动 */
        if (chunk.node === 'action' && !chunk.content && chunk.trace && chunk.trace.length > 0) {
          const endTraces = chunk.trace.filter(t => t.event === 'tool_call_end')
          if (endTraces.length > 0) {
            ensureAssistant('action')
            const la = findLastAssistant()
            if (la) {
              if (!la.trace) la.trace = []
              la.trace.push(...bufferedTraces, ...chunk.trace)
              bufferedTraces.length = 0
            }
          } else {
            bufferedTraces.push(...chunk.trace)
          }
          continue
        }

        /* action 节点(有内容): 只更新内容,不追加 trace(node 事件的 trace 与 tool_trace 重复) */
        if (chunk.node === 'action' && chunk.content) {
          ensureAssistant(chunk.node)
          updateStreamContent(chunk.content)
          updateLastMessage(undefined, chunk.node, undefined, undefined)
          continue
        }

        /* 有实质文本内容 → 确保 assistant 存在, 内容节流写入 */
        if (chunk.content) {
          ensureAssistant(chunk.node)
          updateStreamContent(chunk.content)
          updateLastMessage(undefined, chunk.node, chunk.tool_calls, chunk.trace)
        } else if (chunk.trace && chunk.trace.length > 0) {
          /* 仅有 trace 的事件 */
          if (assistantCreated) {
            const la = findLastAssistant()
            if (la) {
              if (!la.trace) la.trace = []
              la.trace.push(...chunk.trace)
            }
          } else {
            bufferedTraces.push(...chunk.trace)
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') return
      forceFlushContent()
      streamError.value = err.message || 'Stream connection failed'
      if (assistantCreated) {
        updateLastMessage(streamError.value, undefined, undefined, undefined)
      }
    } finally {
      if (signal.aborted) return
      forceFlushContent()
      isStreaming.value = false
      currentNode.value = ''
      loadedSessionId.value = targetSessionId || ''
      if (targetSessionId) {
        try {
          await sessionStore.load(userId)
        } catch { /* 非关键 */ }
      }
    }
  }

  /**
   * 清空当前消息列表,中止正在进行的请求。
   */
  function clear() {
    _streamAbortController?.abort()
    _historyAbortController?.abort()
    _streamAbortController = null
    _historyAbortController = null
    messages.value = []
    contextMirror.value = []
    isStreaming.value = false
    streamError.value = ''
    currentNode.value = ''
    loadedSessionId.value = ''
  }

  return {
    messages,
    isStreaming,
    currentNode,
    streamError,
    loadedSessionId,
    contextMirror,
    lastMessage,
    canSend,
    loadHistory,
    send,
    clear,
  }
})
