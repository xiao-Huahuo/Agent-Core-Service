<!--
  Top command bar.

  Usage:
  Shows the active knowledge root, global actions, theme switch, and navigation
  links between the editor, graph preview, settings, and existing console.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CheckSquare, DatabaseZap, Maximize2, Minus, Moon, Network, Settings, Sun, X } from 'lucide-vue-next'

import SearchPalette from '@/components/editor_workspace/SearchPalette.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const desktopApi = window.agentEditorDesktop
const emit = defineEmits<{
  toggleAgent: []
  toggleTodo: []
  openAgentPage: []
  openSettings: []
}>()
const graphRebuilding = computed(() => workspaceStore.graphQueue.length > 0)
const todoActive = computed(() => workspaceStore.todoSidebarOpen)
const agentActive = computed(() => workspaceStore.agentSidebarOpen)
const logoSrc = new URL('../../assets/images/无底图标.png', import.meta.url).href

const switchingRoot = ref(false)
const savingLibraryName = ref(false)
const libraryNameDraft = ref('')
const activeLibraryName = computed(() => {
  return settingsStore.activeKnowledgeLibrary?.name?.trim() || settingsStore.profile.knowledgeDir
})

watch(
  activeLibraryName,
  (name) => {
    libraryNameDraft.value = name
  },
  { immediate: true },
)

async function openRootPicker() {
  if (!window.agentEditorDesktop?.selectDirectory) return
  const selectedDir = await window.agentEditorDesktop.selectDirectory()
  if (!selectedDir) return
  switchingRoot.value = true
  try {
    await settingsStore.switchKnowledgeRoot(selectedDir)
  } catch {
    // ignore
  } finally {
    await workspaceStore.loadKnowledgeTree()
    workspaceStore.restartFileWatcher()
    switchingRoot.value = false
  }
}

async function commitLibraryName() {
  const nextName = libraryNameDraft.value.trim()
  if (!nextName || nextName === activeLibraryName.value) {
    libraryNameDraft.value = activeLibraryName.value
    return
  }
  savingLibraryName.value = true
  try {
    await settingsStore.renameActiveKnowledgeLibrary(nextName)
  } catch {
    libraryNameDraft.value = activeLibraryName.value
  } finally {
    savingLibraryName.value = false
  }
}

async function handleCloseWindow() {
  if (!(await workspaceStore.confirmSaveDirtyBeforeExit())) {
    return
  }
  desktopApi?.close()
}
</script>

