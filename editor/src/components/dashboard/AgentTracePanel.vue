<!--
  Agent trace dashboard panel.

  Usage:
  Shows the human-readable thinking trace beside the context assembly view.
-->

<script setup lang="ts">
import LanguageTraceCard from '@/components/dashboard/LanguageTraceCard.vue'
</script>

<template>
  <div class="trace-panel">
    <div class="trace-col">
      <LanguageTraceCard mode="trace" />
    </div>
    <div class="context-col">
      <LanguageTraceCard mode="context" />
    </div>
  </div>
</template>

<style scoped>
.trace-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.9fr);
  gap: var(--space-10);
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: var(--space-10);
}

.trace-col,
.context-col {
  position: relative;
  z-index: 1;
  width: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.trace-col > *,
.context-col > * {
  width: 100%;
  min-width: 0;
}

@media (max-width: 1440px) {
  .trace-panel {
    grid-template-columns: minmax(0, 1fr) minmax(320px, 0.9fr);
  }
}

@media (max-width: 980px) {
  .trace-panel {
    grid-template-columns: minmax(0, 1fr);
    flex: none;
    overflow: visible;
    padding: var(--space-8);
  }
}

@media (max-width: 560px) {
  .trace-panel {
    gap: var(--space-8);
    padding: var(--space-8) var(--space-6);
  }
}
</style>
