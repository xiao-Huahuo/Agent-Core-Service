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
    <AgentTracePanel v-if="activeTab === 'trace'" />
    <MemoryKnowledgePanel v-if="activeTab === 'mk'" />
  </div>
</template>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

/* ---- 子页面切换 Tab ---- */
.obs-tabs {
  display: flex;
  align-items: center;
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
</style>
