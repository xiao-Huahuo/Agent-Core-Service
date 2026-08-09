<!--
  Editor activity bar.

  Usage:
  Renders the icon-only left rail for opening editor side panels and navigating
  to future workspace tools. Buttons expose native tooltips through title text.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import lightLogo from '@/assets/images/亮色无底图标.png'
import darkLogo from '@/assets/images/暗色无底图标.png'
import { useSettingsStore } from '@/stores/settings'
import type { SidebarDisplayMode } from '@/types/settings'

const props = defineProps<{
  displayMode: SidebarDisplayMode
  homeActive: boolean
  fileOpen: boolean
  gitActive: boolean
  agentOpen: boolean
  resourcesActive: boolean
  favoritesActive: boolean
  libraryActive: boolean
  formsActive: boolean
  ingestionActive: boolean
  visualizationActive: boolean
  agentActive: boolean
  graphActive: boolean
  dashboardActive: boolean
  debugActive: boolean
  feedbackOpen: boolean
  searchActive: boolean
  skillsActive: boolean
  settingsActive: boolean
}>()

const emit = defineEmits<{
  openHome: []
  toggleFile: []
  toggleGit: []
  openResources: []
  openFavorites: []
  openLibrary: []
  openForms: []
  openIngestion: []
  openVisualization: []
  toggleAgent: []
  toggleGraph: []
  openDashboard: []
  toggleFeedback: []
  openDebug: []
  openSearch: []
  openSkills: []
  openSettings: []
}>()

function handleRipple(e: MouseEvent) {
  const el = e.currentTarget as HTMLElement
  el.querySelectorAll('.ripple-effect').forEach((item) => item.remove())
  const ripple = document.createElement('span')
  ripple.className = 'ripple-effect'
  el.appendChild(ripple)
  ripple.addEventListener('animationend', () => ripple.remove(), { once: true })
  window.setTimeout(() => ripple.remove(), 450)
}

const settingsStore = useSettingsStore()
const agentIconSrc = computed(() => settingsStore.isDark ? darkLogo : lightLogo)
const knowledgeMenuOpen = ref(false)
const knowledgeActive = computed(() => props.resourcesActive || props.libraryActive || props.formsActive)

function toggleKnowledgeMenu() {
  knowledgeMenuOpen.value = !knowledgeMenuOpen.value
}

function openKnowledgeMenuOnHover() {
  if (props.displayMode === 'icon') knowledgeMenuOpen.value = true
}

function closeKnowledgeMenuOnLeave() {
  if (props.displayMode === 'icon') knowledgeMenuOpen.value = false
}

function closeKnowledgeMenu() {
  knowledgeMenuOpen.value = false
}
</script>

