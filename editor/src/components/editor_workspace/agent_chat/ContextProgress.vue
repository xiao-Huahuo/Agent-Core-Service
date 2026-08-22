<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  currentTokens?: number
  maxContextTokens?: number
}>(), {
  currentTokens: 0,
  maxContextTokens: 1000000,
})

const percentage = computed(() => {
  if (props.currentTokens <= 0 || props.maxContextTokens <= 0) return 0
  return Math.min(100, Math.round((props.currentTokens / props.maxContextTokens) * 100))
})

const ringColor = computed(() => {
  if (percentage.value >= 90) return 'var(--color-error, #ef4444)'
  if (percentage.value >= 70) return 'var(--color-warning, #f59e0b)'
  return 'var(--color-text-muted, #8b93a7)'
})

const circumference = 2 * Math.PI * 7 // r=7
const dashOffset = computed(() => {
  return circumference - (percentage.value / 100) * circumference
})
</script>

<template>
  <div v-if="currentTokens > 0" class="context-progress" :title="`${currentTokens.toLocaleString()} / ${maxContextTokens.toLocaleString()} tokens`">
    <svg class="ring" width="18" height="18" viewBox="0 0 18 18">
      <circle cx="9" cy="9" r="7" fill="none" stroke="rgba(148,163,184,0.15)" stroke-width="2" />
      <circle
        cx="9" cy="9" r="7"
        fill="none"
        :stroke="ringColor"
        stroke-width="2"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
        transform="rotate(-90 9 9)"
        class="ring-fill"
      />
    </svg>
    <span class="pct" :style="{ color: ringColor }">{{ percentage }}%</span>
  </div>
</template>

<style scoped>
.context-progress {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: default;
}

.ring {
  flex-shrink: 0;
}

.ring-fill {
  transition: stroke-dashoffset 0.4s ease, stroke 0.3s ease;
}

.pct {
  font-family: var(--font-ui);
  font-size: calc(10px * var(--font-scale));
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  line-height: 1;
  transition: color 0.3s ease;
}
</style>
