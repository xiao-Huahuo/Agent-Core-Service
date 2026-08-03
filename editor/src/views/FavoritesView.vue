<!--
  Favorites page.

  Usage:
  Provides a workspace page for backend-persisted favorites. The page reuses the
  file resource manager, virtual library, and Agent session drawer with their
  favorites filters locked on.
-->
<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'

import FileResourceManager from '@/components/editor_workspace/FileResourceManager.vue'
import FavoriteSessionList from '@/components/editor_workspace/agent_chat/FavoriteSessionList.vue'
import LibraryView from '@/views/LibraryView.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

defineOptions({ name: 'FavoritesView' })

type FavoriteTab = 'files' | 'library' | 'sessions'

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const activeTab = ref<FavoriteTab>('files')
const switchRef = ref<HTMLElement | null>(null)
const sliderStyle = ref({ width: '0px', left: '0px' })
const tabs: Array<{ value: FavoriteTab; label: string }> = [
  { value: 'files', label: '文件' },
  { value: 'library', label: '图书馆' },
  { value: 'sessions', label: '会话' },
]

function updateSlider() {
  nextTick(() => {
    const container = switchRef.value
    if (!container) return
    const active = container.querySelector('.favorites-switch-button.active') as HTMLElement | null
    if (!active) return
    sliderStyle.value = {
      width: `${active.offsetWidth}px`,
      left: `${active.offsetLeft}px`,
    }
  })
}

function switchTab(tab: FavoriteTab) {
  activeTab.value = tab
  updateSlider()
}

function openAgentSession() {
  workspaceStore.setMainView('agent')
}

onMounted(updateSlider)
</script>

<template>
  <section class="favorites-view">
    <header class="favorites-toolbar">
      <div ref="switchRef" class="favorites-switch" aria-label="收藏分类">
        <div class="favorites-slider" :style="sliderStyle"></div>
        <button
          v-for="tab in tabs"
          :key="tab.value"
          class="favorites-switch-button"
          :class="{ active: activeTab === tab.value }"
          type="button"
          @click="switchTab(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
    </header>

    <main class="favorites-body">
      <FileResourceManager v-if="activeTab === 'files'" favorites-only-locked />
      <LibraryView v-else-if="activeTab === 'library'" favorites-only-locked />
      <FavoriteSessionList v-else :user-id="settingsStore.profile.userId" @select="openAgentSession" />
    </main>
  </section>
</template>

<style scoped>
.favorites-view {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  background: var(--color-bg-app);
}

.favorites-toolbar {
  display: flex;
  align-items: center;
  min-height: 48px;
  padding: var(--space-8) var(--space-12);
  border-bottom: 0;
}

.favorites-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
}

.favorites-slider {
  position: absolute;
  top: 2px;
  height: calc(100% - 4px);
  border-radius: 999px;
  background: var(--color-primary-softer);
  transition: left 250ms ease, width 250ms ease;
  z-index: 0;
  pointer-events: none;
}

.favorites-switch-button {
  position: relative;
  z-index: 1;
  height: 26px;
  padding: 0 var(--space-10);
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
  outline: none;
}

.favorites-switch-button:hover {
  color: var(--color-primary);
}

.favorites-switch-button.active {
  color: var(--color-primary);
}

.favorites-body {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

</style>