<template>
  <nav class="activity-bar" :class="{ management: displayMode === 'management' }" aria-label="Editor activity bar">
    <button
      class="activity-button"
      :class="{ active: homeActive }"
      type="button"
      title="主页"
      aria-label="主页"
      @mousedown.prevent="handleRipple"
      @click="emit('openHome')"
    >
      <IcIcon name="home" :size="18" />
      <span class="activity-label">主页</span>
    </button>
    <button
      class="activity-button"
      :class="{ active: fileOpen }"
      type="button"
      title="Files"
      aria-label="Files"
      @mousedown.prevent="handleRipple"
      @click="emit('toggleFile')"
    >
      <IcIcon name="folder" :size="18" />
      <span class="activity-label">文件</span>
    </button>
    <button
      class="activity-button"
      :class="{ active: gitActive }"
      type="button"
      title="Git"
      aria-label="Git"
      @mousedown.prevent="handleRipple"
      @click="emit('toggleGit')"
    >
      <IcIcon name="git" :size="18" />
      <span class="activity-label">Git</span>
    </button>
    <div
      class="knowledge-group"
      @mouseenter="openKnowledgeMenuOnHover"
      @mouseleave="closeKnowledgeMenuOnLeave"
    >
      <button
        class="activity-button knowledge-button"
        :class="{ active: knowledgeActive }"
        type="button"
        title="知识库"
        aria-label="知识库"
        :aria-expanded="knowledgeMenuOpen"
        @mousedown="handleRipple"
        @click.stop="toggleKnowledgeMenu"
      >
        <IcIcon name="graph" :size="18" />
        <span class="activity-label">知识库</span>
        <IcIcon class="knowledge-chevron" :class="{ 'is-open': knowledgeMenuOpen }" name="chevron-right" :size="14" />
      </button>
      <Transition name="knowledge-submenu">
        <div v-if="knowledgeMenuOpen" class="knowledge-submenu" aria-label="知识库菜单">
          <button
            class="activity-button"
            :class="{ active: resourcesActive }"
            type="button"
            title="文件资源管理器"
            aria-label="文件资源管理器"
            @mousedown.prevent="handleRipple"
            @click="emit('openResources'); closeKnowledgeMenu()"
          >
            <IcIcon name="folder-open" :size="18" />
            <span class="activity-label">文件资源管理器</span>
          </button>
          <button
            class="activity-button"
            :class="{ active: libraryActive }"
            type="button"
            title="图书馆"
            aria-label="图书馆"
            @mousedown.prevent="handleRipple"
            @click="emit('openLibrary'); closeKnowledgeMenu()"
          >
            <IcIcon name="book" :size="18" />
            <span class="activity-label">图书馆</span>
          </button>
          <button
            class="activity-button"
            :class="{ active: formsActive }"
            type="button"
            title="智能表格"
            aria-label="智能表格"
            @mousedown.prevent="handleRipple"
            @click="emit('openForms'); closeKnowledgeMenu()"
          >
            <IcIcon name="table-chart" :size="18" />
            <span class="activity-label">智能表格</span>
          </button>
        </div>
      </Transition>
    </div>
    <button
      class="activity-button"
      :class="{ active: favoritesActive }"
      type="button"
      title="我的收藏"
      aria-label="我的收藏"
      @mousedown.prevent="handleRipple"
      @click="emit('openFavorites')"
    >
      <IcIcon name="star" :size="18" />
      <span class="activity-label">收藏</span>
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
      <IcIcon name="search" :size="18" />
      <span class="activity-label">搜索</span>
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
      <img :src="agentIconSrc" class="activity-agent-icon" alt="" />
      <span class="activity-label">Agent</span>
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
      <IcIcon name="hub" :size="18" />
      <span class="activity-label">图谱</span>
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
      <IcIcon name="dashboard" :size="18" />
      <span class="activity-label">看板</span>
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
      <IcIcon name="ingest" :size="18" />
      <span class="activity-label">入库</span>
    </button>
    <button
      class="activity-button"
      :class="{ active: visualizationActive }"
      type="button"
      title="MD-HTML"
      aria-label="MD-HTML"
      @mousedown.prevent="handleRipple"
      @click="emit('openVisualization')"
    >
      <IcIcon name="code" :size="18" />
      <span class="activity-label">MD-HTML</span>
    </button>
    <button
      class="activity-button"
      :class="{ active: skillsActive }"
      type="button"
      title="Skills"
      aria-label="Skills"
      @mousedown.prevent="handleRipple"
      @click="emit('openSkills')"
    >
      <IcIcon name="auto-awesome" :size="18" />
      <span class="activity-label">Skills</span>
    </button>
    <div class="bottom-group">
      <button
        class="activity-button"
        :class="{ active: feedbackOpen }"
        type="button"
        title="用户反馈"
        aria-label="用户反馈"
        @mousedown.prevent="handleRipple"
        @click="emit('toggleFeedback')"
      >
        <IcIcon name="feedback" :size="18" />
        <span class="activity-label">反馈</span>
      </button>
      <button
        class="activity-button"
        :class="{ active: debugActive }"
        type="button"
        title="Debug"
        aria-label="Debug"
        @mousedown.prevent="handleRipple"
      @click="emit('openDebug')"
      >
        <IcIcon name="bug" :size="18" />
        <span class="activity-label">Debug</span>
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
        <IcIcon name="settings" :size="18" />
        <span class="activity-label">设置</span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.activity-bar {
  position: relative;
  z-index: 100;
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: var(--space-4);
  width: 100%;
  height: 100%;
  padding: var(--space-8) var(--space-4);
  background: var(--color-chrome-rail-bg);
  overflow: visible;
  transition: padding 180ms ease;
}

