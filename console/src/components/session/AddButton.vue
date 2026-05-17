<script setup>
import { Plus } from 'lucide-vue-next'
defineEmits(['click'])
</script>

<template>
  <button class="new-btn" @click="$emit('click')">
    <Plus :size="13" />
    <span>New Session</span>
  </button>
</template>

<style scoped>
.new-btn {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  padding: var(--space-8) var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.new-btn:hover {
  color: var(--color-text-primary);
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
}
</style>
