<!--
  Context compression lifecycle bar.

  Usage:
  AgentPanel renders this independent status while the backend synchronously
  compresses the working context before the next model decision.
-->
<script setup lang="ts">
defineProps<{
  failed?: boolean
}>()
</script>

<template>
  <div class="context-compression-status" role="status" aria-live="polite">
    <span class="compression-track" aria-hidden="true"><span></span></span>
    <span>{{ failed ? '上下文压缩失败，已安全回退' : '正在压缩上下文' }}</span>
  </div>
</template>

<style scoped>
.context-compression-status {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-height: 24px;
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: calc(12px * var(--font-scale));
}

.compression-track {
  width: 42px;
  height: 2px;
  overflow: hidden;
  background: var(--color-border);
}

.compression-track span {
  display: block;
  width: 45%;
  height: 100%;
  background: var(--color-primary);
  animation: compression-slide 900ms ease-in-out infinite alternate;
}

@keyframes compression-slide {
  from { transform: translateX(-15%); }
  to { transform: translateX(135%); }
}
</style>
