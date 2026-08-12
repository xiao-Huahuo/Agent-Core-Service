<!--
  Full workspace Agent page.

  Usage:
  Rendered by EditorWorkspace when mainView === 'agent'. It reuses AgentPanel
  in page mode while keeping the global header and left activity bar outside
  this page.
-->
<script setup lang="ts">
import AgentPanel from '@/components/editor_workspace/AgentPanel.vue'
</script>

<template>
  <section class="agent-page">
    <div class="agent-page-shell">
      <AgentPanel mode="page" class="agent-page-panel" />
    </div>
  </section>
</template>

<style scoped>
.agent-page {
  position: relative;
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: visible;
  background: transparent;
}

.agent-page-shell {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 1 1 auto;
  width: 100%;
  min-width: 0;
  min-height: 0;
  padding: 0;
}

.agent-page-panel {
  flex: 1 1 auto;
  width: 100%;
  min-height: 0;
}
</style>
