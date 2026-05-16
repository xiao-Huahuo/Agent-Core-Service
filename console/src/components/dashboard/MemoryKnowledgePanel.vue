<!--
  记忆与知识机制观测面板 — 双层不对称布局容器。
  上层: RagMetricsCard + TokenUsageCard
  下层: LongTermMemoryCard + KnowledgeRecallCard + LatencyCard
-->

<script setup>
import RagMetricsCard from '@/components/dashboard/RagMetricsCard.vue'
import TokenUsageCard from '@/components/dashboard/TokenUsageCard.vue'
import LongTermMemoryCard from '@/components/dashboard/LongTermMemoryCard.vue'
import KnowledgeRecallCard from '@/components/dashboard/KnowledgeRecallCard.vue'
import LatencyCard from '@/components/dashboard/LatencyCard.vue'
</script>

<template>
  <div class="mk-panel">
    <div class="row-upper">
      <div class="col-rag">
        <RagMetricsCard />
      </div>
      <div class="col-token">
        <TokenUsageCard />
      </div>
    </div>
    <div class="row-lower">
      <div class="col-memory">
        <LongTermMemoryCard />
      </div>
      <div class="col-knowledge">
        <KnowledgeRecallCard />
      </div>
      <div class="col-latency">
        <LatencyCard />
      </div>
    </div>
  </div>
</template>

<style scoped>
.mk-panel {
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
}

.row-lower {
  display: grid;
  grid-template-columns: 180px 180px minmax(0, 1fr);
  gap: var(--space-10);
  flex: 1;
  min-height: 0;
}

.col-rag {
  width: 260px;
  min-width: 200px;
  height: 200px;
}

.col-token {
  width: 100%;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.col-memory {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-knowledge {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-latency {
  width: 100%;
  min-width: 0;
  min-height: 0;
}

.col-rag > *,
.col-token > *,
.col-memory > *,
.col-knowledge > *,
.col-latency > * {
  width: 100%;
  min-width: 0;
}

@media (max-width: 1200px) {
  .row-upper {
    flex-direction: column;
  }

  .col-rag {
    width: auto;
    min-width: 0;
    height: auto;
    min-height: 180px;
  }

  .row-lower {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    grid-template-areas:
      'memory knowledge'
      'latency latency';
  }

  .col-memory {
    grid-area: memory;
  }

  .col-knowledge {
    grid-area: knowledge;
  }

  .col-latency {
    grid-area: latency;
  }
}

@media (max-width: 768px) {
  .mk-panel {
    flex: none;
    overflow: visible;
    padding: var(--space-8);
  }

  .row-upper,
  .row-lower {
    display: flex;
    flex-direction: column;
  }
}

@media (max-width: 560px) {
  .mk-panel {
    gap: var(--space-8);
    padding: var(--space-8) var(--space-6);
  }
}
</style>
