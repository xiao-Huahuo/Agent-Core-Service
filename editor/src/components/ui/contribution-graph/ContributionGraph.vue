<!--
  Origin UI Vue contribution graph root.

  Usage:
  Wrap ContributionGraphGroup columns inside this component. It preserves the
  official fixed-gap flex structure and exposes the same class prop.
-->

<script setup lang="ts">
import type { HTMLAttributes } from 'vue'

defineOptions({ name: 'ContributionGraph' })

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <div data-slot="contribution-graph" :class="['contribution-graph', props.class]">
    <slot />
  </div>
</template>

<style scoped>
.contribution-graph {
  display: flex;
  flex: 1;
  gap: 4px;
}
</style>
