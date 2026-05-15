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
  overflow: hidden;
  padding: var(--space-10);
}

.row-upper {
  display: flex;
  gap: var(--space-10);
}

.row-lower {
  display: flex;
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
  flex: 1;
  min-width: 0;
}

.col-memory {
  width: 180px;
  min-width: 140px;
}

.col-knowledge {
  width: 180px;
  min-width: 140px;
}

.col-latency {
  flex: 1;
  min-width: 0;
}
</style>
