/*
 * Agent chat session store.
 *
 * Usage:
 * Keeps editor Agent panel sessions synchronized with the backend session API.
 * The same user_id sees the same sessions in console and editor.
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  clearAllSessions,
  createSession,
  deleteSession,
  listSessions,
  pruneEmptySessions,
  updateSessionName,
  type SessionRecord,
} from '@/api/session'

export const useSessionStore = defineStore('session', () => {
  const sessions = ref<SessionRecord[]>([])
  const currentSessionId = ref<string | null>(null)
  const isLoading = ref(false)

  const currentSession = computed(
    () => sessions.value.find((session) => session.session_id === currentSessionId.value) ?? null,
  )

  const hasSessions = computed(() => sessions.value.length > 0)

  async function load(userId: string) {
    if (!userId) {
      return
    }
    isLoading.value = true
    try {
      sessions.value = await listSessions(userId)
      if (currentSessionId.value && !sessions.value.some((session) => session.session_id === currentSessionId.value)) {
        currentSessionId.value = null
      }
    } finally {
      isLoading.value = false
    }
  }

  async function create(userId: string, sessionName?: string): Promise<string> {
    const session = await createSession(userId, sessionName)
    sessions.value = [session, ...sessions.value.filter((item) => item.session_id !== session.session_id)]
    currentSessionId.value = session.session_id
    return session.session_id
  }

  function select(sessionId: string) {
    currentSessionId.value = sessionId
  }

  function clearSelection() {
    currentSessionId.value = null
  }

  async function remove(sessionId: string) {
    await deleteSession(sessionId)
    sessions.value = sessions.value.filter((session) => session.session_id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = null
    }
  }

  async function clearAll(userId: string) {
    await clearAllSessions(userId)
    sessions.value = []
    currentSessionId.value = null
  }

  async function rename(sessionId: string, sessionName: string) {
    await updateSessionName(sessionId, sessionName)
    const session = sessions.value.find((item) => item.session_id === sessionId)
    if (session) {
      session.session_name = sessionName
    }
  }

  function renameLocal(sessionId: string, sessionName: string) {
    const session = sessions.value.find((item) => item.session_id === sessionId)
    if (session) {
      session.session_name = sessionName
    }
  }

  async function pruneEmpty(userId: string) {
    try {
      await pruneEmptySessions(userId)
      await load(userId)
    } catch {
      // non-critical
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
    renameLocal,
    pruneEmpty,
  }
})
