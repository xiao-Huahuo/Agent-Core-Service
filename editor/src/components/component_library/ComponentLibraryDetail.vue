<!--
  Component library detail workbench.

  Usage:
  Render the selected component in a large interactive sandbox beside its
  exact stored source. Navigation is owned by ComponentLibraryView.
-->
<script setup lang="ts">
import { ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import ComponentPreview from '@/components/component_library/ComponentPreview.vue'
import CodePreview from '@/components/editor_workspace/CodePreview.vue'
import type { ComponentLibraryItem } from '@/types/componentLibrary'

defineOptions({ name: 'ComponentLibraryDetail' })

const props = withDefaults(defineProps<{
  item: ComponentLibraryItem
  deleting?: boolean
}>(), {
  deleting: false,
})
const emit = defineEmits<{
  delete: [item: ComponentLibraryItem]
}>()
const copied = ref(false)

/** Copy the original source represented by the detail workbench. */
async function copySource(): Promise<void> {
  await navigator.clipboard.writeText(props.item.source)
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 1400)
}
</script>

<template>
  <section class="detail-workbench" aria-label="组件详情">
    <section class="detail-preview-panel">
      <header class="panel-header">
        <span class="panel-label"><IcIcon name="visibility" :size="15" />实时预览</span>
        <span class="tag-pill">{{ item.tag }}</span>
      </header>
      <div class="detail-preview-surface">
        <ComponentPreview :source="item.source" :source-format="item.source_format" :label="item.title" />
      </div>
    </section>

    <section class="detail-code-panel">
      <header class="panel-header">
        <span class="panel-label"><IcIcon name="code" :size="16" />{{ item.source_format.toUpperCase() }}</span>
        <div class="panel-actions">
          <button
            class="detail-copy-button"
            type="button"
            :title="copied ? '已复制' : '复制代码'"
            :aria-label="copied ? '已复制' : '复制代码'"
            @click="copySource"
          >
            <IcIcon :name="copied ? 'check' : 'copy'" :size="15" />
          </button>
          <button
            class="detail-delete-button"
            type="button"
            title="删除组件"
            aria-label="删除组件"
            :disabled="deleting"
            @click="emit('delete', item)"
          >
            <IcIcon name="trash" :size="15" />
          </button>
        </div>
      </header>
      <CodePreview :content="item.source" :language="item.source_format" />
    </section>
  </section>
</template>

<style scoped>
.detail-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 1fr);
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  animation: detail-workbench-enter 220ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

.detail-preview-panel,
.detail-code-panel {
  display: grid;
  grid-template-rows: 44px minmax(0, 1fr);
  min-width: 0;
  min-height: 0;
}

.detail-preview-panel {
  background: var(--color-surface-raised);
  animation: detail-panel-enter 200ms 30ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

.detail-code-panel {
  background: var(--color-canvas);
  animation: detail-panel-enter 200ms 70ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-10);
  min-width: 0;
  padding: 0 var(--space-12);
  color: var(--color-text-secondary);
}

.panel-label,
.panel-actions,
.detail-copy-button,
.detail-delete-button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-6);
}

.panel-actions {
  gap: 2px;
}

.panel-label {
  font-size: calc(12px * var(--font-scale));
  font-weight: 700;
  letter-spacing: 0.02em;
}

.tag-pill {
  display: inline-flex;
  align-items: center;
  min-height: 23px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-primary) 26%, transparent);
  color: var(--color-primary);
  padding: 0 9px;
  font-size: calc(11px * var(--font-scale));
}

.detail-preview-surface {
  min-width: 0;
  min-height: 0;
}

.detail-copy-button,
.detail-delete-button {
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-secondary);
  padding: 0;
  cursor: pointer;
  transition:
    color 140ms ease,
    transform 140ms cubic-bezier(0.23, 1, 0.32, 1);
}

.detail-copy-button:hover {
  color: var(--color-primary);
}

.detail-delete-button:hover:not(:disabled) {
  color: var(--color-danger);
}

.detail-delete-button:disabled {
  cursor: wait;
  opacity: 0.45;
}

.detail-code-panel :deep(.code-preview) {
  height: 100%;
  min-width: 0;
  min-height: 0;
  background: transparent;
}

@media (hover: hover) and (pointer: fine) {
  .detail-copy-button:hover,
  .detail-delete-button:hover:not(:disabled) {
    transform: scale(1.1);
  }
}

@keyframes detail-workbench-enter {
  from { opacity: 0; transform: scale(0.99); }
  to { opacity: 1; transform: scale(1); }
}

@keyframes detail-panel-enter {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 900px) {
  .detail-workbench {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(360px, 1fr) minmax(360px, 1fr);
    overflow: visible;
  }

  .detail-preview-panel {
    border: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .detail-workbench,
  .detail-preview-panel,
  .detail-code-panel {
    animation: none;
    transform: none;
  }

  .detail-copy-button,
  .detail-delete-button {
    transform: none;
  }
}
</style>
