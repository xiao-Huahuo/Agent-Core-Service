<!--
  Agent queue dropdown.

  Usage:
  Keeps the queue-specific public API while delegating selection, focus, menu
  background, and motion to the shared Reka dropdown select.
-->
<script setup lang="ts">
import DropdownSelect from '@/components/ui/dropdown-menu/DropdownSelect.vue'

defineOptions({ name: 'QueueDropdown' })

type DropdownOption = { value: string; label: string }

const props = defineProps<{
  options: DropdownOption[]
  'aria-label': string
  disabled?: boolean
}>()
const model = defineModel<string>({ required: true })
</script>

<template>
  <DropdownSelect
    v-model="model"
    class="queue-select-trigger"
    :options="options"
    :aria-label="props['aria-label']"
    :disabled="disabled"
  />
</template>

<style scoped>
.queue-select-trigger {
  width: 100%;
  color: var(--color-text);
}
</style>
