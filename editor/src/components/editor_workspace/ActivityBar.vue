<!--
  Editor activity bar.

  Usage:
  Renders the icon-only left rail for opening editor side panels and navigating
  to future workspace tools. Buttons expose native tooltips through title text.
-->
<script setup lang="ts">
import { Activity, Bot, Bug, DatabaseZap, Files, Folder, Search, Settings, Share2 } from 'lucide-vue-next'

defineProps<{
  fileOpen: boolean
  agentOpen: boolean
  resourcesActive: boolean
  ingestionActive: boolean
  agentActive: boolean
  graphActive: boolean
  dashboardActive: boolean
  debugActive: boolean
  searchActive: boolean
  settingsActive: boolean
}>()

const emit = defineEmits<{
  toggleFile: []
  openResources: []
  openIngestion: []
  toggleAgent: []
  toggleGraph: []
  openDashboard: []
  openDebug: []
  openSearch: []
  openSettings: []
}>()
</script>

<template>
  <nav class="activity-bar" aria-label="Editor activity bar">
    <button
      class="activity-button"
      :class="{ active: fileOpen }"
      type="button"
      title="Files"
      aria-label="Files"
      @click="emit('toggleFile')"
    >
      <Folder :size="18" />
    </button>
    <button
      class="activity-button"
      :class="{ active: resourcesActive }"
      type="button"
      title="File resources"
      aria-label="File resources"
      @click="emit('openResources')"
    >
      <Files :size="18" />
    </button>
    <button
      class="activity-button"
      :class="{ active: ingestionActive }"
      type="button"
      title="入库进度"
      aria-label="入库进度"
      @click="emit('openIngestion')"
    >
      <DatabaseZap :size="18" />
    </button>
    <button
      class="activity-button"
      :class="{ active: searchActive }"
      type="button"
      title="Search"
      aria-label="Search"
      @click="emit('openSearch')"
    >
      <Search :size="18" />
    </button>
    <button
      class="activity-button"
      :class="{ active: agentActive }"
      type="button"
      title="Agent"
      aria-label="Agent"
      @click="emit('toggleAgent')"
    >
      <Bot :size="18" />
    </button>
    <button
      class="activity-button"
      :class="{ active: graphActive }"
      type="button"
      title="Knowledge graph"
      aria-label="Knowledge graph"
      @click="emit('toggleGraph')"
    >
      <Share2 :size="18" />
    </button>
    <button
      class="activity-button"
      :class="{ active: dashboardActive }"
      type="button"
      title="Dashboard"
      aria-label="Dashboard"
      @click="emit('openDashboard')"
    >
      <Activity :size="18" />
    </button>
    <button
      class="activity-button"
      :class="{ active: debugActive }"
      type="button"
      title="Debug"
      aria-label="Debug"
      @click="emit('openDebug')"
    >
      <Bug :size="18" />
    </button>
    <button
      class="activity-button bottom-button"
      :class="{ active: settingsActive }"
      type="button"
      title="Settings"
      aria-label="Settings"
      @click="emit('openSettings')"
    >
      <Settings :size="18" />
    </button>
  </nav>
</template>

<style scoped>
.activity-bar {
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: var(--space-4);
  width: 100%;
  height: 100%;
  padding: var(--space-8) var(--space-4);
  background: var(--color-chrome-bg-solid);
}

.activity-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
}

.activity-button:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.activity-button.active {
  border-color: var(--color-primary);
  background: transparent;
  color: var(--color-primary);
}

.bottom-button {
  margin-top: auto;
}
</style>
