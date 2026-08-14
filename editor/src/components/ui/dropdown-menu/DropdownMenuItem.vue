<!--
  Shared themed dropdown action item.

  Usage:
  Place inside DropdownMenuContent for commands that are not radio choices.
  Use variant="destructive" for irreversible actions.
-->
<script setup lang="ts">
import type { DropdownMenuItemEmits, DropdownMenuItemProps } from 'reka-ui'
import { DropdownMenuItem, useForwardPropsEmits } from 'reka-ui'

defineOptions({ name: 'UiDropdownMenuItem' })

const props = defineProps<DropdownMenuItemProps & { variant?: 'default' | 'destructive' }>()
const emit = defineEmits<DropdownMenuItemEmits>()
const forwarded = useForwardPropsEmits(props, emit)
</script>

<template>
  <DropdownMenuItem
    v-bind="forwarded"
    class="ui-dropdown-item"
    :class="{ 'ui-dropdown-item-destructive': variant === 'destructive' }"
  >
    <slot />
  </DropdownMenuItem>
</template>

<style>
.ui-dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  min-width: 0;
  padding: 0 8px;
  border-radius: 5px;
  color: var(--color-text-secondary);
  outline: none;
  cursor: default;
  user-select: none;
}

.ui-dropdown-item[data-highlighted] {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  color: var(--color-text);
}

.ui-dropdown-item[data-disabled] {
  opacity: 0.42;
  pointer-events: none;
}

.ui-dropdown-item-destructive,
.ui-dropdown-item-destructive[data-highlighted] {
  color: var(--color-danger);
}

.ui-dropdown-item-destructive[data-highlighted] {
  background: color-mix(in srgb, var(--color-danger) 12%, transparent);
}
</style>
