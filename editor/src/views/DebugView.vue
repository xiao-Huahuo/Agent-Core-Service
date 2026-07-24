<!--
  Debug workspace page.

  Usage:
  Hosts developer-facing runtime tools behind a single activity-bar entry.
-->
<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

import AgentTracePanel from '@/components/dashboard/AgentTracePanel.vue'
import MemoryKnowledgePanel from '@/components/dashboard/MemoryKnowledgePanel.vue'
import ToolRegistryPanel from '@/components/dashboard/ToolRegistryPanel.vue'
import MultimodalIngestionPanel from '@/components/debug/MultimodalIngestionPanel.vue'
import RuntimeApisPanel from '@/components/debug/RuntimeApisPanel.vue'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { useSettingsStore } from '@/stores/settings'

const activeTab = ref<'trace' | 'multimodal' | 'mk' | 'tools' | 'apis'>('trace')
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
  () => [userId, sessionStore.currentSessionId, sessionStore.sessions.length],
  () => {
    ensureDebugHistoryLoaded()
  },
  { immediate: true },
)

onMounted(() => {
  ensureDebugHistoryLoaded()
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
        Agent 轨迹
      </button>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'multimodal' }"
        type="button"
        @click="activeTab = 'multimodal'"
      >
        多模态入库
      </button>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'mk' }"
        type="button"
        @click="activeTab = 'mk'"
      >
        记忆与知识
      </button>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'tools' }"
        type="button"
        @click="activeTab = 'tools'"
      >
        工具注册表
      </button>
      <button
        class="debug-tab"
        :class="{ active: activeTab === 'apis' }"
        type="button"
        @click="activeTab = 'apis'"
      >
        API
      </button>
    </div>

    <div class="debug-content">
      <AgentTracePanel v-if="activeTab === 'trace'" />
      <MultimodalIngestionPanel v-else-if="activeTab === 'multimodal'" />
      <MemoryKnowledgePanel v-else-if="activeTab === 'mk'" />
      <ToolRegistryPanel v-else-if="activeTab === 'tools'" />
      <RuntimeApisPanel v-else />
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
  gap: 4px;
  padding: 3px;
  margin: var(--space-8) var(--space-10) 0;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  flex-shrink: 0;
  align-self: flex-start;
}

.debug-slider {
  position: absolute;
  top: 3px;
  height: calc(100% - 6px);
  border-radius: 999px;
  background: var(--color-primary-soft);
  transition: left 250ms ease, width 250ms ease;
  z-index: 0;
  pointer-events: none;
}

.debug-tab {
  position: relative;
  z-index: 1;
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: 999px;
  padding: 4px 12px;
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
    border-bottom: 1px solid var(--color-border);
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
