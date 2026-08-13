<!--
  Agent queue dropdown.

  Usage:
  Reuses the resource manager's sort-menu interaction and visual hierarchy for
  queue form fields and toolbar settings. Bind it with v-model and provide the
  available values as label/value pairs.
-->
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'

defineOptions({ name: 'QueueDropdown' })

type DropdownOption = { value: string; label: string }

const props = defineProps<{
  modelValue: string
  options: DropdownOption[]
  ariaLabel: string
  disabled?: boolean
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const root = ref<HTMLElement | null>(null)
const open = ref(false)

/** 收起点击区域之外的菜单。 */
function closeWhenClickedOutside(event: PointerEvent) {
  if (!root.value?.contains(event.target as Node)) open.value = false
}

/** 选择一个值，并立即关闭菜单。 */
function select(value: string) {
  emit('update:modelValue', value)
  open.value = false
}

onMounted(() => document.addEventListener('pointerdown', closeWhenClickedOutside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', closeWhenClickedOutside))
</script>

<template>
  <div ref="root" class="queue-select">
    <button
      class="queue-select-trigger"
      type="button"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      :disabled="disabled"
      @click="open = !open"
    >
      <span>{{ options.find((option) => option.value === modelValue)?.label }}</span>
      <IcIcon name="chevron-down" :size="16" />
    </button>

    <div v-if="open" class="queue-select-menu" role="listbox" :aria-label="ariaLabel">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        role="option"
        :aria-selected="option.value === modelValue"
        @click="select(option.value)"
      >
        <IcIcon v-if="option.value === modelValue" name="check" :size="16" />
        <span v-else class="queue-select-check-placeholder"></span>
        <span class="queue-select-icon-placeholder"></span>
        <span>{{ option.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.queue-select {
  position: relative;
  min-width: 0;
}

.queue-select-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-8);
  width: 100%;
  min-height: 28px;
  border: 0;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  cursor: pointer;
}

.queue-select-trigger:disabled {
  cursor: default;
  opacity: 0.62;
}

.queue-select-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 20;
  display: grid;
  min-width: 172px;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
  animation: queue-select-menu-pop 140ms ease-out both;
}

.queue-select-menu button {
  display: grid;
  grid-template-columns: 16px 16px minmax(0, 1fr);
  align-items: center;
  gap: var(--space-6);
  height: 30px;
  padding: 0 var(--space-6);
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  text-align: left;
  cursor: pointer;
  animation: queue-select-row-drop 150ms ease-out both;
}

.queue-select-menu button:hover {
  background: var(--color-selection-blue-soft);
  color: var(--color-text);
}

.queue-select-check-placeholder,
.queue-select-icon-placeholder {
  width: 14px;
}

@keyframes queue-select-menu-pop {
  from { transform: translateY(-6px); }
  to { transform: translateY(0); }
}

@keyframes queue-select-row-drop {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
