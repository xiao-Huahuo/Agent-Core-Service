<!--
  DashboardView —— time and consumption observability page.
-->

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import TimeConsumptionPanel from '@/components/dashboard/TimeConsumptionPanel.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()

const userId = settingsStore.profile.userId

async function ensureObsHistoryLoaded() {
  if (!userId) return
  if (sessionStore.sessions.length === 0) {
    await sessionStore.load(userId)
  }

  let sessionId = sessionStore.currentSessionId
  if (!sessionId && sessionStore.sessions.length > 0) {
    sessionId = sessionStore.sessions[0]!.session_id
    sessionStore.select(sessionId)
  }

  if (!sessionId) return
  if (chatStore.loadedSessionId === sessionId && chatStore.messages.length > 0) return
  await chatStore.loadHistory(sessionId, userId, 200)
}

watch(
  () => [userId, sessionStore.currentSessionId, sessionStore.sessions.length],
  () => {
    ensureObsHistoryLoaded()
  },
  { immediate: true },
)

onMounted(() => {
  ensureObsHistoryLoaded()
})
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
  overflow: hidden;
}

@media (max-width: 768px) {
  .dashboard-view {
    display: block;
    overflow: auto;
  }
}
</style>
