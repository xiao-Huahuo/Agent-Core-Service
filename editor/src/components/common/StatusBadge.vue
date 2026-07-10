<!--
  Status badge component.

  Usage:
  Render indexing and file lifecycle states with consistent semantic colors.
-->
<script setup lang="ts">
import type { IndexStatus } from '@/types/knowledge'

defineProps<{
  status?: IndexStatus
}>()

const labels: Record<IndexStatus, string> = {
  clean: 'clean',
  dirty: 'dirty',
  indexing: 'indexing',
  indexed: 'indexed',
  failed: 'failed',
}
</script>

<template>
  <span v-if="status" class="status-badge" :data-status="status">
    {{ labels[status] }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  height: 18px;
  padding: 0 var(--space-6);
  border: 1px solid currentColor;
  border-radius: var(--radius-sm);
  font-family: var(--font-code);
  font-size: 11px;
  line-height: 1;
}

.status-badge[data-status='clean'] {
  color: var(--color-text-muted);
}

.status-badge[data-status='dirty'] {
  color: var(--color-warning);
}

.status-badge[data-status='indexing'] {
  color: var(--color-primary-hover);
}

.status-badge[data-status='indexed'] {
  color: var(--color-success);
}

.status-badge[data-status='failed'] {
  color: var(--color-danger);
}
</style>
