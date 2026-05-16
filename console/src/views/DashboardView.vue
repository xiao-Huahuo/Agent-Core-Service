<!--
  观测面板主视图 — 两个可切换子页面。
  页面切换通过本地 tab 实现,不依赖路由。
-->

<script setup>
import { ref } from 'vue'
import AgentTracePanel from '@/components/dashboard/AgentTracePanel.vue'
import MemoryKnowledgePanel from '@/components/dashboard/MemoryKnowledgePanel.vue'

const activeTab = ref('trace')
</script>

<template>
  <div class="dashboard-view">
    <!-- ================================================================
         子页面切换 Tab
         ================================================================ -->
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
    </div>

    <!-- ================================================================
         面板内容
         ================================================================ -->
    <div class="dashboard-content">
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
