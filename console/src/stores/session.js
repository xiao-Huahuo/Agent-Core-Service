/*
 * 会话管理 Store。
 *
 * 功能说明:
 * 管理会话列表、当前选中会话及加载状态。
 * 会话数据从后端 REST API 获取,不持久化到 localStorage。
 *
 * 使用说明:
 * import { useSessionStore } from '@/stores/session'
 * const sessionStore = useSessionStore()
 * await sessionStore.loadSessions(userId)
 * sessionStore.selectSession(sessionId)
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { listSessions, createSession as apiCreateSession, deleteSession as apiDeleteSession, clearAllSessions as apiClearAllSessions, updateSessionName as apiUpdateSessionName } from '@/api/session'

export const useSessionStore = defineStore('session', () => {
  /* ================================================================
   * 状态
   * ================================================================ */

  /** @type {import('vue').Ref<Array<{session_id:string,user_id:string,session_name:string,created_at:string,updated_at:string}>>} */
  const sessions = ref([])

  /** @type {import('vue').Ref<string|null>} */
  const currentSessionId = ref(null)

  /** @type {import('vue').Ref<boolean>} */
  const isLoading = ref(false)

  /* ================================================================
   * 计算属性
   * ================================================================ */

  /** 当前选中的会话对象 */
  const currentSession = computed(() =>
    sessions.value.find(s => s.session_id === currentSessionId.value) || null
  )

  /** 会话列表是否为空 */
  const hasSessions = computed(() => sessions.value.length > 0)

  /* ================================================================
   * 方法
   * ================================================================ */

  /**
   * 从服务端加载用户的会话列表,按 updated_at 倒序排列。
   *
   * @param {string} userId 用户 ID
   */
  async function load(userId) {
    if (!userId) return
    isLoading.value = true
    try {
      sessions.value = await listSessions(userId)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 创建新会话并自动选中。
   *
   * @param {string} userId 用户 ID
   * @param {string} [sessionName] 可选会话名称
   * @returns {Promise<string>} 新创建的 session_id
   */
  async function create(userId, sessionName) {
    const newSession = await apiCreateSession(userId, sessionName)
    sessions.value.unshift(newSession)
    return newSession.session_id
  }

  /**
   * 选中指定会话。
   *
   * @param {string} sessionId 会话 ID
   */
  function select(sessionId) {
    currentSessionId.value = sessionId
  }

  /**
   * 取消选中当前会话,回到空白状态。
   */
  function clearSelection() {
    currentSessionId.value = null
  }

  /**
   * 删除指定会话。
   *
   * @param {string} sessionId 会话 ID
   */
  async function remove(sessionId) {
    await apiDeleteSession(sessionId)
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
    }
  }

  /**
   * 清空当前用户的所有会话。
   *
   * @param {string} userId 用户 ID
   */
  async function clearAll(userId) {
    await apiClearAllSessions(userId)
    sessions.value = []
    currentSessionId.value = null
  }

  /**
   * 更新会话名称。
   *
   * @param {string} sessionId 会话 ID
   * @param {string} sessionName 新的会话名称
   */
  async function rename(sessionId, sessionName) {
    await apiUpdateSessionName(sessionId, sessionName)
    const session = sessions.value.find(s => s.session_id === sessionId)
    if (session) {
      session.session_name = sessionName
    }
  }

  return {
    sessions,
    currentSessionId,
    isLoading,
    currentSession,
    hasSessions,
    load,
    create,
    select,
    clearSelection,
    remove,
    clearAll,
    rename,
  }
})
