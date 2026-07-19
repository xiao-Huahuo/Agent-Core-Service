<!--
  TimeConsumptionPanel —— RAG 指标、Token 消耗与耗时观测页。
-->

<script setup lang="ts">
import RagMetricsCard from '@/components/dashboard/RagMetricsCard.vue'
import TokenUsageCard from '@/components/dashboard/TokenUsageCard.vue'
import LatencyCard from '@/components/dashboard/LatencyCard.vue'
</script>

<template>
  <div class="time-panel">
    <div class="row-upper">
      <div class="col-rag">
        <RagMetricsCard />
      </div>
      <div class="col-token">
        <TokenUsageCard />
      </div>
    </div>

    <div class="row-lower">
      <div class="col-empty" aria-hidden="true"></div>
      <div class="col-empty" aria-hidden="true"></div>
      <div class="col-latency">
        <LatencyCard />
      </div>
    </div>
  </div>
</template>

<style scoped>
.time-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-10);
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: var(--space-10);
}

.row-upper {
  display: flex;
  gap: var(--space-10);
  min-height: 0;
  height: 240px;
  align-items: stretch;
}

.row-lower {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(280px, 1fr) minmax(0, 1fr);
  gap: var(--space-10);
  flex: 1;
  min-height: 0;
}

.col-rag {
  flex: 0 0 auto;
  min-width: 200px;
  max-width: 340px;
  min-height: 0;
}

.col-token {
  width: 100%;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.col-empty,
.col-latency {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-rag > *,
.col-token > *,
.col-latency > * {
  height: 100%;
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.time-panel :deep(.card-block) {
  box-shadow: none;
}

@media (max-width: 1200px) {
  .row-upper {
    flex-direction: column;
    height: auto;
  }

  .col-rag {
    flex: 1 1 auto;
    max-width: none;
    min-height: 180px;
    max-height: none;
  }

  .col-token {
    flex: none;
    height: 300px;
  }

  .row-lower {
    grid-template-columns: minmax(0, 1fr);
  }

  .col-empty {
    display: none;
  }
}

@media (max-width: 768px) {
  .time-panel {
    flex: none;
    overflow: visible;
    padding: var(--space-8);
  }

  .row-upper,
  .row-lower {
    display: flex;
    flex-direction: column;
  }

  .col-token,
  .col-latency {
    flex: none;
    height: 320px;
  }
}

@media (max-width: 560px) {
  .time-panel {
    gap: var(--space-8);
    padding: var(--space-8) var(--space-6);
  }
}
</style>
