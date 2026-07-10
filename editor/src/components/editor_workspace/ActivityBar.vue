<!--
  Editor activity bar.

  Usage:
  Renders the icon-only left rail for opening editor side panels and navigating
  to future workspace tools. Buttons expose native tooltips through title text.
-->
<script setup lang="ts">
import { Activity, Bot, Folder, GitBranch, Search, Settings, Share2 } from 'lucide-vue-next'

defineProps<{
  fileOpen: boolean
  agentOpen: boolean
  graphActive: boolean
  dashboardActive: boolean
  searchActive: boolean
  settingsActive: boolean
}>()

const emit = defineEmits<{
  toggleFile: []
  toggleAgent: []
  toggleGraph: []
  openDashboard: []
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
    <button class="activity-button" type="button" title="Git" aria-label="Git">
      <GitBranch :size="18" />
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
      :class="{ active: agentOpen }"
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
  border-right: 1px solid var(--color-border);
  background: var(--color-canvas);
}

.activity-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-muted);
}

.activity-button:hover,
.activity-button.active {
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.activity-button.active {
  color: var(--color-selection-blue);
}

.bottom-button {
  margin-top: auto;
}
</style>
