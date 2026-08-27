<!--
  Shared resource sorting menu.

  Usage:
  FileTreePanel and LiteratureReadingView provide their domain sort keys while
  this component keeps the exact menu layout, icons, animation, and direction
  controls consistent across resource sidebars.
-->
<script setup lang="ts">
defineProps<{
  options: Array<{ value: string; label: string; icon: string }>
  sortKey: string
  direction: 'asc' | 'desc'
}>()

defineEmits<{
  selectKey: [value: string]
  selectDirection: [value: 'asc' | 'desc']
}>()

import IcIcon from '@/components/common/IcIcon.vue'
</script>

<template>
  <div class="sort-menu ui-floating-menu-surface" role="menu" @click.stop>
    <button v-for="option in options" :key="option.value" type="button" @click="$emit('selectKey', option.value)">
      <IcIcon v-if="sortKey === option.value" name="check" :size="14" />
      <span v-else class="sort-check-placeholder"></span>
      <IcIcon :name="option.icon" :size="14" />
      <span>{{ option.label }}</span>
    </button>
    <hr />
    <button type="button" @click="$emit('selectDirection', 'asc')">
      <IcIcon v-if="direction === 'asc'" name="check" :size="14" />
      <span v-else class="sort-check-placeholder"></span>
      <IcIcon name="arrow-up" :size="14" />
      <span>升序</span>
    </button>
    <button type="button" @click="$emit('selectDirection', 'desc')">
      <IcIcon v-if="direction === 'desc'" name="check" :size="14" />
      <span v-else class="sort-check-placeholder"></span>
      <IcIcon name="arrow-down" :size="14" />
      <span>降序</span>
    </button>
  </div>
</template>

<style scoped>
.sort-menu { position: absolute; top: calc(100% + 6px); right: 0; z-index: 50; display: grid; min-width: 172px; padding: var(--space-4); animation: sort-menu-pop 140ms ease-out both; }
.sort-menu button { display: grid; grid-template-columns: 16px 16px minmax(0, 1fr); align-items: center; gap: var(--space-6); height: 28px; padding: 0 var(--space-6); border: 0; border-radius: var(--radius-sm); background: transparent; color: var(--color-text-secondary); font: inherit; font-size: calc(12px * var(--font-scale)); text-align: left; cursor: pointer; animation: sort-row-drop 150ms ease-out both; }
.sort-menu button:nth-of-type(1) { animation-delay: 20ms; }.sort-menu button:nth-of-type(2) { animation-delay: 38ms; }.sort-menu button:nth-of-type(3) { animation-delay: 56ms; }.sort-menu button:nth-of-type(4) { animation-delay: 74ms; }.sort-menu button:nth-of-type(5) { animation-delay: 92ms; }.sort-menu button:nth-of-type(6) { animation-delay: 110ms; }
.sort-menu button:hover { background: var(--color-selection-blue-soft); color: var(--color-text); }
.sort-menu hr { width: 100%; margin: var(--space-6) 0; border: 0; border-top: 1px solid var(--color-border); }
.sort-check-placeholder { width: 14px; }
@keyframes sort-menu-pop { from { transform: translateY(-6px); } }
@keyframes sort-row-drop { from { opacity: 0; transform: translateY(-4px); } }
</style>
