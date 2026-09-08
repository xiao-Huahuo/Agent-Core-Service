<!--
  Favorites page.

  Usage:
  Provides a workspace page for backend-persisted favorites. The page reuses the
  file resource manager, virtual library, and Agent session drawer with their
  favorites filters locked on.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import FileResourceManager from '@/components/editor_workspace/FileResourceManager.vue'
import FavoriteSessionList from '@/components/editor_workspace/agent_chat/FavoriteSessionList.vue'
import ScannerFavoritesPanel from '@/components/scanner_view/ScannerFavoritesPanel.vue'
import ComponentLibraryView from '@/views/ComponentLibraryView.vue'
import LibraryView from '@/views/LibraryView.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

defineOptions({ name: 'FavoritesView' })

const props = withDefaults(defineProps<{
  privacyMode?: boolean
}>(), {
  privacyMode: false,
})

type FavoriteTab = 'files' | 'library' | 'components' | 'sessions' | 'scanner'

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const activeTab = ref<FavoriteTab>('files')
const switchRef = ref<HTMLElement | null>(null)
const sliderStyle = ref({ width: '0px', left: '0px' })
const favoriteTabs: Array<{ value: FavoriteTab; label: string; icon: string }> = [
  { value: 'files', label: '文件', icon: 'document' },
  { value: 'library', label: '图书馆', icon: 'book' },
  { value: 'components', label: '组件', icon: 'grid-view' },
  { value: 'sessions', label: '会话', icon: 'forum' },
  { value: 'scanner', label: '扫描器', icon: 'document' },
]
const tabs = computed(() => props.privacyMode ? favoriteTabs.slice(0, 2) : favoriteTabs)

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
      <div ref="switchRef" class="favorites-switch" :aria-label="privacyMode ? '隐私分类' : '收藏分类'">
        <div class="favorites-slider" :style="sliderStyle"></div>
        <button
          v-for="tab in tabs"
          :key="tab.value"
          class="favorites-switch-button"
          :class="{ active: activeTab === tab.value }"
          type="button"
          @click="switchTab(tab.value)"
        >
          <IcIcon :name="tab.icon" :size="17" />
          <span>{{ tab.label }}</span>
        </button>
      </div>
    </header>

    <main class="favorites-body">
      <FileResourceManager v-if="activeTab === 'files'" :favorites-only-locked="!privacyMode" :privacy-only-locked="privacyMode" />
      <LibraryView v-else-if="activeTab === 'library'" :favorites-only-locked="!privacyMode" :privacy-only-locked="privacyMode" />
      <ComponentLibraryView v-else-if="activeTab === 'components'" favorites-only-locked />
      <FavoriteSessionList v-else-if="activeTab === 'sessions'" :user-id="settingsStore.profile.userId" @select="openAgentSession" />
      <ScannerFavoritesPanel v-else />
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
  min-height: 44px;
  padding: var(--space-8) var(--space-12);
  border-bottom: 0;
  font-size: calc(12px * var(--font-scale));
}

.favorites-switch {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  height: 28px;
  padding: 0 var(--space-8);
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(12px * var(--font-scale));
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
