<!--
  Root application shell.

  Usage:
  - Initializes the shared theme store once.
  - Renders the active route for the editor front-end.
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterView } from 'vue-router'

import UserIdGate from '@/components/common/UserIdGate.vue'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const profileReady = ref(false)

onMounted(async () => {
  settingsStore.initTheme()
  if (settingsStore.hasUserId) {
    try {
      await settingsStore.refreshUserProfile()
    } catch {
      settingsStore.clearUserId()
    }
  }
  profileReady.value = true
})
</script>

<template>
  <div v-if="!profileReady" class="app-loading mono">loading profile</div>
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
  color: var(--color-text-muted);
  font-size: 12px;
}
</style>
