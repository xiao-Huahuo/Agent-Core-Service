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

function handleRipple(e: MouseEvent) {
  const el = e.currentTarget as HTMLElement
  const ripple = document.createElement('span')
  ripple.className = 'ripple-effect'
  el.appendChild(ripple)
  ripple.addEventListener('animationend', () => ripple.remove(), { once: true })
}
</script>

<template>
  <nav class="activity-bar" aria-label="Editor activity bar">
    <button
      class="activity-button"
      :class="{ active: fileOpen }"
      type="button"
      title="Files"
      aria-label="Files"
      @mousedown.prevent="handleRipple"
      @click="emit('toggleFile')"
    >
      <Files :size="18" />
    </button>
    <button
      class="activity-button"
      :class="{ active: resourcesActive }"
      type="button"
      title="File resources"
      aria-label="File resources"
      @mousedown.prevent="handleRipple"
      @click="emit('openResources')"
    >
      <Folder :size="18" />
    </button>
    <button
      class="activity-button"
      :class="{ active: ingestionActive }"
      type="button"
      title="入库进度"
      aria-label="入库进度"
      @mousedown.prevent="handleRipple"
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
      @mousedown.prevent="handleRipple"
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
      @mousedown.prevent="handleRipple"
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
      @mousedown.prevent="handleRipple"
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
      @mousedown.prevent="handleRipple"
      @click="emit('openDashboard')"
    >
      <Activity :size="18" />
    </button>
    <div class="bottom-group">
      <button
        class="activity-button"
        :class="{ active: debugActive }"
        type="button"
        title="Debug"
        aria-label="Debug"
        @mousedown.prevent="handleRipple"
      @click="emit('openDebug')"
      >
        <Bug :size="18" />
      </button>
      <button
        class="activity-button"
        :class="{ active: settingsActive }"
        type="button"
        title="Settings"
        aria-label="Settings"
        @mousedown.prevent="handleRipple"
      @click="emit('openSettings')"
      >
        <Settings :size="18" />
      </button>
    </div>
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
  background: var(--color-chrome-rail-bg);
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
  position: relative;
  overflow: hidden;
  transition: background 0.25s, border-color 0.25s, color 0.25s;
}

.ripple-effect {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: var(--color-primary);
  animation: ripple-expand 0.35s ease-out;
  pointer-events: none;
  will-change: transform;
  z-index: 2;
}

@keyframes ripple-expand {
  0% {
    transform: scale(0);
    opacity: 1;
  }
  100% {
    transform: scale(2.5);
    opacity: 0;
  }
}

.activity-button:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.activity-button.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #ffffff;
}

.bottom-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  margin-top: auto;
}
</style>
