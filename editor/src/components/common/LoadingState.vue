<!--
  Pixel-grid loading indicator.

  Usage:
  Shows a compact loading label and elapsed time. Use `variant` to select the
  Drive, Dots, or Orbit pixel animation.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

/** Available pixel animation styles. */
type LoadingVariant = 'Drive' | 'Dots' | 'Orbit'

/** Maps the 3 × 3 grid to a right-moving chevron wave. */
const chevronDelays = Array.from({ length: 9 }, (_, index) => {
  const row = Math.floor(index / 3)
  const column = index % 3
  return (column + Math.abs(row - 1)) * 90
})

/** Maps perimeter cells to the order used by the orbit animation. */
const orbitOrder = [0, 1, 2, 5, 8, 7, 6, 3]
const orbitDelays = Array.from({ length: 9 }, (_, index) => {
  const orbitIndex = orbitOrder.indexOf(index)
  return orbitIndex === -1 ? null : orbitIndex * 110
})

/** Defines timing and shape for each public loading variant. */
const patterns = {
  Drive: { delays: chevronDelays, duration: 650, round: false },
  Dots: { delays: chevronDelays, duration: 650, round: true },
  Orbit: { delays: orbitDelays, duration: 950, round: false },
} as const

const props = withDefaults(defineProps<{
  /** Text shown beside the animated grid. */
  label?: string
  /** Pixel animation style. */
  variant?: LoadingVariant
  /** Shared turn start time, so remounting does not reset elapsed time. */
  startedAtMs?: number
  /** Whether to render the shimmering status label. */
  showLabel?: boolean
  /** Whether to render the elapsed-time display. */
  showElapsed?: boolean
}>(), {
  label: 'Thinking',
  variant: 'Drive',
  showLabel: true,
  showElapsed: true,
})

/** Refreshes the clock while the component is visible. */
const nowMs = ref(Date.now())
const mountedAtMs = Date.now()
let elapsedTimer: number | undefined

onMounted(() => {
  elapsedTimer = window.setInterval(() => {
    nowMs.value = Date.now()
  }, 100)
})

onBeforeUnmount(() => {
  if (elapsedTimer !== undefined) window.clearInterval(elapsedTimer)
})

/** Formats the elapsed time for the compact monospaced display. */
const elapsed = computed(() => {
  const candidateStartMs = props.startedAtMs
  const startMs = typeof candidateStartMs === 'number'
    && candidateStartMs >= 1_000_000_000_000
    && candidateStartMs <= nowMs.value
    ? candidateStartMs
    : mountedAtMs
  const totalSeconds = Math.max(0, nowMs.value - startMs) / 1000
  return totalSeconds < 60
    ? `${totalSeconds.toFixed(1)}s`
    : `${Math.floor(totalSeconds / 60)}m ${(totalSeconds % 60).toFixed(1)}s`
})

/** Selects the animation definition requested by the consumer. */
const pattern = computed(() => patterns[props.variant])
</script>

<template>
  <div class="loading-state" role="status" :aria-label="label">
    <span aria-hidden="true" class="pixel-grid">
      <span
        v-for="(delay, index) in pattern.delays"
        :key="index"
        class="pixel"
        :class="{ 'pixel--round': pattern.round, 'pixel--inactive': delay === null }"
        :style="{
          opacity: delay === null ? 0.07 : 0.15,
          '--pixel-delay': `${delay ?? 0}ms`,
          '--pixel-duration': `${pattern.duration}ms`,
        }"
      />
    </span>
    <span v-if="showLabel" class="loading-state__label">{{ label }}</span>
    <span v-if="showElapsed" class="loading-state__elapsed">{{ elapsed }}</span>
  </div>
</template>

<style scoped>
.loading-state {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  width: fit-content;
}

.pixel-grid { display: grid; grid-template-columns: repeat(3, 4px); gap: 2px; }
.pixel {
  width: 4px;
  height: 4px;
  border-radius: 1px;
  background: var(--color-text-primary);
  animation: pixel-on var(--pixel-duration) ease-in-out var(--pixel-delay) infinite;
}
.pixel--round { border-radius: 50%; }
.pixel--inactive { animation: none; }

.loading-state__label {
  color: transparent;
  background: linear-gradient(90deg, var(--color-text-tertiary) 35%, var(--color-text-primary) 50%, var(--color-text-tertiary) 65%);
  -webkit-background-clip: text;
  background-clip: text;
  background-size: 200% 100%;
  font-family: var(--font-ui);
  font-size: calc(13px * var(--font-scale));
  font-weight: 500;
  animation: shimmer-text 1.4s linear infinite;
}

.loading-state__elapsed {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: calc(12px * var(--font-scale));
  font-variant-numeric: tabular-nums;
}

@keyframes pixel-on {
  0%, 100% { opacity: 0.15; transform: scale(1); }
  45% { opacity: 1; transform: scale(1); }
}

@keyframes shimmer-text { to { background-position: -200% 0; } }

@media (prefers-reduced-motion: reduce) {
  .pixel, .loading-state__label { animation: none !important; }
}
</style>
