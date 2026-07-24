<!--
  Top command bar.

  Usage:
  Shows the active knowledge root, global actions, theme switch, and navigation
  links between the editor, graph preview, settings, and existing console.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CheckSquare, DatabaseZap, Maximize2, Minus, Network, X } from 'lucide-vue-next'

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
      <button class="github-btn-topbar" :class="{ dark: settingsStore.isDark }" type="button" title="GitHub" onclick="window.open('https://github.com/xiao-Huahuo/MetaWeave.git','_blank')">
        <svg class="github-svg-icon" viewBox="0 0 496 512" height="1.2em" xmlns="http://www.w3.org/2000/svg"><path d="M165.9 397.4c0 2-2.3 3.6-5.2 3.6-3.3.3-5.6-1.3-5.6-3.6 0-2 2.3-3.6 5.2-3.6 3-.3 5.6 1.3 5.6 3.6zm-31.1-4.5c-.7 2 1.3 4.3 4.3 4.9 2.6 1 5.6 0 6.2-2s-1.3-4.3-4.3-5.2c-2.6-.7-5.5.3-6.2 2.3zm44.2-1.7c-2.9.7-4.9 2.6-4.6 4.9.3 2 2.9 3.3 5.9 2.6 2.9-.7 4.9-2.6 4.6-4.6-.3-1.9-3-3.2-5.9-2.9zM244.8 8C106.1 8 0 113.3 0 252c0 110.9 69.8 205.8 169.5 239.2 12.8 2.3 17.3-5.6 17.3-12.1 0-6.2-.3-40.4-.3-61.4 0 0-70 15-84.7-29.8 0 0-11.4-29.1-27.8-36.6 0 0-22.9-15.7 1.6-15.4 0 0 24.9 2 38.6 25.8 21.9 38.6 58.6 27.5 72.9 20.9 2.3-16 8.8-27.1 16-33.7-55.9-6.2-112.3-14.3-112.3-110.5 0-27.5 7.6-41.3 23.6-58.9-2.6-6.5-11.1-33.3 2.6-67.9 20.9-6.5 69 27 69 27 20-5.6 41.5-8.5 62.8-8.5s42.8 2.9 62.8 8.5c0 0 48.1-33.6 69-27 13.7 34.7 5.2 61.4 2.6 67.9 16 17.7 25.8 31.5 25.8 58.9 0 96.5-58.9 104.2-114.8 110.5 9.2 7.9 17 22.9 17 46.4 0 33.7-.3 75.4-.3 83.6 0 6.5 4.6 14.4 17.3 12.1C428.2 457.8 496 362.9 496 252 496 113.3 383.5 8 244.8 8zM97.2 352.9c-1.3 1-1 3.3.7 5.2 1.6 1.6 3.9 2.3 5.2 1 1.3-1 1-3.3-.7-5.2-1.6-1.6-3.9-2.3-5.2-1zm-10.8-8.1c-.7 1.3.3 2.9 2.3 3.9 1.6 1 3.6.7 4.3-.7.7-1.3-.3-2.9-2.3-3.9-2-.6-3.6-.3-4.3.7zm32.4 35.6c-1.6 1.3-1 4.3 1.3 6.2 2.3 2.3 5.2 2.6 6.5 1 1.3-1.3.7-4.3-1.3-6.2-2.2-2.3-5.2-2.6-6.5-1zm-11.4-14.7c-1.6 1-1.6 3.6 0 5.9 1.6 2.3 4.3 3.3 5.6 2.3 1.6-1.3 1.6-3.9 0-6.2-1.4-2.3-4-3.3-5.6-2z"></path></svg>
        <span class="github-text-topbar">GitHub</span>
      </button>
      <button class="agent-play-btn" :class="{ active: agentActive }" type="button" title="切换 Agent 面板" @click="emit('toggleAgent')">
        <img :src="logoSrc" class="agent-play-img" alt="MetaWeave" />
        <span class="agent-now">NOW!</span>
        <span class="agent-play">AGENT</span>
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
        class="todo-link"
        :class="{ refreshing: graphRebuilding }"
        type="button"
        :disabled="graphRebuilding"
        title="图谱抽取"
        @click="workspaceStore.startGraphRebuild"
      >
        <Network :size="14" />
      </button>
      <button
        class="todo-link"
        :class="{ refreshing: workspaceStore.refreshing }"
        type="button"
        :disabled="workspaceStore.refreshing"
        title="重新灌库"
        @click="workspaceStore.markIndexing"
      >
        <DatabaseZap :size="14" />
      </button>
      <label class="switch" title="切换主题">
        <input
          type="checkbox"
          :checked="settingsStore.isDark"
          @change="settingsStore.toggleTheme"
        />
        <span class="slider">
          <div class="moons-hole">
            <div class="moon-hole"></div>
            <div class="moon-hole"></div>
            <div class="moon-hole"></div>
          </div>
          <div class="clouds">
            <div class="cloud"></div>
            <div class="cloud"></div>
            <div class="cloud"></div>
            <div class="cloud"></div>
            <div class="cloud"></div>
            <div class="cloud"></div>
            <div class="cloud"></div>
          </div>
          <div class="stars">
            <svg class="star" viewBox="0 0 20 20">
              <path d="M 0 10 C 10 10,10 10 ,0 10 C 10 10 , 10 10 , 10 20 C 10 10 , 10 10 , 20 10 C 10 10 , 10 10 , 10 0 C 10 10,10 10 ,0 10 Z" />
            </svg>
            <svg class="star" viewBox="0 0 20 20">
              <path d="M 0 10 C 10 10,10 10 ,0 10 C 10 10 , 10 10 , 10 20 C 10 10 , 10 10 , 20 10 C 10 10 , 10 10 , 10 0 C 10 10,10 10 ,0 10 Z" />
            </svg>
            <svg class="star" viewBox="0 0 20 20">
              <path d="M 0 10 C 10 10,10 10 ,0 10 C 10 10 , 10 10 , 10 20 C 10 10 , 10 10 , 20 10 C 10 10 , 10 10 , 10 0 C 10 10,10 10 ,0 10 Z" />
            </svg>
            <svg class="star" viewBox="0 0 20 20">
              <path d="M 0 10 C 10 10,10 10 ,0 10 C 10 10 , 10 10 , 10 20 C 10 10 , 10 10 , 20 10 C 10 10 , 10 10 , 10 0 C 10 10,10 10 ,0 10 Z" />
            </svg>
            <svg class="star" viewBox="0 0 20 20">
              <path d="M 0 10 C 10 10,10 10 ,0 10 C 10 10 , 10 10 , 10 20 C 10 10 , 10 10 , 20 10 C 10 10 , 10 10 , 10 0 C 10 10,10 10 ,0 10 Z" />
            </svg>
          </div>
        </span>
      </label>
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
  min-height: 56px;
  padding: 6px var(--space-10);
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

