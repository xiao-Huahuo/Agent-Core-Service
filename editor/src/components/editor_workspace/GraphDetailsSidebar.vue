<!--
  Knowledge graph node details sidebar.

  Usage:
  GraphPane supplies filtered and connected nodes while this component owns
  only the existing search/details presentation and its open/close controls.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'
import type {
  KnowledgeGraphNode,
  KnowledgeGraphNodeEvent,
} from '@/components/knowledge_graph/graphTypes'

defineOptions({ name: 'GraphDetailsSidebar' })

defineProps<{
  open: boolean
  selectedNode: KnowledgeGraphNodeEvent | null
  searchResults: KnowledgeGraphNode[]
  connectedNodes: KnowledgeGraphNode[]
}>()

const searchQuery = defineModel<string>('searchQuery', { required: true })

defineEmits<{
  toggle: []
  close: []
  selectNode: [nodeId: string]
}>()

/** Return the compact localized label for one graph-node kind. */
function kindLabel(kind: string): string {
  if (kind === 'root') return '根'
  if (kind === 'folder') return '文件夹'
  if (kind === 'file') return '文件'
  if (kind === 'virtual-group') return '集锦'
  if (kind === 'document') return '文档'
  if (kind === 'entity') return '实体'
  return kind
}
</script>

<template>
  <button
    class="sidebar-tab"
    :class="{ open }"
    type="button"
    :title="open ? '关闭节点面板' : '节点面板'"
    @click="$emit('toggle')"
  >
    <IcIcon name="search" :size="14" />
  </button>

  <aside class="graph-sidebar" :class="{ open }">
    <div class="sidebar-header">
      <span class="sidebar-title">节点搜索</span>
      <button class="sidebar-close" type="button" @click="$emit('close')">
        <IcIcon name="close" :size="14" />
      </button>
    </div>

    <div class="sidebar-search">
      <IcIcon name="search" :size="14" class="search-icon" />
      <input v-model="searchQuery" class="search-input" type="text" placeholder="搜索节点名称..." />
    </div>

    <div v-if="searchQuery && searchResults.length > 0" class="sidebar-section">
      <div class="sidebar-label">搜索结果</div>
      <div class="search-tags">
        <button
          v-for="node in searchResults"
          :key="node.id"
          class="search-tag"
          :class="{ active: node.id === selectedNode?.id }"
          type="button"
          @click="$emit('selectNode', node.id)"
        >
          {{ node.label }}
        </button>
      </div>
    </div>
    <div v-else-if="searchQuery && searchResults.length === 0" class="sidebar-empty">
      无匹配节点
    </div>

    <div v-if="selectedNode" class="sidebar-section">
      <div class="sidebar-label">选中节点</div>
      <div class="selected-node-name">
        <span class="selected-node-kind-tag" :class="selectedNode.kind">{{
          kindLabel(selectedNode.kind)
        }}</span>
        {{ selectedNode.label }}
      </div>
    </div>

    <div v-if="connectedNodes.length > 0" class="sidebar-section sidebar-section-grow">
      <div class="sidebar-label">关联节点 ({{ connectedNodes.length }})</div>
      <div class="connected-list">
        <button
          v-for="node in connectedNodes"
          :key="node.id"
          class="connected-item"
          :class="{ active: node.id === selectedNode?.id }"
          :title="node.path || node.label"
          type="button"
          @click="$emit('selectNode', node.id)"
        >
          <span class="connected-kind-tag" :class="node.kind">{{ kindLabel(node.kind) }}</span>
          <span class="connected-name">{{ node.label }}</span>
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-tab {
  position: absolute;
  top: 50%;
  right: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-right: 0;
  border-radius: 8px 0 0 8px;
  background: var(--color-surface);
  color: var(--color-text-muted);
  transform: translateY(-50%);
}
.sidebar-tab:hover,
.sidebar-tab.open {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.graph-sidebar {
  display: flex;
  flex-direction: column;
  width: 0;
  min-width: 0;
  overflow: hidden;
  border-left: 0;
  background: var(--color-surface);
  transition:
    width 250ms ease,
    border-left-color 250ms ease;
}
.graph-sidebar.open {
  width: 280px;
  border-left: 0;
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-8) var(--space-12);
  border-bottom: 0;
}
.sidebar-title {
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
  font-weight: 600;
}
.sidebar-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--color-text-muted);
}
.sidebar-close:hover {
  background: var(--color-surface-raised);
  color: var(--color-text);
}
.sidebar-search {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  margin: var(--space-8) var(--space-12);
  padding: var(--space-4) var(--space-8);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface-raised);
}
.search-icon {
  flex-shrink: 0;
  color: var(--color-text-muted);
}
.search-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
}
.search-input::placeholder {
  color: var(--color-text-muted);
}
.sidebar-section {
  padding: var(--space-4) var(--space-12);
}
.sidebar-section-grow {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.sidebar-label {
  margin-bottom: var(--space-4);
  color: var(--color-text-muted);
  font-size: calc(10px * var(--font-scale));
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.sidebar-empty {
  padding: var(--space-8) var(--space-12);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}
.search-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}
.search-tag {
  display: inline-flex;
  align-items: center;
  max-width: 240px;
  min-height: 22px;
  overflow: hidden;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-raised);
  color: var(--color-text);
  font-size: calc(11px * var(--font-scale));
  text-overflow: ellipsis;
  white-space: nowrap;
}
.search-tag:hover {
  border-color: var(--color-primary);
}
.search-tag.active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.selected-node-name {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-6) 0;
  color: var(--color-text);
  font-size: calc(12px * var(--font-scale));
}
.selected-node-kind-tag,
.connected-kind-tag {
  display: inline-flex;
  align-items: center;
  min-height: 18px;
  padding: 0 6px;
  border-radius: 4px;
  font-size: calc(10px * var(--font-scale));
  font-weight: 600;
  white-space: nowrap;
}
.selected-node-kind-tag.entity,
.connected-kind-tag.entity {
  border: 1px solid var(--color-accent);
  background: color-mix(in srgb, var(--color-accent) 12%, transparent);
  color: var(--color-accent);
}
.selected-node-kind-tag.document,
.connected-kind-tag.document {
  border: 1px solid var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.selected-node-kind-tag.file,
.connected-kind-tag.file {
  border: 1px solid var(--color-border);
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
}
.selected-node-kind-tag.folder,
.connected-kind-tag.folder,
.selected-node-kind-tag.virtual-group,
.connected-kind-tag.virtual-group {
  border: 1px solid var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.connected-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.connected-item {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  width: 100%;
  padding: var(--space-4) var(--space-6);
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
  text-align: left;
  cursor: pointer;
}
.connected-item:hover {
  background: var(--color-primary-softer);
  color: var(--color-text);
}
.connected-item.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.connected-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
