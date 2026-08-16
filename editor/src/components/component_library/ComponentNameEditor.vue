<!--
  Reusable inline component-name editor.

  Usage:
  Displays a borderless title button and swaps it for a focused input. Enter
  or blur commits one rename; Escape restores the persisted name.
-->
<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'

defineOptions({ name: 'ComponentNameEditor' })

const props = withDefaults(defineProps<{
  name: string
  saving?: boolean
  compact?: boolean
}>(), {
  saving: false,
  compact: false,
})
const emit = defineEmits<{
  rename: [name: string]
}>()
const editing = ref(false)
const draft = ref(props.name)
const input = ref<HTMLInputElement | null>(null)

/** Keep the idle editor synchronized with successful server responses. */
watch(() => props.name, (name) => {
  if (!editing.value) draft.value = name
})

/** Enter edit mode and select the current name for immediate replacement. */
async function beginEditing(): Promise<void> {
  if (props.saving) return
  draft.value = props.name
  editing.value = true
  await nextTick()
  input.value?.focus()
  input.value?.select()
}

/** Commit one changed non-empty name and close the transient input. */
function commitRename(): void {
  if (!editing.value) return
  editing.value = false
  const name = draft.value.trim()
  if (name && name !== props.name) emit('rename', name)
  else draft.value = props.name
}

/** Cancel the transient edit without emitting a persistence request. */
function cancelRename(): void {
  editing.value = false
  draft.value = props.name
}
</script>

<template>
  <div class="component-name-editor" :class="{ compact, saving }">
    <button
      v-if="!editing"
      class="component-name-trigger"
      type="button"
      :title="`重命名 ${name}`"
      :aria-label="`重命名 ${name}`"
      @click.stop="beginEditing"
    >
      <span>{{ name }}</span>
      <IcIcon name="edit" :size="compact ? 13 : 14" />
    </button>
    <input
      v-else
      ref="input"
      v-model="draft"
      class="component-name-input"
      type="text"
      maxlength="180"
      aria-label="组件名"
      @click.stop
      @blur="commitRename"
      @keydown.enter.prevent="commitRename"
      @keydown.esc.prevent="cancelRename"
    />
  </div>
</template>

<style scoped>
.component-name-editor {
  min-width: 0;
  max-width: min(52vw, 520px);
}

.component-name-trigger {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  gap: var(--space-6);
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  padding: 3px 0;
  cursor: text;
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  font-weight: 700;
}

.component-name-trigger span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.component-name-trigger :deep(svg),
.component-name-trigger :deep(.ic-icon) {
  flex: 0 0 auto;
  opacity: 0;
  transform: translateX(-4px);
  transition:
    opacity 140ms cubic-bezier(0.23, 1, 0.32, 1),
    transform 140ms cubic-bezier(0.23, 1, 0.32, 1),
    color 140ms ease;
}

.component-name-input {
  box-sizing: border-box;
  width: min(100%, 360px);
  min-height: 30px;
  border: 0;
  border-radius: 7px;
  outline: 0;
  background: var(--color-canvas-soft);
  color: var(--color-text);
  box-shadow: none;
  padding: 0 var(--space-8);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  font-weight: 700;
  animation: component-name-input-in 160ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

.compact {
  max-width: 100%;
}

.compact .component-name-trigger,
.compact .component-name-input {
  font-size: calc(13px * var(--font-scale));
}

.saving {
  opacity: 0.58;
}

@media (hover: hover) and (pointer: fine) {
  .component-name-trigger:hover {
    color: var(--color-primary);
  }

  .component-name-trigger:hover :deep(svg),
  .component-name-trigger:hover :deep(.ic-icon) {
    color: var(--color-primary);
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes component-name-input-in {
  from { opacity: 0; transform: translateY(-4px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .component-name-trigger :deep(svg),
  .component-name-trigger :deep(.ic-icon),
  .component-name-input {
    animation: none;
    transform: none;
  }
}
</style>
