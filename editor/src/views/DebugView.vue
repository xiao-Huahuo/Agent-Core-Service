<!--
  Debug workspace page.

  Usage:
  Hosts developer-facing runtime tools behind a single activity-bar entry.
-->
<script setup lang="ts">
import { ref } from 'vue'

import ToolRegistryPanel from '@/components/dashboard/ToolRegistryPanel.vue'
import RuntimeApisPanel from '@/components/debug/RuntimeApisPanel.vue'

const activeTab = ref<'tools' | 'apis'>('tools')
</script>

<template>
  <div class="debug-view">
    <div class="debug-tabs">
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
      <ToolRegistryPanel v-if="activeTab === 'tools'" />
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
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  padding: var(--space-8) var(--space-10) 0;
  flex-shrink: 0;
}

.debug-tab {
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

.debug-tab:hover {
  color: var(--color-text-primary);
  background: var(--color-bg-hover);
}

.debug-tab.active {
  color: var(--color-primary);
  border-color: color-mix(in srgb, var(--color-primary) 35%, transparent);
  background: var(--color-primary-soft);
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
}
</style>
