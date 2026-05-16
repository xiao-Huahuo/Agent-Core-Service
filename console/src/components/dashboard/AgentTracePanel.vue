<!--
  Agent 轨迹观测面板 — 三栏布局容器。
  左: StateGraphCard, 中: LanguageTraceCard, 右: ExecutionTraceCard。
-->

<script setup>
import StateGraphCard from '@/components/dashboard/StateGraphCard.vue'
import LanguageTraceCard from '@/components/dashboard/LanguageTraceCard.vue'
import ExecutionTraceCard from '@/components/dashboard/ExecutionTraceCard.vue'
</script>

<template>
  <div class="trace-panel">
    <div class="col-left">
      <StateGraphCard />
    </div>
    <div class="col-mid">
      <LanguageTraceCard />
    </div>
    <div class="col-right">
      <ExecutionTraceCard />
    </div>
  </div>
</template>

<style scoped>
.trace-panel {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr) 260px;
  gap: var(--space-10);
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: var(--space-10);
}

.col-left {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-mid {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-right {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-left > *,
.col-mid > *,
.col-right > * {
  width: 100%;
  min-width: 0;
}

@media (min-width: 1600px) and (min-aspect-ratio: 6/5) {
  .trace-panel {
    grid-template-columns: clamp(320px, calc(100dvh - 340px), 460px) minmax(0, 1fr) 260px;
  }
}

@media (max-width: 1440px) {
  .trace-panel {
    grid-template-columns: 280px minmax(0, 1fr) 240px;
  }
}

@media (max-width: 1200px) {
  .trace-panel {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    grid-template-areas:
      'left left'
      'mid right';
  }

  .col-left {
    grid-area: left;
  }

  .col-mid {
    grid-area: mid;
  }

  .col-right {
    grid-area: right;
  }
}

@media (max-width: 768px) {
  .trace-panel {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      'left'
      'mid'
      'right';
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
