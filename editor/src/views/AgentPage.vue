<!--
  Full workspace Agent page.

  Usage:
  Rendered by EditorWorkspace when mainView === 'agent'. It keeps page mode on
  desktop/tablet widths and reuses the existing compact panel mode on mobile.
-->
<script setup lang="ts">
import AgentPanel from '@/components/editor_workspace/AgentPanel.vue'

const props = withDefaults(defineProps<{
  /** Switch the full Agent surface to the existing sidebar interaction model. */
  mobile?: boolean
}>(), {
  mobile: false,
})
</script>

<template>
  <section class="agent-page">
    <div class="agent-page-shell">
      <AgentPanel
        :mode="props.mobile ? 'panel' : 'page'"
        :mobile-main="props.mobile"
        class="agent-page-panel"
      />
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
