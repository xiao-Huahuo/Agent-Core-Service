<!--
  Debug workspace page.

  Usage:
  Hosts developer-facing runtime tools behind a single activity-bar entry.
-->
<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import AgentTracePanel from '@/components/dashboard/AgentTracePanel.vue'
import MemoryKnowledgePanel from '@/components/dashboard/MemoryKnowledgePanel.vue'
import ToolRegistryPanel from '@/components/dashboard/ToolRegistryPanel.vue'
import GlobalConstantsPanel from '@/components/debug/GlobalConstantsPanel.vue'
import MultimodalIngestionPanel from '@/components/debug/MultimodalIngestionPanel.vue'
import RuntimeApisPanel from '@/components/debug/RuntimeApisPanel.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'

const activeTab = ref<'trace' | 'multimodal' | 'mk' | 'tools' | 'constants' | 'apis'>('trace')
const debugTabsRef = ref<HTMLElement | null>(null)
const debugSliderStyle = ref({ width: '0px', left: '0px' })

function updateDebugSlider() {
  nextTick(() => {
    const container = debugTabsRef.value
    if (!container) return
    const active = container.querySelector('.debug-tab.active') as HTMLElement | null
    if (!active) return
    debugSliderStyle.value = {
      width: `${active.offsetWidth}px`,
      left: `${active.offsetLeft}px`,
    }
  })
}

watch(activeTab, updateDebugSlider)
const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()

const userId = settingsStore.profile.userId

async function ensureDebugHistoryLoaded() {
  if (!userId) return
  if (sessionStore.sessions.length === 0) {
    await sessionStore.load(userId)
  }

  let sessionId = sessionStore.currentSessionId
  if (!sessionId && sessionStore.sessions.length > 0) {
    sessionId = sessionStore.sessions[0]!.session_id
    sessionStore.select(sessionId)
  }

  if (!sessionId) return
  if (chatStore.loadedSessionId === sessionId && chatStore.messages.length > 0) return
  await chatStore.loadHistory(sessionId, userId, 200)
}

watch(
  [() => sessionStore.currentSessionId, () => sessionStore.sessions.length],
  () => {
    ensureDebugHistoryLoaded()
  },
  { immediate: true },
)

onMounted(() => {
  updateDebugSlider()
})
</script>

<template>
  <div class="debug-view">
    <div ref="debugTabsRef" class="debug-tabs">
      <div class="debug-slider" :style="debugSliderStyle"></div>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'trace' }"
        type="button"
        @click="activeTab = 'trace'"
      >
        <IcIcon name="bug" :size="17" />
        <span>Agent 轨迹</span>
      </button>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'multimodal' }"
        type="button"
        @click="activeTab = 'multimodal'"
      >
        <IcIcon name="image" :size="17" />
        <span>多模态入库</span>
      </button>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'mk' }"
        type="button"
        @click="activeTab = 'mk'"
      >
        <IcIcon name="psychology" :size="17" />
        <span>记忆与知识</span>
      </button>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'tools' }"
        type="button"
        @click="activeTab = 'tools'"
      >
        <IcIcon name="build" :size="17" />
        <span>工具注册表</span>
      </button>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'constants' }"
        type="button"
        @click="activeTab = 'constants'"
      >
        <IcIcon name="tune" :size="17" />
        <span>全局常量</span>
      </button>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'apis' }"
        type="button"
        @click="activeTab = 'apis'"
      >
        <IcIcon name="code" :size="17" />
        <span>API</span>
      </button>
    </div>

    <div class="debug-content">
      <AgentTracePanel v-if="activeTab === 'trace'" />
      <MultimodalIngestionPanel v-else-if="activeTab === 'multimodal'" />
      <MemoryKnowledgePanel v-else-if="activeTab === 'mk'" />
      <ToolRegistryPanel v-else-if="activeTab === 'tools'" />
      <GlobalConstantsPanel v-else-if="activeTab === 'constants'" />
      <RuntimeApisPanel v-else-if="activeTab === 'apis'" />
    </div>
  </div>
</template>

<style scoped>
.debug-view {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

.debug-tabs {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 2px;
  margin: var(--space-8) var(--space-12) 0;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  flex-shrink: 0;
  align-self: flex-start;
}

.debug-slider {
  position: absolute;
  top: 2px;
  height: calc(100% - 4px);
  border-radius: 999px;
  background: var(--color-primary-soft);
  transition: left 250ms ease, width 250ms ease;
  z-index: 0;
  pointer-events: none;
}

.debug-tab {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  height: 28px;
  font: inherit;
  font-size: calc(12px * var(--font-scale));
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: 999px;
  padding: 0 var(--space-8);
  cursor: pointer;
  outline: none;
}

.debug-tab:hover {
  color: var(--color-primary);
}

.debug-tab.active {
  color: var(--color-primary);
}

.debug-content {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 768px) {
  .debug-view {
    overflow: auto;
  }

  .debug-content {
    display: block;
    width: 100%;
    overflow: visible;
  }

  .debug-content > * {
    width: 100%;
    min-width: 0;
  }

  .debug-tabs {
    position: sticky;
    top: 0;
    z-index: 5;
    display: flex;
    margin: 0;
    padding: var(--space-8);
    background: var(--color-bg-app);
    border: none;
    border-radius: 0;
    border-bottom: 0;
    align-self: auto;
  }

  .debug-slider {
    display: none;
  }

  .debug-tab {
    flex: 1 1 calc(50% - 2px);
    min-width: 0;
    text-align: center;
  }

  .debug-tab.active {
    background: var(--color-primary-soft);
  }
}
</style>