/* ── Theme switch (sun/moon animation) ── */
.switch {
  position: relative;
  display: inline-block;
  width: 58px;
  height: 28px;
  border: 1px solid var(--color-border);
  border-radius: 22px;
  flex-shrink: 0;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--color-primary);
  border-radius: 20px;
  transition: 0.4s;
  overflow: hidden;
  z-index: 2;
}

.slider:before {
  position: absolute;
  content: "";
  height: 20px;
  width: 20px;
  left: 35px;
  bottom: 3px;
  background-color: orange;
  transition: 1s;
  border-radius: 50%;
  overflow: hidden;
  z-index: 3;
}

/* ── Dark: slider moves to left, bg turns black ── */
input:checked + .slider {
  background-color: black;
}

input:checked + .slider:before {
  left: 3px;
  background-color: white;
}

.moons-hole {
  content: "";
  position: absolute;
  opacity: 0;
  transition: 1s;
  z-index: 4;
}

.moon-hole {
  position: absolute;
  border-radius: 50%;
  transform: translateX(0px);
}

.moon-hole:nth-child(1) {
  background-color: rgb(85, 85, 85);
  height: 5px;
  width: 5px;
  top: 18px;
  left: 14px;
}

.moon-hole:nth-child(2) {
  background-color: rgb(85, 85, 85);
  height: 10px;
  width: 10px;
  top: 10px;
  left: 5px;
}

.moon-hole:nth-child(3) {
  background-color: rgb(85, 85, 85);
  height: 4px;
  width: 4px;
  top: 7px;
  left: 15px;
}

input:checked + .slider .moons-hole {
  opacity: 1;
}

.stars {
  right: 4px;
  top: 0;
  bottom: 0;
  transition: 1s;
  transform: translateY(-22px);
  opacity: 0;
  position: absolute;
  z-index: 4;
}

.star {
  position: absolute;
  fill: white;
  animation: star-twinkle 2s infinite;
  opacity: 1;
}

.star:nth-child(1) {
  top: 3px;
  right: 10px;
  width: 15px;
  animation-delay: 0.3s;
}

.star:nth-child(2) {
  top: 12px;
  right: 4px;
  width: 12px;
}

.star:nth-child(3) {
  top: 3px;
  right: 8px;
  width: 8px;
  animation-delay: 0.6s;
}

