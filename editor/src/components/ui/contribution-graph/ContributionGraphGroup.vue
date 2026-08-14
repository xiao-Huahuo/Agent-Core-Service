<!--
  Origin UI Vue contribution graph week group.

  Usage:
  Place seven ContributionGraphBlock components in each group.
-->

<script setup lang="ts">
import type { HTMLAttributes } from 'vue'

defineOptions({ name: 'ContributionGraphGroup' })

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <div data-slot="contribution-graph-group" :class="['contribution-graph-group', props.class]">
    <slot />
  </div>
</template>

<style scoped>
.contribution-graph-group {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  gap: 4px;
}
</style>
