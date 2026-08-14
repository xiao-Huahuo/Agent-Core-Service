<!-- Shared visual separator for themed dropdown-menu groups. -->
<script setup lang="ts">
import type { DropdownMenuSeparatorProps } from 'reka-ui'
import { DropdownMenuSeparator } from 'reka-ui'

defineOptions({ name: 'UiDropdownMenuSeparator' })
const props = defineProps<DropdownMenuSeparatorProps>()
</script>

<template>
  <DropdownMenuSeparator v-bind="props" class="ui-dropdown-separator" />
</template>

<style>
.ui-dropdown-separator {
  height: 1px;
  margin: 5px -6px;
  background: var(--color-border);
}
</style>
