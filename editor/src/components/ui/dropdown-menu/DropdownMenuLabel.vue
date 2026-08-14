<!-- Shared section label for themed dropdown menus. -->
<script setup lang="ts">
import type { DropdownMenuLabelProps } from 'reka-ui'
import { DropdownMenuLabel } from 'reka-ui'

defineOptions({ name: 'UiDropdownMenuLabel' })
const props = defineProps<DropdownMenuLabelProps>()
</script>

<template>
  <DropdownMenuLabel v-bind="props" class="ui-dropdown-label">
    <slot />
  </DropdownMenuLabel>
</template>

<style>
.ui-dropdown-label {
  padding: 5px 8px 4px;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
</style>
