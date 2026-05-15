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
   * @param {Array} [trace] trace 事件列表
   */
  function updateLastMessage(content, node, toolCalls, trace) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') {
      last.content = content
      if (node !== undefined) last.node = node
      if (toolCalls !== undefined) last.tool_calls = toolCalls
      if (trace !== undefined) last.trace = trace
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
    messages.value = []
    try {
      const history = await fetchMessages(sessionId, userId, limit)
      messages.value = history.map(m => ({
        role: m.role,
        content: m.content,
        message_id: m.message_id,
        tool_calls: m.tool_calls,
        trace: m.metadata?.trace || [],
        created_at: m.created_at,
      }))
    } catch (err) {
      console.error('加载历史消息失败:', err)
      messages.value = []
    }
  }

  /**
   * 发送用户消息并开始流式对话。
   *
   * 流程:
   * 1. 将用户消息加入 messages
   * 2. 添加占位助手消息
   * 3. 调用 SSE 流接口,逐块更新助手消息内容
   * 4. 流结束时最终化消息
   *
   * @param {string} userId 用户 ID
   * @param {string} sessionId 会话 ID
   * @param {string} prompt 用户输入文本
   */
  async function send(userId, sessionId, prompt) {
    if (!prompt.trim() || isStreaming.value) return

    /* 用户消息入列 */
    appendMessage({ role: 'user', content: prompt })

    /* 助手占位消息 */
    appendMessage({ role: 'assistant', content: '', node: '', tool_calls: [], trace: [] })

    isStreaming.value = true
    streamError.value = ''

    try {
      for await (const chunk of streamPrompt(userId, sessionId, prompt)) {
        currentNode.value = chunk.node || ''
        /* 始终更新节点标签，让用户看到进度（如 safety_input → planner → agent） */
        const last = messages.value[messages.value.length - 1]
        if (last && last.role === 'assistant') {
          if (chunk.node) last.node = chunk.node
        }
        /* 有内容或 tool_calls 时更新消息体 */
        if (chunk.content || (chunk.tool_calls && chunk.tool_calls.length > 0)) {
          updateLastMessage(
            chunk.content,
            chunk.node,
            chunk.tool_calls,
            chunk.trace
          )
        }
      }
    } catch (err) {
      streamError.value = err.message || 'Stream connection failed'
      /* 在助手消息中显示错误 */
      updateLastMessage(
        streamError.value,
        undefined,
        undefined,
        undefined
      )
    } finally {
      isStreaming.value = false
      currentNode.value = ''
      /* 流式结束后刷新会话列表(获取后台自动生成的标题) */
      try {
        const sessionStore = useSessionStore()
        await sessionStore.load(userId)
      } catch { /* 非关键 */ }
    }
  }

  /**
   * 清空当前消息列表。
   */
  function clear() {
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
