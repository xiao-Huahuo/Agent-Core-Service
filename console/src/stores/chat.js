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

  /** 用于取消正在进行的请求(加载历史、发送消息) */
  let _abortController = null

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
   *
   * @param {{role:string,content:string,message_id?:string,node?:string,tool_calls?:Array,trace?:Array,created_at?:string}} msg
   */
  function appendMessage(msg) {
    messages.value.push({ ...msg })
  }

  /**
   * 更新最后一条消息的内容和元数据。
   *
   * @param {string} content 累积的完整内容
   * @param {string} [node] 当前节点名
   * @param {Array} [toolCalls] 工具调用列表
   * @param {Array} [trace] trace 事件列表(追加而非替换)
   */
  function findLastAssistant() {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].role === 'assistant') return messages.value[i]
    }
    return null
  }

  function updateLastMessage(content, node, toolCalls, trace) {
    const last = findLastAssistant()
    if (!last) return
    last.content = content
    if (node !== undefined) last.node = node
    if (toolCalls !== undefined) last.tool_calls = toolCalls
    if (trace !== undefined && trace.length > 0) {
      if (!last.trace) last.trace = []
      last.trace.push(...trace)
    }
  }

  /* ================================================================
   * 公开方法
   * ================================================================ */

  /**
   * 从服务端加载会话的历史消息。
   *
   * @param {string} sessionId 会话 ID
   * @param {string} userId 用户 ID
   * @param {number} [limit=50] 返回数量上限
   */
  async function loadHistory(sessionId, userId, limit = 50) {
    _abortController?.abort()
    _abortController = new AbortController()
    const { signal } = _abortController

    messages.value = []
    try {
      const history = await fetchMessages(sessionId, userId, limit, { signal })
      messages.value = history
        .filter(m => m.role !== 'tool')
        .map(m => ({
          role: m.role,
          content: m.content,
          message_id: m.message_id,
          tool_calls: m.tool_calls,
          trace: m.metadata?.trace || [],
          created_at: m.created_at,
        }))
    } catch (err) {
      if (err.name === 'AbortError') return
      console.error('加载历史消息失败:', err)
      messages.value = []
    }
  }

  /**
   * 发送用户消息并开始流式对话。
   *
   * 如果当前正在流式输出,会先中断上一次请求,保留已输出的部分内容,
   * 然后立即发送新的 prompt。
   *
   * @param {string} userId 用户 ID
   * @param {string} sessionId 会话 ID
   * @param {string} prompt 用户输入文本
   */
  async function send(userId, sessionId, prompt) {
    if (!prompt.trim()) return

    /* 如果正在流式输出,中断上一次请求 */
    if (isStreaming.value) {
      _abortController?.abort()
      isStreaming.value = false
      const lastAssistant = findLastAssistant()
      if (lastAssistant) {
        lastAssistant.node = 'interrupted'
      }
    }

    /* 用户消息入列 */
    appendMessage({ role: 'user', content: prompt })

    /* 助手占位消息 */
    appendMessage({ role: 'assistant', content: '', node: '', tool_calls: [], trace: [] })

    _abortController = new AbortController()
    const { signal } = _abortController
    isStreaming.value = true
    streamError.value = ''

    try {
      for await (const chunk of streamPrompt(userId, sessionId, prompt, { signal })) {
        currentNode.value = chunk.node || ''

        /* action 节点: trace 附加到 assistant 占位,工具结果已在思考步骤中展示 */
        if (chunk.node === 'action' && chunk.content) {
          const lastAssistant = findLastAssistant()
          if (lastAssistant) {
            lastAssistant.node = chunk.node
            if (chunk.trace && chunk.trace.length > 0) {
              if (!lastAssistant.trace) lastAssistant.trace = []
              lastAssistant.trace.push(...chunk.trace)
            }
          }
          continue
        }

        /* 普通节点事件: 更新 assistant 占位消息 */
        const lastAssistant = findLastAssistant()
        if (lastAssistant) {
          if (chunk.node) lastAssistant.node = chunk.node
        }
        if (chunk.content || (chunk.tool_calls && chunk.tool_calls.length > 0)) {
          updateLastMessage(
            chunk.content,
            chunk.node,
            chunk.tool_calls,
            chunk.trace
          )
        } else if (chunk.trace && chunk.trace.length > 0) {
          /* trace 仅有事件(planner/reflection/compress): 附加 trace 到 assistant */
          if (lastAssistant) {
            if (!lastAssistant.trace) lastAssistant.trace = []
            lastAssistant.trace.push(...chunk.trace)
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') return
      streamError.value = err.message || 'Stream connection failed'
      updateLastMessage(
        streamError.value,
        undefined,
        undefined,
        undefined
      )
    } finally {
      /* 如果 signal 已被新请求 abort,跳过清理,让新请求接管 */
      if (signal.aborted) return
      isStreaming.value = false
      currentNode.value = ''
      try {
        const sessionStore = useSessionStore()
        await sessionStore.load(userId)
      } catch { /* 非关键 */ }
    }
  }

  /**
   * 清空当前消息列表,中止正在进行的请求。
   */
  function clear() {
    _abortController?.abort()
    _abortController = null
    messages.value = []
    isStreaming.value = false
    streamError.value = ''
    currentNode.value = ''
  }

  return {
    messages,
    isStreaming,
    currentNode,
    streamError,
    lastMessage,
    canSend,
    loadHistory,
    send,
    clear,
  }
})
