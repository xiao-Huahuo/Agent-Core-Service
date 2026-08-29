<!--
  DashboardView —— time and consumption observability page.
-->

<script setup lang="ts">
import { computed, watch } from 'vue'
import TimeConsumptionPanel from '@/components/dashboard/TimeConsumptionPanel.vue'
import { useObsHistory } from '@/composable/useObsHistory'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()
const obsHistory = useObsHistory()

const userId = computed(() => settingsStore.profile.userId)

/** Ensure only the current-session context needed by non-history cards is loaded. */
async function ensureDashboardContextLoaded() {
  const activeUserId = userId.value
  if (!activeUserId) return
  if (sessionStore.sessions.length === 0) {
    await sessionStore.load(activeUserId)
  }

  let sessionId = sessionStore.currentSessionId
  if (!sessionId && sessionStore.sessions.length > 0) {
    sessionId = sessionStore.sessions[0]!.session_id
    sessionStore.select(sessionId)
  }

  if (sessionId && (chatStore.loadedSessionId !== sessionId || chatStore.messages.length === 0)) {
    await chatStore.loadHistory(sessionId, activeUserId, 200)
  }
}

watch(
  () => [userId.value, sessionStore.currentSessionId, sessionStore.sessions.length],
  () => {
    ensureDashboardContextLoaded()
  },
  { immediate: true },
)

watch(
  () => chatStore.isStreaming,
  (streaming, wasStreaming) => {
    if (!streaming && wasStreaming) {
      void obsHistory.refreshLoaded(userId.value, sessionStore.sessions)
    }
  },
)
</script>

<template>
  <div class="dashboard-view">
    <TimeConsumptionPanel />
  </div>
</template>

<style scoped>
.dashboard-view {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
}
</style>
