<!--
  观测面板主视图 — 两个可切换子页面。
  页面切换通过本地 tab 实现,不依赖路由。
  进入面板时会自动同步当前选中会话的历史消息，确保 Obs 卡片有数据源可读。
-->

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useSessionStore } from '@/stores/session'
import { useChatStore } from '@/stores/chat'
import AgentTracePanel from '@/components/dashboard/AgentTracePanel.vue'
import MemoryKnowledgePanel from '@/components/dashboard/MemoryKnowledgePanel.vue'
import ToolRegistryPanel from '@/components/dashboard/ToolRegistryPanel.vue'

const activeTab = ref<'trace' | 'mk' | 'tools'>('trace')
const settingsStore = useSettingsStore()
const sessionStore = useSessionStore()
const chatStore = useChatStore()

const userId = settingsStore.profile.userId

/**
 * 确保观测面板使用的是当前选中会话的消息历史。
 * 如果 chatStore 还没有加载该 session，则主动补拉一次。
 */
async function ensureObsHistoryLoaded() {
  if (!userId) return
  if (sessionStore.sessions.length === 0) {
    await sessionStore.load(userId)
  }

  let sessionId = sessionStore.currentSessionId
  if (!sessionId && sessionStore.sessions.length > 0) {
    sessionId = sessionStore.sessions[0]!.session_id
    sessionStore.select(sessionId)
  }

  if (!userId || !sessionId) return
  if (chatStore.loadedSessionId === sessionId && chatStore.messages.length > 0) return
  await chatStore.loadHistory(sessionId, userId, 200)
}

watch(
  () => [userId, sessionStore.currentSessionId, sessionStore.sessions.length],
  () => {
    ensureObsHistoryLoaded()
  },
  { immediate: true },
)

onMounted(() => {
  ensureObsHistoryLoaded()
})
</script>

<template>
  <div class="dashboard-view">
    <!-- 子页面切换 Tab -->
    <div class="obs-tabs">
      <button
        class="obs-tab"
        :class="{ active: activeTab === 'trace' }"
        @click="activeTab = 'trace'"
      >
        Agent 轨迹
      </button>
      <button
        class="obs-tab"
        :class="{ active: activeTab === 'mk' }"
        @click="activeTab = 'mk'"
      >
        记忆与知识
      </button>
      <button
        class="obs-tab"
        :class="{ active: activeTab === 'tools' }"
        @click="activeTab = 'tools'"
      >
        工具注册表
      </button>
    </div>

    <div class="dashboard-content">
      <AgentTracePanel v-if="activeTab === 'trace'" />
      <MemoryKnowledgePanel v-if="activeTab === 'mk'" />
      <ToolRegistryPanel v-if="activeTab === 'tools'" />
    </div>
  </div>
</template>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.dashboard-content {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ---- 子页面切换 Tab ---- */
.obs-tabs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  padding: var(--space-8) var(--space-10) 0;
  flex-shrink: 0;
}

.obs-tab {
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  padding: 4px 12px;
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.obs-tab:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
}

.obs-tab.active {
  color: var(--color-accent);
  border-color: rgba(217, 145, 120, 0.35);
  background: var(--color-accent-muted);
}

@media (max-width: 900px) {
  .obs-tabs {
    padding: var(--space-8);
  }
}

@media (max-width: 768px) {
  .dashboard-view {
    overflow: auto;
  }

  .dashboard-content {
    display: block;
    width: 100%;
    overflow: visible;
  }

  .dashboard-content > * {
    width: 100%;
    min-width: 0;
  }

  .obs-tabs {
    position: sticky;
    top: 0;
    z-index: 5;
    padding: var(--space-8);
    background: var(--color-bg-app);
    border-bottom: 1px solid var(--color-border);
  }

  .obs-tab {
    flex: 1 1 calc(50% - 2px);
    min-width: 0;
    text-align: center;
  }
}
</style>