<template>
  <header class="topbar">
    <div class="brand">
      <button class="logo-btn" type="button" title="打开 Agent 页面" @click="emit('openAgentPage')">
        <img :src="logoSrc" class="logo-img" alt="MetaWeave" />
      </button>
      <div class="brand-copy">
        <input
          v-model="libraryNameDraft"
          class="library-name-input"
          :disabled="savingLibraryName"
          :title="settingsStore.profile.knowledgeDir"
          spellcheck="false"
          @blur="commitLibraryName"
          @keydown.enter.prevent="commitLibraryName"
          @keydown.escape.prevent="libraryNameDraft = activeLibraryName"
        />
        <button
          class="root-path-btn"
          type="button"
          :disabled="switchingRoot"
          :title="settingsStore.profile.knowledgeDir"
          @click="openRootPicker"
        >
          {{ settingsStore.profile.knowledgeDir }}
        </button>
      </div>
      <div v-if="workspaceStore.ingestionProgressVisible" class="ingestion-progress" aria-live="polite">
        <span class="ingestion-progress-track" aria-hidden="true">
          <span
            class="ingestion-progress-fill"
            :style="{ width: `${workspaceStore.ingestionProgress}%` }"
          />
        </span>
        <span class="ingestion-progress-percent">{{ workspaceStore.ingestionProgress }}%</span>
      </div>
      <div v-if="workspaceStore.graphProgressVisible" class="ingestion-progress graph-progress" aria-live="polite">
        <span class="ingestion-progress-track" aria-hidden="true">
          <span
            class="ingestion-progress-fill"
            :style="{ width: `${workspaceStore.graphProgress}%` }"
          />
        </span>
        <span class="ingestion-progress-percent">{{ workspaceStore.graphProgress }}%</span>
      </div>
    </div>

    <div class="search-center">
      <SearchPalette />
    </div>

    <div class="actions">
      <button class="icon-button" type="button" title="设置" @click="emit('openSettings')">
        <Settings :size="14" />
      </button>
      <button class="console-link" :class="{ active: agentActive }" type="button" title="切换 Agent 面板" @click="emit('toggleAgent')">
        <span>Agent</span>
      </button>
      <button
        class="todo-link"
        :class="{ active: todoActive }"
        type="button"
        title="切换待办列表"
        @click="emit('toggleTodo')"
      >
        <CheckSquare :size="14" />
      </button>
      <button
        class="ingest-button graph-btn"
        :class="{ refreshing: graphRebuilding }"
        type="button"
        :disabled="graphRebuilding"
        title="图谱抽取"
        @click="workspaceStore.startGraphRebuild"
      >
        <Network :size="14" />
      </button>
      <button
        class="ingest-button"
        :class="{ refreshing: workspaceStore.refreshing }"
        type="button"
        :disabled="workspaceStore.refreshing"
        title="重新灌库"
        @click="workspaceStore.markIndexing"
      >
        <DatabaseZap :size="14" />
      </button>
      <button
        class="theme-button icon-button"
        :class="{ dark: settingsStore.isDark, light: !settingsStore.isDark }"
        type="button"
        title="切换主题"
        @click="settingsStore.toggleTheme"
      >
        <Moon v-if="settingsStore.isDark" :size="14" />
        <Sun v-else :size="18" />
      </button>
      <div v-if="desktopApi?.isDesktop" class="window-controls" aria-label="Window controls">
        <button type="button" title="最小化" @click="desktopApi.minimize">
          <Minus :size="13" />
        </button>
        <button type="button" title="最大化" @click="desktopApi.toggleMaximize">
          <Maximize2 :size="13" />
        </button>
        <button class="close-window" type="button" title="关闭" @click="handleCloseWindow">
          <X :size="13" />
        </button>
      </div>
    </div>
  </header>
  <Transition name="toast-slide">
    <div v-if="workspaceStore.toastVisible" class="toast-banner">
      {{ workspaceStore.toastMessage }}
    </div>
  </Transition>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  min-height: 46px;
  padding: 4px var(--space-8);
  background: var(--color-chrome-topbar-bg);
  -webkit-app-region: drag;
  user-select: none;
  position: relative;
  z-index: 50;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-width: 0;
  overflow: hidden;
  flex-shrink: 0;
  z-index: 1;
  padding-left: var(--space-4);
}

.brand-copy {
  display: grid;
  gap: 0;
  min-width: 0;
  -webkit-app-region: no-drag;
}

.logo-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  -webkit-app-region: no-drag;
}

.logo-btn:hover {
  background: transparent;
}

.logo-img {
  display: block;
  width: 22px;
  height: 22px;
  object-fit: contain;
}

.library-name-input {
  display: block;
  width: min(180px, 100%);
  min-width: 0;
  height: 18px;
  padding: 0;
  border: 0;
  outline: 0;
  overflow: hidden;
  background: transparent;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.2;
}

.library-name-input:disabled {
  cursor: wait;
  opacity: 0.62;
}

.root-path-btn {
  display: block;
  overflow: hidden;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
  line-height: 1.1;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition: color var(--transition-fast);
}

.root-path-btn:hover:not(:disabled) {
  color: var(--color-primary);
}

.root-path-btn:disabled {
  cursor: wait;
  opacity: 0.62;
}

.ingest-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  -webkit-app-region: no-drag;
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    opacity var(--transition-fast);
}

.ingest-button:hover:not(:disabled) {
  background: color-mix(in srgb, var(--color-primary) 12%, transparent);
  color: var(--color-primary);
}

