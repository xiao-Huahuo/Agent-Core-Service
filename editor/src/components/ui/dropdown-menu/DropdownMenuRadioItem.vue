<!-- Shared radio item with a stable check-indicator column. -->
<script setup lang="ts">
import type { DropdownMenuRadioItemEmits, DropdownMenuRadioItemProps } from 'reka-ui'
import { DropdownMenuItemIndicator, DropdownMenuRadioItem, useForwardPropsEmits } from 'reka-ui'

import IcIcon from '@/components/common/IcIcon.vue'

defineOptions({ name: 'UiDropdownMenuRadioItem' })

const props = defineProps<DropdownMenuRadioItemProps>()
const emit = defineEmits<DropdownMenuRadioItemEmits>()
const forwarded = useForwardPropsEmits(props, emit)
</script>

<template>
  <DropdownMenuRadioItem v-bind="forwarded" class="ui-dropdown-radio-item">
    <span class="ui-dropdown-indicator" aria-hidden="true">
      <DropdownMenuItemIndicator>
        <IcIcon name="check" :size="14" />
      </DropdownMenuItemIndicator>
    </span>
    <span class="ui-dropdown-radio-copy"><slot /></span>
  </DropdownMenuRadioItem>
</template>

<style>
.ui-dropdown-radio-item {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-height: 30px;
  border-radius: 5px;
  color: var(--color-text-secondary);
  outline: none;
  padding: 0 8px;
  cursor: default;
  user-select: none;
}

.ui-dropdown-radio-item[data-highlighted] {
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  color: var(--color-text);
}

.ui-dropdown-radio-item[data-state='checked'] {
  color: var(--color-primary);
}

.ui-dropdown-radio-item[data-disabled] {
  opacity: 0.42;
  pointer-events: none;
}

.ui-dropdown-indicator {
  display: grid;
  place-items: center;
  width: 16px;
  height: 16px;
}

.ui-dropdown-radio-copy {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
