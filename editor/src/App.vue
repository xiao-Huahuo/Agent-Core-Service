<!--
  Root application shell.

  Usage:
  - Initializes the shared theme store once.
  - Renders the active route for the editor front-end.
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterView } from 'vue-router'

import WifiLoader from '@/components/common/WifiLoader.vue'
import UserIdGate from '@/components/common/UserIdGate.vue'
import FloatingAgentRoot from '@/components/floating/FloatingAgentRoot.vue'
import { isFloatingWindow } from '@/floating/isFloating'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const backendReady = ref(false)

async function waitForBackend(maxRetries = 120): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const r = await fetch('/health', { method: 'GET' })
      if (r.ok) return
    } catch { /* 后端未就绪 */ }
    await new Promise(r => setTimeout(r, 1000))
  }
}

async function waitForModelsReady(maxRetries = 300): Promise<void> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const r = await fetch('/settings/models/status')
      if (r.ok) {
        const s: Record<string, string> = await r.json()
        // embedding 和 rerank 都就绪即可结束；
        // 如果未下载或出错也结束（不卡住用户去手动下载）
        const e = s.embedding
        const rr = s.rerank
        if (e === 'ready' && rr === 'ready') return
        if (e === 'not_downloaded' || e === 'downloaded' || e === 'error') return
        if (rr === 'not_downloaded' || rr === 'downloaded' || rr === 'error') return
      }
    } catch { /* ignore */ }
    await new Promise(r => setTimeout(r, 1000))
  }
}

onMounted(async () => {
  settingsStore.initTheme()
  await waitForBackend()
  await waitForModelsReady()
  backendReady.value = true
  if (settingsStore.hasUserId) {
    try {
      await settingsStore.refreshUserProfile()
    } catch {
      settingsStore.clearUserId()
    }
  }
})
</script>

<template>
  <div v-if="!backendReady" class="app-loading">
    <WifiLoader />
  </div>
  <FloatingAgentRoot v-else-if="isFloatingWindow && settingsStore.hasUserId" />
  <RouterView v-else-if="settingsStore.hasUserId" />
  <UserIdGate v-else />
</template>

<style scoped>
.app-loading {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  background: var(--color-canvas);
}

</style>
