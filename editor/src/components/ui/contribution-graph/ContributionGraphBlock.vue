<!--
  Origin UI Vue contribution graph block.

  Usage:
  Pass a level from zero through six. Every block remains a fixed 12px square;
  the parent can set --contribution-color to theme the intensity scale.
-->

<script setup lang="ts">
import { computed } from 'vue'
import type { HTMLAttributes } from 'vue'

defineOptions({ name: 'ContributionGraphBlock' })

const props = defineProps<{
  class?: HTMLAttributes['class']
  level?: number
  colors?: string[]
}>()

/** Clamp arbitrary activity values to the seven levels supported by the graph. */
const normalizedLevel = computed(() => Math.max(0, Math.min(6, Math.trunc(props.level ?? 0))))

/** Preserve Origin UI's optional per-level class override API. */
const colorClass = computed(() => props.colors?.[normalizedLevel.value] ?? '')
</script>

<template>
  <div
    data-slot="contribution-graph-block"
    :data-level="normalizedLevel"
    :class="['contribution-graph-block', colorClass, props.class]"
  >
    <slot />
  </div>
</template>

<style scoped>
.contribution-graph-block {
  box-sizing: border-box;
  width: 12px;
  height: 12px;
  flex: 0 0 12px;
  border: 0.5px solid color-mix(in srgb, var(--color-border) 30%, transparent);
  border-radius: 3px;
  background: color-mix(in srgb, var(--color-text-tertiary) 10%, transparent);
}

.contribution-graph-block[data-level='1'] { background: color-mix(in srgb, var(--contribution-color, #27885b) 23%, transparent); }
.contribution-graph-block[data-level='2'] { background: color-mix(in srgb, var(--contribution-color, #27885b) 38%, transparent); }
.contribution-graph-block[data-level='3'] { background: color-mix(in srgb, var(--contribution-color, #27885b) 54%, transparent); }
.contribution-graph-block[data-level='4'] { background: color-mix(in srgb, var(--contribution-color, #27885b) 69%, transparent); }
.contribution-graph-block[data-level='5'] { background: color-mix(in srgb, var(--contribution-color, #27885b) 84%, transparent); }
.contribution-graph-block[data-level='6'] { background: var(--contribution-color, #27885b); }
</style>
