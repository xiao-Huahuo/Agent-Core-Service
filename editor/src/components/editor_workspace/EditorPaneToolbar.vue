<!--
  Shared editor pane toolbar.

  Usage:
  Renders the same file tab, mode switch, contextual action slot, and animated
  save control for the workspace editor and scanner editor panes.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'
import EditorModeSwitch from '@/components/editor_workspace/EditorModeSwitch.vue'
import type { EditorWorkspaceMode } from '@/types/knowledge'

defineOptions({ name: 'EditorPaneToolbar' })

const props = withDefaults(defineProps<{
  title: string
  modelValue: EditorWorkspaceMode
  options: Array<{ mode: EditorWorkspaceMode; label: string; icon: string }>
  dirty?: boolean
  closable?: boolean
  compact?: boolean
  saveLabel?: string
  saveDisabled?: boolean
}>(), {
  dirty: false,
  closable: false,
  compact: false,
  saveLabel: '',
  saveDisabled: false,
})

const emit = defineEmits<{
  activate: []
  close: []
  save: []
  'update:modelValue': [mode: EditorWorkspaceMode]
}>()
</script>

<template>
  <header class="editor-pane-toolbar" :class="{ compact: props.compact }">
    <div class="editor-pane-tab-list">
      <button class="editor-pane-tab" :class="{ closable: props.closable }" type="button" @click="emit('activate')">
        <span class="editor-pane-tab-title">{{ props.title }}</span>
        <i v-if="props.dirty" class="editor-pane-dirty-dot"></i>
        <IcIcon v-if="props.closable" name="close" class="editor-pane-tab-close" :size="13" @click.stop="emit('close')" />
      </button>
    </div>
    <div class="editor-pane-toolbar-actions">
      <EditorModeSwitch
        class="editor-pane-mode-control"
        :class="{ 'single-mode': props.options.length === 1 }"
        :model-value="props.modelValue"
        :options="props.options"
        @update:model-value="emit('update:modelValue', $event)"
      />
      <slot name="actions" />
      <button v-if="props.saveLabel" class="editor-pane-save" type="button" :disabled="props.saveDisabled" @click="emit('save')">
        <svg class="save-motion-icon" aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path data-save-path="box" d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" />
          <path data-save-path="top" d="M7 3v5h8" />
          <path data-save-path="bottom" d="M17 20v-7H7v7" />
        </svg>
        <span>{{ props.saveLabel }}</span>
      </button>
    </div>
  </header>
</template>

<style scoped>
.editor-pane-toolbar { display: flex; min-width: 0; min-height: 34px; align-items: center; justify-content: space-between; gap: var(--space-8); padding: var(--space-8) var(--space-10) 0; background: var(--color-canvas-soft); }
.editor-pane-tab-list { display: flex; flex: 1; min-width: 0; overflow: hidden; }
.editor-pane-tab { position: relative; z-index: 2; display: grid; grid-template-columns: minmax(0,1fr); width: min(260px,45vw); min-width: 0; max-width: min(260px,45vw); height: 28px; flex: 0 1 min(260px,45vw); align-items: center; gap: var(--space-6); padding: 0 var(--space-10); border: 0; border-radius: 999px; background: var(--color-tab-active); color: var(--color-text); font: inherit; font-size: calc(12px * var(--font-scale)); text-align: left; }
.editor-pane-tab.closable { grid-template-columns: minmax(0,1fr) 8px 16px; }
.editor-pane-tab-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.editor-pane-dirty-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-accent); }
.editor-pane-tab-close { color: var(--color-text-muted); }
.editor-pane-tab-close:hover { color: var(--color-text); }
.editor-pane-toolbar-actions { display: flex; flex-shrink: 0; align-items: center; gap: var(--space-6); padding-bottom: var(--space-6); }
.editor-pane-toolbar.compact { gap: var(--space-4); padding-right: var(--space-6); padding-left: var(--space-6); }
.editor-pane-toolbar.compact .editor-pane-tab { min-width: 72px; max-width: 110px; }
.editor-pane-toolbar.compact .editor-pane-toolbar-actions { gap: var(--space-4); }
.editor-pane-toolbar.compact :deep(.editor-mode-switch button) { min-width: 54px; padding-right: var(--space-4); padding-left: var(--space-4); }
.editor-pane-save { display: inline-flex; height: 22px; align-items: center; justify-content: center; gap: var(--space-4); padding: 0 var(--space-8); border: 0; border-radius: var(--radius-sm); background: transparent; color: var(--color-text); font: inherit; font-size: calc(11px * var(--font-scale)); transition: background 160ms ease,color 160ms ease,transform 140ms cubic-bezier(.23,1,.32,1); }
.editor-pane-save:active:not(:disabled) { transform: scale(.94); }
.save-motion-icon,.save-motion-icon path { overflow: visible; transform-origin: center; transition: transform 220ms cubic-bezier(.23,1,.32,1); }
.editor-pane-save:disabled { cursor: not-allowed; opacity: .45; }
@media (hover:hover) and (pointer:fine) { .editor-pane-save:hover:not(:disabled) { background: var(--color-primary-softer); color: var(--color-primary-hover); } .editor-pane-save:hover:not(:disabled) .save-motion-icon { transform: rotate(-9deg) scale(1.1); } .editor-pane-save:hover:not(:disabled) [data-save-path='box'] { transform: translateY(1px) scale(1.04); } .editor-pane-save:hover:not(:disabled) [data-save-path='top'] { transform: translate(1.5px,1.5px) scaleX(.9); } .editor-pane-save:hover:not(:disabled) [data-save-path='bottom'] { transform: translateY(-2px) scaleY(.9); } }
@media (max-width:920px) { .editor-pane-toolbar { align-items: flex-start; flex-direction: column; } .editor-pane-toolbar-actions { width: 100%; overflow: hidden; } }
@media (prefers-reduced-motion:reduce) { .editor-pane-save,.save-motion-icon,.save-motion-icon path { transition: color 160ms ease,background 160ms ease; } .editor-pane-save:active:not(:disabled),.editor-pane-save:hover:not(:disabled) .save-motion-icon,.editor-pane-save:hover:not(:disabled) [data-save-path] { transform: none; } }
</style>