.star:nth-child(4) {
  top: 18px;
  right: 14px;
  width: 10px;
  animation-delay: 0.9s;
}

.star:nth-child(5) {
  top: 1px;
  right: 30px;
  width: 6px;
  animation-delay: 1.2s;
}

input:checked + .slider .stars {
  transform: translateY(0px);
  opacity: 1;
}

@keyframes star-twinkle {
  0% { transform: scale(1); }
  40% { transform: scale(1.2); }
  80% { transform: scale(0.8); }
  100% { transform: scale(1); }
}

.clouds {
  position: absolute;
  left: 4px;
  top: 0;
  bottom: 0;
  width: 14px;
  transition: 1s;
  transform: translateX(0px);
  opacity: 1;
  z-index: 1;
}

.cloud {
  position: absolute;
  width: 14px;
  height: 14px;
  background-color: white;
  border-radius: 50%;
  z-index: 1;
  animation: cloud-move 6s infinite;
}

.cloud:nth-child(1) {
  top: 0;
  height: 15px;
  width: 15px;
  right: 10px;
}

.cloud:nth-child(2) {
  height: 18px;
  width: 18px;
  border-radius: 50%;
  top: 10px;
  right: 4px;
}

.cloud:nth-child(3) {
  height: 16px;
  width: 16px;
  top: 19px;
  left: 3px;
}

.cloud:nth-child(4) {
  top: 18px;
  left: 15px;
}

.cloud:nth-child(5) {
  top: 20px;
  left: 20px;
}

.cloud:nth-child(6) {
  top: 19px;
  left: 30px;
}

.cloud:nth-child(7) {
  top: 21px;
  left: 38px;
}

input:checked + .slider .clouds {
  transform: translateX(-40px);
  opacity: 0;
}

.black-clouds {
  display: none;
}

.black-cloud {
  display: none;
}

@keyframes cloud-move {
  0% { transform: translateX(-22px); }
  40% { transform: translateX(-26px); }
  80% { transform: translateX(-18px); }
  100% { transform: translateX(-22px); }
}

.github-btn-topbar {
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition-duration: .4s;
  cursor: pointer;
  position: relative;
  background-color: rgb(31, 31, 31);
  overflow: hidden;
  flex-shrink: 0;
}

.github-btn-topbar.dark {
  background-color: #fff;
}

.github-btn-topbar.dark .github-svg-icon path {
  fill: #000;
}

.github-btn-topbar.dark .github-text-topbar {
  color: #000;
}

.github-svg-icon {
  transition-duration: .3s;
}

.github-svg-icon path {
  fill: white;
}

.github-text-topbar {
  position: absolute;
  color: rgb(255, 255, 255);
  width: 120px;
  font-weight: 600;
  opacity: 0;
  transition-duration: .4s;
  font-family: var(--font-ui);
  font-size: calc(11px * var(--font-scale));
}

.github-btn-topbar:hover {
  width: 90px;
  transition-duration: .4s;
  border-radius: 30px;
}

.github-btn-topbar:hover .github-text-topbar {
  opacity: 1;
  transition-duration: .4s;
}

.github-btn-topbar:hover .github-svg-icon {
  opacity: 0;
  transition-duration: .3s;
}

.agent-play-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  border: 0;
  border-radius: 999px;
  background-color: var(--color-primary);
  color: #fff;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: all 0.5s ease;
}

.agent-play-btn:active {
  transform: scale(0.9);
  transition: all 100ms ease;
}

.agent-play-img {
  width: 14px;
  height: 14px;
  object-fit: contain;
  transition: all 0.5s ease;
  z-index: 2;
  filter: brightness(0) invert(1);
}

.agent-play {
  transition: all 0.5s ease;
  transition-delay: 300ms;
}

.agent-play-btn:hover .agent-play-img {
  transform: scale(2.5) translateX(14px);
  transform-origin: left center;
}

.agent-now {
  position: absolute;
  left: 0;
  transform: translateX(-100%);
  transition: all 0.5s ease;
  z-index: 2;
}

.agent-play-btn:hover .agent-now {
  transform: translateX(6px);
  transition-delay: 300ms;
}

.agent-play-btn:hover .agent-play {
  transform: translateX(200%);
  transition-delay: 300ms;
}

.agent-play-btn.active {
  background-color: color-mix(in srgb, var(--color-primary) 80%, #000);
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

.todo-link :deep(svg) {
  transition: transform 0.3s;
}

.todo-link:hover {
  border-color: var(--color-primary);
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.todo-link:hover :deep(svg) {
  transform: rotate(90deg);
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

.todo-link.refreshing :deep(svg) {
  animation: refresh-spin 900ms linear infinite;
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
