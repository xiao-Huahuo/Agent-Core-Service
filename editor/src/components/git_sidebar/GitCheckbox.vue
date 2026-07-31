<!--
  Animated Git selection checkbox.

  Usage:
  Renders the draw-on checkmark toggle used by Git change groups and file rows.
  It is a controlled input: the parent owns the checked state and reacts to the
  change event. The native input is visually hidden but stays accessible.
-->
<script setup lang="ts">
defineOptions({ name: 'GitCheckbox' })

defineProps<{
  checked: boolean
  label: string
}>()

const emit = defineEmits<{
  change: [checked: boolean]
}>()
</script>

<template>
  <label class="git-check">
    <input
      type="checkbox"
      class="sr-only"
      :checked="checked"
      :aria-label="label"
      @change="emit('change', ($event.target as HTMLInputElement).checked)"
    />
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path d="M1,9 L1,3.5 C1,2 2,1 3.5,1 L14.5,1 C16,1 17,2 17,3.5 L17,14.5 C17,16 16,17 14.5,17 L3.5,17 C2,17 1,16 1,14.5 L1,9 Z" />
      <polyline points="1 9 7 14 15 4" />
    </svg>
  </label>
</template>

<style scoped>
.git-check {
  position: relative;
  display: inline-flex;
  width: 18px;
  height: 18px;
  margin: auto;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transform: translate3d(0, 0, 0);
}

.git-check:before {
  content: "";
  position: absolute;
  top: -15px;
  left: -15px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-primary-soft);
  opacity: 0;
  pointer-events: none;
  transition: opacity 200ms ease;
}

.git-check svg {
  position: relative;
  z-index: 1;
  fill: none;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke: var(--color-text-muted);
  stroke-width: 1.5;
  transform: translate3d(0, 0, 0);
  transition: stroke 200ms ease;
}

.git-check svg path {
  stroke-dasharray: 60;
  stroke-dashoffset: 0;
}

.git-check svg polyline {
  stroke-dasharray: 22;
  stroke-dashoffset: 66;
}

.git-check:hover:before {
  opacity: 1;
}

.git-check:hover svg {
  stroke: var(--color-primary);
}

.git-check input:checked + svg {
  stroke: var(--color-primary);
}

.git-check input:checked + svg path {
  stroke-dashoffset: 60;
  transition: stroke-dashoffset 300ms linear;
}

.git-check input:checked + svg polyline {
  stroke-dashoffset: 42;
  transition: stroke-dashoffset 200ms linear;
  transition-delay: 150ms;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
