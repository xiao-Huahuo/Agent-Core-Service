<!--
  Compact shared code input.

  Usage:
  Provides the small code-entry surface shared by component uploads and
  library script books while preserving the caller's v-model text value.
-->
<script setup lang="ts">
defineOptions({ name: 'CompactCodeInput' })

withDefaults(defineProps<{
  /** Text displayed above the editable code surface. */
  label: string
  /** Native textarea placeholder shown when the model is empty. */
  placeholder?: string
  /** Editable source text owned by the parent form. */
  modelValue: string
  /** Prevents edits when the same code surface is used for read-only previews. */
  readonly?: boolean
}>(), {
  placeholder: '',
  readonly: false,
})

const emit = defineEmits<{
  /** Keeps this field compatible with Vue's standard v-model contract. */
  'update:modelValue': [value: string]
}>()

/** Forward native textarea edits without introducing local form state. */
function updateValue(event: Event): void {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
}
</script>

<template>
  <label class="compact-code-input">
    <span class="compact-code-input__label">{{ label }}</span>
    <textarea
      class="compact-code-input__field"
      :value="modelValue"
      :placeholder="placeholder"
      :readonly="readonly"
      spellcheck="false"
      @input="updateValue"
    ></textarea>
  </label>
</template>

<style scoped>
.compact-code-input {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  background: var(--color-canvas);
}

.compact-code-input__label {
  flex: 0 0 auto;
  min-height: 30px;
  padding: var(--space-8) var(--space-12);
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}

.compact-code-input__field {
  flex: 1;
  width: 100%;
  min-height: 0;
  resize: none;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  padding: var(--space-12);
  font-family: var(--font-text);
  font-size: calc(13px * var(--font-scale));
  line-height: 1.6;
  tab-size: 2;
}
</style>
