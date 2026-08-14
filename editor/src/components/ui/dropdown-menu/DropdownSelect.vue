<!--
  Shared compact dropdown select.

  Usage:
  Bind a string or numeric v-model and pass matching label/value options. The
  trigger accepts caller classes while selection and focus stay managed by Reka.
-->
<script setup lang="ts" generic="T extends string | number">
import { computed, useAttrs } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import DropdownMenuContent from '@/components/ui/dropdown-menu/DropdownMenuContent.vue'
import DropdownMenuRadioItem from '@/components/ui/dropdown-menu/DropdownMenuRadioItem.vue'
import {
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRoot as DropdownMenu,
  DropdownMenuTrigger,
} from 'reka-ui'

defineOptions({ name: 'DropdownSelect', inheritAttrs: false })

const props = defineProps<{
  options: Array<{ value: T; label: string }>
  disabled?: boolean
  align?: 'start' | 'center' | 'end'
}>()
const model = defineModel<T>({ required: true })
const attrs = useAttrs()
const selectedLabel = computed(() => props.options.find((option) => option.value === model.value)?.label ?? '')
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <button
        v-bind="attrs"
        class="ui-dropdown-select-trigger"
        type="button"
        :disabled="disabled"
      >
        <span>{{ selectedLabel }}</span>
        <IcIcon name="chevron-down" :size="14" aria-hidden="true" />
      </button>
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent :align="align ?? 'end'">
        <DropdownMenuRadioGroup v-model="model">
          <DropdownMenuRadioItem v-for="option in options" :key="String(option.value)" :value="option.value">
            {{ option.label }}
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenu>
</template>

<style>
.ui-dropdown-select-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 28px;
  min-width: 0;
  padding: 0 8px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  cursor: pointer;
}

.ui-dropdown-select-trigger:hover,
.ui-dropdown-select-trigger[data-state='open'] {
  background: var(--color-primary-softer);
  color: var(--color-text);
}

.ui-dropdown-select-trigger:disabled {
  cursor: default;
  opacity: 0.42;
}
</style>