.ingest-button:disabled {
  cursor: wait;
  opacity: 0.72;
}

.ingest-button.refreshing :deep(svg) {
  animation: refresh-spin 900ms linear infinite;
}

.search-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 320px;
  -webkit-app-region: no-drag;
}

.brand strong {
  display: block;
  overflow: hidden;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
  font-weight: 650;
  letter-spacing: 0;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-shrink: 0;
  -webkit-app-region: no-drag;
  z-index: 1;
}

.topbar .icon-button {
  width: 24px;
  height: 24px;
  border-radius: 999px;
}

.topbar .theme-button.light {
  border-color: var(--color-accent);
  background: #ffffff;
  color: var(--color-accent);
}

.topbar .theme-button.light:hover {
  border-color: var(--color-accent);
  background: #fff5f8;
  color: var(--color-accent);
}

.topbar .theme-button.dark {
  border-color: #f5d77a;
  background: #050506;
  color: #f5d77a;
}

.topbar .theme-button.dark:hover {
  border-color: #ffe391;
  background: #0b0b0d;
  color: #ffe391;
}

.topbar .theme-button.dark :deep(svg) {
  fill: currentColor;
  stroke: currentColor;
}

.console-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  height: 24px;
  padding: 0 var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.console-link:hover {
  border-color: var(--color-primary);
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.console-link.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: white;
}

.console-link.active:hover {
  border-color: var(--color-primary-hover);
  background: var(--color-primary-hover);
  color: white;
}

.todo-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-secondary);
  -webkit-app-region: no-drag;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.todo-link:hover {
  border-color: var(--color-primary);
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.todo-link.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: white;
}

.ingestion-progress {
  display: inline-flex;
  align-items: center;
  gap: var(--space-4);
  width: min(140px, 30vw);
  height: 16px;
  padding: 0 var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-canvas) 92%, var(--color-primary) 8%);
  color: var(--color-primary);
  font-family: var(--font-ui);
  font-size: calc(9px * var(--font-scale));
  font-weight: 700;
  line-height: 1;
  -webkit-app-region: no-drag;
}

.ingestion-progress-track {
  display: block;
  flex: 1 1 auto;
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-primary) 14%, transparent);
}

.ingestion-progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-primary);
  transition: width 140ms ease;
}

.ingestion-progress-percent {
  flex: 0 0 auto;
  white-space: nowrap;
}

.graph-progress {
  border-color: color-mix(in srgb, var(--color-primary) 50%, #14b8a6 50%);
  background: color-mix(in srgb, var(--color-canvas) 92%, #14b8a6 8%);
  color: #14b8a6;
}

.graph-progress .ingestion-progress-track {
  background: color-mix(in srgb, #14b8a6 14%, transparent);
}

.graph-progress .ingestion-progress-fill {
  background: #14b8a6;
}

@keyframes refresh-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.toast-banner {
  position: fixed;
  top: 72px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 999;
  padding: var(--space-8) var(--space-20);
  border: 0;
  border-radius: var(--radius-lg);
  background: #fff;
  color: #333;
  font-size: calc(13px * var(--font-scale));
  font-weight: 600;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  pointer-events: none;
}

.toast-slide-enter-active {
  transition: all 280ms cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-slide-leave-active {
  transition: all 220ms ease-in;
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-12px);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-8px);
}

kbd {
  padding: 0 4px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
}

.window-controls {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.window-controls button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 24px;
  border: 0;
  border-left: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text-secondary);
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.window-controls button:first-child {
  border-left: 0;
}

.window-controls button:hover {
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.window-controls .close-window:hover {
  background: var(--color-accent);
  color: white;
}

@media (max-width: 760px) {
  .topbar {
    align-items: flex-start;
    flex-direction: column;
    padding: var(--space-10);
  }

  .actions {
    width: 100%;
    overflow-x: auto;
    padding-bottom: var(--space-2);
  }
}
</style>
