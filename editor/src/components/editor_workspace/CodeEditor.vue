<!--
  Code editor surface.

  Usage:
  Provides a lightweight textarea-based code editor for supported source files.
  Syntax highlighting is handled by CodePreview.vue in Preview/Split mode.
-->
<script setup lang="ts">
const model = defineModel<string>({ required: true })

defineProps<{
  language: string
  readonly?: boolean
}>()

defineEmits<{
  save: []
}>()
</script>

<template>
  <section class="code-editor">
    <div class="code-editor-header">
      <span>{{ language || 'text' }}</span>
    </div>
    <textarea
      v-model="model"
      class="code-editor-input"
      :class="{ readonly }"
      spellcheck="false"
      :readonly="readonly"
      @keydown.ctrl.s.prevent="$emit('save')"
      @keydown.meta.s.prevent="$emit('save')"
    ></textarea>
  </section>
</template>

<style scoped>
.code-editor {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-canvas);
}

.code-editor-header {
  display: flex;
  align-items: center;
  height: 28px;
  padding: 0 var(--space-10);
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: 11px;
}

.code-editor-input {
  flex: 1;
  min-width: 0;
  min-height: 0;
  padding: var(--space-12);
  resize: none;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font-family: var(--font-text);
  font-size: 13px;
  line-height: 1.6;
  tab-size: 2;
  white-space: pre;
}

.code-editor-input.readonly {
  cursor: default;
  color: var(--color-text-secondary);
}
</style>
