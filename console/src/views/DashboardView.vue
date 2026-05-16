<!--
  观测面板主视图 — 两个可切换子页面。
  页面切换通过本地 tab 实现,不依赖路由。
  进入面板时会自动同步当前选中会话的历史消息，确保 Obs 卡片有数据源可读。
-->

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useUserId } from '@/composable/useUserId'
import { useSessionStore } from '@/stores/session'
import { useChatStore } from '@/stores/chat'
import AgentTracePanel from '@/components/dashboard/AgentTracePanel.vue'
import MemoryKnowledgePanel from '@/components/dashboard/MemoryKnowledgePanel.vue'

const activeTab = ref('trace')
const { userId, hasUserId, setUserId } = useUserId()
const sessionStore = useSessionStore()
const chatStore = useChatStore()
const userIdInput = ref(userId.value)

async function submitUserId() {
  const id = userIdInput.value.trim()
  if (!id) return
  setUserId(id)
  await ensureObsHistoryLoaded()
}

/**
 * 确保观测面板使用的是当前选中会话的消息历史。
 * 如果 chatStore 还没有加载该 session，则主动补拉一次。
 */
async function ensureObsHistoryLoaded() {
  if (!userId.value) return
  if (sessionStore.sessions.length === 0) {
    await sessionStore.load(userId.value)
  }

  let sessionId = sessionStore.currentSessionId
  if (!sessionId && sessionStore.sessions.length > 0) {
    sessionId = sessionStore.sessions[0].session_id
    sessionStore.select(sessionId)
  }

  if (!userId.value || !sessionId) return
  if (chatStore.loadedSessionId === sessionId && chatStore.messages.length > 0) return
  await chatStore.loadHistory(sessionId, userId.value, 200)
}

watch(
  () => [userId.value, sessionStore.currentSessionId, sessionStore.sessions.length],
  () => {
    ensureObsHistoryLoaded()
  },
  { immediate: true }
)

onMounted(() => {
  ensureObsHistoryLoaded()
})
</script>

<template>
  <div class="dashboard-view">
    <!-- ================================================================
         子页面切换 Tab
         ================================================================ -->
    <div v-if="hasUserId" class="obs-tabs">
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
    </div>

    <!-- ================================================================
         面板内容
         ================================================================ -->
    <div v-if="!hasUserId" class="user-id-prompt">
      <div class="macos-card prompt-card">
        <div class="macos-card-titlebar">
          <div class="traffic-lights">
            <span class="traffic-dot sm red"></span>
            <span class="traffic-dot sm yellow"></span>
            <span class="traffic-dot sm green"></span>
          </div>
          <span class="window-filename">obs --user</span>
          <span class="window-status"></span>
        </div>
        <div class="macos-card-body prompt-body">
          <span class="prompt-dollar">$</span>
          <input
            v-model="userIdInput"
            class="prompt-input"
            placeholder="user_id"
            @keydown.enter="submitUserId"
          />
          <button class="prompt-btn" :disabled="!userIdInput.trim()" @click="submitUserId">
            Enter
          </button>
        </div>
      </div>
    </div>

    <div v-else class="dashboard-content">
      <AgentTracePanel v-if="activeTab === 'trace'" />
      <MemoryKnowledgePanel v-if="activeTab === 'mk'" />
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

.user-id-prompt {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: var(--space-32);
}

.prompt-card {
  width: 100%;
  max-width: 380px;
}

.prompt-body {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-20) var(--space-16);
}

.prompt-dollar {
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--color-green);
  flex-shrink: 0;
}

.prompt-input {
  flex: 1;
  padding: var(--space-6) var(--space-8);
  border: none;
  background: transparent;
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  outline: none;
}

.prompt-input::placeholder {
  color: var(--color-text-tertiary);
}

.prompt-btn {
  padding: var(--space-6) var(--space-16);
  border: 1px solid var(--color-accent);
  background: var(--color-accent-muted);
  color: var(--color-accent);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), opacity var(--transition-fast);
  flex-shrink: 0;
}

.prompt-btn:hover:not(:disabled) {
  background: var(--color-accent);
  color: #0a0a0a;
}

.prompt-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
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
  font-family: var(--font-mono);
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