.activity-bar.management {
  align-items: stretch;
  padding: var(--space-8) var(--space-6);
}

.activity-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  width: 32px;
  height: 32px;
  border: 1px solid transparent;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  position: relative;
  overflow: hidden;
  transition:
    width 180ms ease,
    gap 180ms ease,
    padding 180ms ease,
    background 0.25s,
    border-color 0.25s,
    color 0.25s;
}

.activity-bar.management .activity-button {
  justify-content: flex-start;
  width: 100%;
  padding: 0 var(--space-8);
  gap: var(--space-8);
  border-radius: var(--radius-sm);
}

.knowledge-group {
  position: relative;
  z-index: 101;
}

.activity-bar.management .knowledge-group {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  gap: var(--space-4);
}

.knowledge-button .knowledge-chevron {
  position: absolute;
  top: 50%;
  right: var(--space-8);
  display: none;
  width: 14px;
  height: 14px;
  margin-left: auto;
  transform: translateY(-50%);
  transition: transform 180ms ease;
}

.activity-bar.management .knowledge-button .knowledge-chevron {
  display: block;
}

.knowledge-button .knowledge-chevron.is-open {
  transform: translateY(-50%) rotate(90deg);
}

.knowledge-submenu {
  position: absolute;
  top: 0;
  left: calc(100% + var(--space-8));
  z-index: 1000;
  display: grid;
  gap: var(--space-4);
  min-width: 48px;
  width: 48px;
  padding: var(--space-4);
  border: 1px solid var(--color-border-subtle);
  border-radius: 999px;
  background: var(--color-surface);
  box-shadow: var(--shadow-window);
}

.activity-bar.management .knowledge-submenu {
  position: relative;
  top: auto;
  left: auto;
  min-width: 0;
  width: auto;
  padding: 0 0 0 var(--space-12);
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.knowledge-submenu .activity-button {
  width: 32px;
}

.activity-bar:not(.management) .knowledge-submenu .activity-button {
  margin-inline: auto;
}

.activity-bar.management .knowledge-submenu .activity-button {
  width: 100%;
}

.activity-bar.management .knowledge-submenu .activity-label {
  max-width: 136px;
  opacity: 1;
  transform: translateX(0);
}

.knowledge-submenu-enter-active,
.knowledge-submenu-leave-active {
  transition: opacity 180ms ease, transform 180ms ease, max-height 180ms ease;
  transform-origin: top left;
}

.knowledge-submenu-enter-from,
.knowledge-submenu-leave-to {
  max-height: 0;
  opacity: 0;
  transform: translateX(-6px) scale(0.98);
}

.knowledge-submenu-enter-to,
.knowledge-submenu-leave-from {
  max-height: 180px;
  opacity: 1;
  transform: translateX(0) scale(1);
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
  z-index: 0;
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

.activity-agent-icon {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  object-fit: contain;
  position: relative;
  z-index: 1;
}

.activity-button :deep(svg) {
  flex: 0 0 auto;
  position: relative;
  z-index: 1;
}

.activity-label {
  display: inline-block;
  position: relative;
  z-index: 1;
  max-width: 0;
  overflow: hidden;
  opacity: 0;
  color: currentColor;
  font-size: calc(12px * var(--font-scale));
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
  transform: translateX(-6px);
  transition:
    max-width 180ms ease,
    opacity 140ms ease,
    transform 180ms ease;
}

.activity-bar.management .activity-label {
  max-width: 72px;
  opacity: 1;
  transform: translateX(0);
  transition-delay: 40ms;
}

.activity-button.active .activity-agent-icon {
  filter: brightness(0) invert(1);
}

.bottom-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-4);
  margin-top: auto;
}

.activity-bar.management .bottom-group {
  align-items: stretch;
  width: 100%;
}
</style>
