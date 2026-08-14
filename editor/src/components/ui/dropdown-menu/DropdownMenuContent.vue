<!--
  Shared themed dropdown-menu surface.

  Usage:
  Place inside DropdownMenuPortal and compose menu groups/items in its slot.
-->
<script setup lang="ts">
import type { DropdownMenuContentEmits, DropdownMenuContentProps } from 'reka-ui'
import { DropdownMenuContent, useForwardPropsEmits } from 'reka-ui'

defineOptions({ name: 'UiDropdownMenuContent' })

const props = withDefaults(defineProps<DropdownMenuContentProps>(), {
  sideOffset: 6,
})
const emit = defineEmits<DropdownMenuContentEmits>()
const forwarded = useForwardPropsEmits(props, emit)
</script>

<template>
  <DropdownMenuContent v-bind="forwarded" class="ui-dropdown-content">
    <slot />
  </DropdownMenuContent>
</template>

<style>
.ui-dropdown-content {
  z-index: 100;
  min-width: 240px;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-text);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.2);
  padding: 6px;
  font-family: var(--font-ui);
  font-size: calc(13px * var(--font-scale));
  transform-origin: var(--reka-dropdown-menu-content-transform-origin);
}

.ui-dropdown-content[data-state='open'] {
  animation: dropdown-in 160ms cubic-bezier(0.16, 1, 0.3, 1) both !important;
}

.ui-dropdown-content[data-state='closed'] {
  animation: dropdown-out 120ms ease-in both !important;
}

@keyframes dropdown-in {
  from { opacity: 0; transform: scale(0.96) translateY(-5px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

@keyframes dropdown-out {
  from { opacity: 1; transform: scale(1) translateY(0); }
  to { opacity: 0; transform: scale(0.98) translateY(-2px); }
}

@media (prefers-reduced-motion: reduce) {
  .ui-dropdown-content[data-state] {
    animation-duration: 1ms !important;
  }
}
</style>
