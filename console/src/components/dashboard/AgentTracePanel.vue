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
  display: flex;
  gap: var(--space-10);
  flex: 1;
  overflow: hidden;
  padding: var(--space-10);
}

.col-left {
  width: 220px;
  min-width: 180px;
}

.col-mid {
  flex: 1;
  min-width: 0;
}

.col-right {
  width: 260px;
  min-width: 200px;
}
</style>
