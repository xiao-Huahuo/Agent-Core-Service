<!--
  Semantic graph node context menu.

  Usage:
  GraphPane positions this menu at the Canvas right-click coordinates. Its
  spacing, colors, hover treatment, and entrance motion match FileContextMenu.
-->
<script setup lang="ts">
import { ref } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import type { KnowledgeGraphNodeEvent } from '@/components/knowledge_graph/graphTypes'

defineOptions({ name: 'GraphNodeContextMenu' })

defineProps<{
  node: KnowledgeGraphNodeEvent
  menuStyle: Record<string, string>
}>()

const emit = defineEmits<{
  details: []
  open: []
  copyName: []
  delete: []
  clear: []
}>()

const menuRef = ref<HTMLElement | null>(null)

defineExpose({
  getBoundingClientRect: () => menuRef.value?.getBoundingClientRect() ?? new DOMRect(),
})
</script>

<template>
  <div ref="menuRef" class="graph-node-context-menu" :style="menuStyle" role="menu" @click.stop>
    <button type="button" role="menuitem" @click="emit('details')">
      <IcIcon name="search" :size="15" /><span>详情</span>
    </button>
    <button v-if="node.kind === 'document'" type="button" role="menuitem" @click="emit('open')">
      <IcIcon name="document" :size="15" /><span>打开</span>
    </button>
    <button type="button" role="menuitem" @click="emit('copyName')">
      <IcIcon name="text-fields" :size="15" /><span>复制名称</span>
    </button>
    <hr class="context-separator" />
    <button
      v-if="node.kind === 'entity'"
      class="danger"
      type="button"
      role="menuitem"
      @click="emit('delete')"
    >
      <IcIcon name="trash" :size="15" /><span>删除</span>
    </button>
    <button v-else class="danger" type="button" role="menuitem" @click="emit('clear')">
      <IcIcon name="trash" :size="15" /><span>清空节点</span>
    </button>
  </div>
</template>

<style scoped>
.graph-node-context-menu {
  position: fixed;
  z-index: 40;
  display: grid;
  min-width: 280px;
  padding: var(--space-6);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.2);
  transform-origin: top left;
  animation: context-menu-in 160ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

.graph-node-context-menu button {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  align-items: center;
  column-gap: var(--space-10);
  min-height: 30px;
  padding: 0 var(--space-8);
  border: 0;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  text-align: left;
}

.graph-node-context-menu button:hover {
  background: var(--color-selection-blue-soft);
  color: var(--color-text);
}

.graph-node-context-menu button:active {
  transform: translateY(1px);
}

.graph-node-context-menu span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.context-separator {
  width: 100%;
  margin: var(--space-6) 0;
  border: 0;
  border-top: 1px solid var(--color-border);
}

.graph-node-context-menu .danger {
  color: var(--color-danger);
}

@keyframes context-menu-in {
  from {
    opacity: 0;
    transform: translateY(-4px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .graph-node-context-menu {
    animation: context-menu-fade 120ms ease both;
  }
}

@keyframes context-menu-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
